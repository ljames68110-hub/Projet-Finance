# routes_v3.py — Dépenses fixes + compte joint
from flask import Blueprint, request, jsonify
from db import get_conn
from jwt_utils import verify_token
from datetime import datetime, date
# pas de dateutil nécessaire

v3_bp = Blueprint('v3', __name__)

def _auth():
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '): return None
    return verify_token(auth.split(' ', 1)[1])

def _uid(p) -> int:
    return int(p.get('sub') or p.get('id') or 0)

def _wallet_ok(cur, wid, uid, need_write=False):
    cur.execute("SELECT id, owner_id FROM wallets WHERE id=?", (wid,))
    w = cur.fetchone()
    if not w: return False
    if w[1] == uid: return True
    cur.execute("SELECT can_write FROM wallet_members WHERE wallet_id=? AND user_id=?", (wid, uid))
    m = cur.fetchone()
    if not m: return False
    if need_write: return bool(m[0])
    return True

def _next_date(current: str, frequency: str) -> str:
    try:
        d = datetime.strptime(current, '%Y-%m-%d').date()
    except Exception:
        d = date.today()
    import calendar
    if frequency == 'weekly':
        from datetime import timedelta
        return (d + timedelta(weeks=1)).strftime('%Y-%m-%d')
    elif frequency == 'biweekly':
        from datetime import timedelta
        return (d + timedelta(weeks=2)).strftime('%Y-%m-%d')
    elif frequency == 'quarterly':
        m = d.month + 3
        y = d.year + (m - 1) // 12
        m = (m - 1) % 12 + 1
        day = min(d.day, calendar.monthrange(y, m)[1])
        return date(y, m, day).strftime('%Y-%m-%d')
    elif frequency == 'yearly':
        y = d.year + 1
        day = min(d.day, calendar.monthrange(y, d.month)[1])
        return date(y, d.month, day).strftime('%Y-%m-%d')
    else:  # monthly par défaut
        m = d.month + 1
        y = d.year + (m - 1) // 12
        m = (m - 1) % 12 + 1
        day = min(d.day, calendar.monthrange(y, m)[1])
        return date(y, m, day).strftime('%Y-%m-%d')

# ═══════════════════════════════════════════════════════════════════════════════
# COMPTE JOINT
# ═══════════════════════════════════════════════════════════════════════════════
@v3_bp.route('/api/wallets/joint', methods=['POST'])
def create_joint_wallet():
    """Crée un compte joint et invite automatiquement le conjoint"""
    p = _auth()
    if not p: return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    data = request.get_json() or {}
    name = (data.get('name') or 'Compte Joint').strip()
    partner_identifier = (data.get('partner') or '').strip()
    if not partner_identifier:
        return jsonify({'error': 'partner_required'}), 400

    conn = get_conn(); cur = conn.cursor()
    try:
        import bcrypt
        # Trouver le partenaire
        cur.execute("""
            SELECT id, COALESCE(display_name, name, login, email, '') as uname, email
            FROM users
            WHERE email=? OR login=? OR name=? OR display_name=?
               OR CAST(id AS TEXT)=?
            LIMIT 1
        """, (partner_identifier, partner_identifier, partner_identifier,
               partner_identifier, partner_identifier))
        partner = cur.fetchone()
        if not partner:
            return jsonify({'error': 'partner_not_found'}), 404
        if partner[0] == uid:
            return jsonify({'error': 'cannot_add_self'}), 400

        # Créer le wallet joint
        iban = (data.get('iban') or '').strip().upper().replace(' ','')
        cur.execute("""
            INSERT INTO wallets (name, description, currency, owner_id, is_shared,
                                 color, icon, wallet_type, iban)
            VALUES (?,?,?,?,1,?,?,?,?)
        """, (name, data.get('description', 'Compte partagé'),
              data.get('currency', 'EUR'), uid,
              data.get('color', '#22c55e'), '👫', 'joint', iban))
        conn.commit()
        wid = cur.lastrowid

        # Ajouter le partenaire comme membre avec droits complets
        cur.execute("""
            INSERT OR IGNORE INTO wallet_members (wallet_id, user_id, can_write)
            VALUES (?,?,1)
        """, (wid, partner[0]))
        conn.commit()

        # Notification au partenaire
        try:
            # Récupérer le nom du créateur
            cur.execute("SELECT COALESCE(display_name,name,login,email,'') FROM users WHERE id=?", (uid,))
            creator_row = cur.fetchone()
            creator_name = creator_row[0] if creator_row else 'Votre partenaire'
            cur.execute("""
                INSERT INTO notifications (user_id, type, title, body)
                VALUES (?,?,?,?)
            """, (partner[0], 'joint_wallet',
                  f'Compte joint \u00ab {name} \u00bb cr\u00e9\u00e9',
                  f'{creator_name} vous a ajout\u00e9 au compte joint. Reconnectez-vous pour le voir.'))
            conn.commit()
        except Exception:
            pass

        return jsonify({
            'id': wid, 'name': name,
            'partner': {'id': partner[0], 'name': partner[1], 'email': partner[2]}
        }), 201
    finally:
        cur.close(); conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# DÉPENSES FIXES
# ═══════════════════════════════════════════════════════════════════════════════
@v3_bp.route('/api/wallets/<int:wid>/fixed', methods=['GET'])
def list_fixed(wid):
    p = _auth()
    if not p: return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    conn = get_conn(); cur = conn.cursor()
    try:
        if not _wallet_ok(cur, wid, uid):
            return jsonify({'error': 'forbidden'}), 403
        cur.execute("""
            SELECT f.id, f.label, f.amount, f.frequency, f.next_date,
                   f.auto_insert, f.note, f.active, f.category_id,
                   COALESCE(c.name,'Sans catégorie') as cat_name,
                   COALESCE(c.icon,'📦') as cat_icon,
                   COALESCE(c.color,'#6b7280') as cat_color,
                   COALESCE(u.name, u.login, u.email,'') as author,
                   f.user_id, f.created_at
            FROM fixed_expenses f
            LEFT JOIN categories c ON c.id=f.category_id
            LEFT JOIN users u ON u.id=f.user_id
            WHERE f.wallet_id=?
            ORDER BY f.next_date ASC
        """, (wid,))
        rows = cur.fetchall()
        today = date.today().strftime('%Y-%m-%d')
        result = []
        for r in rows:
            days_left = None
            try:
                nd = datetime.strptime(r[4], '%Y-%m-%d').date()
                days_left = (nd - date.today()).days
            except Exception:
                pass
            result.append({
                'id': r[0], 'label': r[1], 'amount': r[2],
                'frequency': r[3], 'next_date': r[4],
                'auto_insert': bool(r[5]), 'note': r[6], 'active': bool(r[7]),
                'category_id': r[8], 'cat_name': r[9], 'cat_icon': r[10],
                'cat_color': r[11], 'author': r[12], 'user_id': r[13],
                'created_at': r[14], 'days_left': days_left,
                'overdue': days_left is not None and days_left < 0
            })
        return jsonify(result)
    finally:
        cur.close(); conn.close()


@v3_bp.route('/api/wallets/<int:wid>/fixed', methods=['POST'])
def create_fixed(wid):
    p = _auth()
    if not p: return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    data = request.get_json() or {}
    label = (data.get('label') or '').strip()
    try:
        amount = float(data.get('amount', 0))
    except (TypeError, ValueError):
        return jsonify({'error': 'invalid_amount'}), 400
    if not label or amount <= 0:
        return jsonify({'error': 'invalid_data'}), 400

    conn = get_conn(); cur = conn.cursor()
    try:
        if not _wallet_ok(cur, wid, uid, need_write=True):
            return jsonify({'error': 'forbidden'}), 403
        frequency  = data.get('frequency', 'monthly')
        next_date  = data.get('next_date') or date.today().replace(day=1).strftime('%Y-%m-%d')
        auto_insert= int(data.get('auto_insert', 0))
        note       = (data.get('note') or '').strip()
        cat_id     = data.get('category_id') or None

        cur.execute("""
            INSERT INTO fixed_expenses
                (wallet_id, user_id, label, amount, category_id,
                 frequency, next_date, auto_insert, note)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (wid, uid, label, amount, cat_id,
              frequency, next_date, auto_insert, note))
        conn.commit()
        fid = cur.lastrowid

        # Si auto_insert actif et date déjà passée → insérer maintenant
        if auto_insert:
            _try_auto_insert(conn, cur, fid, wid, uid, label, amount, cat_id, next_date)

        return jsonify({'id': fid}), 201
    finally:
        cur.close(); conn.close()


@v3_bp.route('/api/fixed/<int:fid>', methods=['PUT'])
def update_fixed(fid):
    p = _auth()
    if not p: return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    data = request.get_json() or {}
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("SELECT wallet_id, user_id FROM fixed_expenses WHERE id=?", (fid,))
        f = cur.fetchone()
        if not f: return jsonify({'error': 'not_found'}), 404
        if not _wallet_ok(cur, f[0], uid, need_write=True):
            return jsonify({'error': 'forbidden'}), 403

        fields, vals = [], []
        for field in ('label','amount','category_id','frequency','next_date',
                      'auto_insert','note','active'):
            if field in data:
                fields.append(f"{field}=?")
                vals.append(data[field])
        if not fields: return jsonify({'error': 'nothing_to_update'}), 400
        vals.append(fid)
        cur.execute(f"UPDATE fixed_expenses SET {', '.join(fields)} WHERE id=?", vals)
        conn.commit()
        return jsonify({'ok': True})
    finally:
        cur.close(); conn.close()


@v3_bp.route('/api/fixed/<int:fid>', methods=['DELETE'])
def delete_fixed(fid):
    p = _auth()
    if not p: return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("SELECT wallet_id, user_id FROM fixed_expenses WHERE id=?", (fid,))
        f = cur.fetchone()
        if not f: return jsonify({'error': 'not_found'}), 404
        if not _wallet_ok(cur, f[0], uid, need_write=True):
            return jsonify({'error': 'forbidden'}), 403
        cur.execute("DELETE FROM fixed_expenses WHERE id=?", (fid,))
        conn.commit()
        return jsonify({'ok': True})
    finally:
        cur.close(); conn.close()


@v3_bp.route('/api/fixed/<int:fid>/pay', methods=['POST'])
def pay_fixed(fid):
    """Marque la dépense fixe comme payée et calcule la prochaine échéance"""
    p = _auth()
    if not p: return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("""
            SELECT f.wallet_id, f.label, f.amount, f.category_id,
                   f.frequency, f.next_date
            FROM fixed_expenses f WHERE f.id=?
        """, (fid,))
        f = cur.fetchone()
        if not f: return jsonify({'error': 'not_found'}), 404
        wid = f[0]
        if not _wallet_ok(cur, wid, uid, need_write=True):
            return jsonify({'error': 'forbidden'}), 403

        # Insérer la transaction
        pay_date = date.today().strftime('%Y-%m-%d')
        cur.execute("""
            INSERT INTO transactions
                (wallet_id, user_id, amount, type, category_id, label, note, date)
            VALUES (?,?,?,?,?,?,?,?)
        """, (wid, uid, f[2], 'expense', f[3],
              f[1], 'Dépense fixe automatique', pay_date))

        # Calculer prochaine échéance
        new_next = _next_date(f[5], f[4])
        cur.execute("UPDATE fixed_expenses SET next_date=? WHERE id=?", (new_next, fid))
        conn.commit()

        # Solde mis à jour
        cur.execute("""
            SELECT COALESCE(SUM(CASE WHEN type='income' THEN amount ELSE -amount END),0)
            FROM transactions WHERE wallet_id=?
        """, (wid,))
        balance = round(cur.fetchone()[0], 2)

        return jsonify({'ok': True, 'tx_id': cur.lastrowid,
                       'next_date': new_next, 'balance': balance})
    finally:
        cur.close(); conn.close()


def _try_auto_insert(conn, cur, fid, wid, uid, label, amount, cat_id, next_date):
    """Insère automatiquement si la date est aujourd'hui ou passée"""
    try:
        nd = datetime.strptime(next_date, '%Y-%m-%d').date()
        if nd <= date.today():
            cur.execute("""
                INSERT INTO transactions
                    (wallet_id, user_id, amount, type, category_id, label, note, date)
                VALUES (?,?,?,?,?,?,?,?)
            """, (wid, uid, amount, 'expense', cat_id,
                  label, 'Dépense fixe automatique', date.today().strftime('%Y-%m-%d')))
            new_next = _next_date(next_date, 'monthly')
            cur.execute("UPDATE fixed_expenses SET next_date=? WHERE id=?",
                        (new_next, fid))
            conn.commit()
    except Exception:
        pass


# ── Vérifier et auto-insérer les dépenses fixes dues ─────────────────────────
@v3_bp.route('/api/wallets/<int:wid>/fixed/process', methods=['POST'])
def process_fixed(wid):
    """Traite toutes les dépenses fixes auto dues pour ce wallet"""
    p = _auth()
    if not p: return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    conn = get_conn(); cur = conn.cursor()
    try:
        if not _wallet_ok(cur, wid, uid): return jsonify({'error': 'forbidden'}), 403
        today = date.today().strftime('%Y-%m-%d')
        cur.execute("""
            SELECT id, label, amount, category_id, frequency, next_date
            FROM fixed_expenses
            WHERE wallet_id=? AND auto_insert=1 AND active=1 AND next_date<=?
        """, (wid, today))
        due = cur.fetchall()
        inserted = 0
        for f in due:
            cur.execute("""
                INSERT INTO transactions
                    (wallet_id, user_id, amount, type, category_id, label, note, date)
                VALUES (?,?,?,?,?,?,?,?)
            """, (wid, uid, f[2], 'expense', f[3],
                  f[1], 'Dépense fixe auto', today))
            new_next = _next_date(f[5], f[4])
            cur.execute("UPDATE fixed_expenses SET next_date=? WHERE id=?",
                        (new_next, f[0]))
            inserted += 1
        conn.commit()
        return jsonify({'ok': True, 'inserted': inserted})
    finally:
        cur.close(); conn.close()
