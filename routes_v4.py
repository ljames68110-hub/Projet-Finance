# routes_v4.py — Revenus fixes + rappels CAF
from flask import Blueprint, request, jsonify
from db import get_conn
from jwt_utils import verify_token
from datetime import datetime, date
import calendar

v4_bp = Blueprint('v4', __name__)

def _auth():
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '): return None
    return verify_token(auth.split(' ', 1)[1])

def _uid(p) -> int:
    return int(p.get('sub') or p.get('id') or 0)

def _wallet_ok(cur, wid, uid):
    cur.execute("SELECT id, owner_id FROM wallets WHERE id=?", (wid,))
    w = cur.fetchone()
    if not w: return False
    if w[1] == uid: return True
    cur.execute("SELECT 1 FROM wallet_members WHERE wallet_id=? AND user_id=?", (wid, uid))
    return bool(cur.fetchone())

def _next_date_calc(current: str, frequency: str) -> str:
    try:
        d = datetime.strptime(current, '%Y-%m-%d').date()
    except Exception:
        d = date.today()
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
    else:  # monthly
        m = d.month + 1
        y = d.year + (m - 1) // 12
        m = (m - 1) % 12 + 1
        day = min(d.day, calendar.monthrange(y, m)[1])
        return date(y, m, day).strftime('%Y-%m-%d')

# ═══════════════════════════════════════════════════════════════════════════════
# REVENUS FIXES
# ═══════════════════════════════════════════════════════════════════════════════
@v4_bp.route('/api/wallets/<int:wid>/fixed-incomes', methods=['GET'])
def list_fixed_incomes(wid):
    p = _auth()
    if not p: return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    conn = get_conn(); cur = conn.cursor()
    try:
        if not _wallet_ok(cur, wid, uid):
            return jsonify({'error': 'forbidden'}), 403
        cur.execute("""
            SELECT fi.id, fi.label, fi.amount, fi.frequency, fi.next_date,
                   fi.auto_insert, fi.note, fi.active, fi.category_id,
                   fi.income_type,
                   COALESCE(c.name,'Sans catégorie') as cat_name,
                   COALESCE(c.icon,'💰') as cat_icon,
                   COALESCE(c.color,'#22c55e') as cat_color,
                   COALESCE(u.name, u.login, u.email,'') as author,
                   fi.user_id, fi.created_at
            FROM fixed_incomes fi
            LEFT JOIN categories c ON c.id=fi.category_id
            LEFT JOIN users u ON u.id=fi.user_id
            WHERE fi.wallet_id=?
            ORDER BY fi.next_date ASC
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
                'category_id': r[8], 'income_type': r[9],
                'cat_name': r[10], 'cat_icon': r[11], 'cat_color': r[12],
                'author': r[13], 'user_id': r[14], 'created_at': r[15],
                'days_left': days_left,
                'overdue': days_left is not None and days_left < 0
            })
        return jsonify(result)
    finally:
        cur.close(); conn.close()


@v4_bp.route('/api/wallets/<int:wid>/fixed-incomes', methods=['POST'])
def create_fixed_income(wid):
    p = _auth()
    if not p: return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    data = request.get_json() or {}
    label = (data.get('label') or '').strip()
    if not label: return jsonify({'error': 'label_required'}), 400
    conn = get_conn(); cur = conn.cursor()
    try:
        if not _wallet_ok(cur, wid, uid):
            return jsonify({'error': 'forbidden'}), 403
        amount = data.get('amount')
        try:
            amount = float(amount) if amount else None
        except (TypeError, ValueError):
            amount = None
        frequency  = data.get('frequency', 'monthly')
        next_date  = data.get('next_date') or date.today().replace(day=5).strftime('%Y-%m-%d')
        auto_insert= int(data.get('auto_insert', 0))
        note       = (data.get('note') or '').strip()
        cat_id     = data.get('category_id') or None
        income_type= data.get('income_type', 'regular')
        cur.execute("""
            INSERT INTO fixed_incomes
                (wallet_id, user_id, label, amount, category_id,
                 frequency, next_date, auto_insert, note, income_type)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (wid, uid, label, amount, cat_id,
              frequency, next_date, auto_insert, note, income_type))
        conn.commit()
        return jsonify({'id': cur.lastrowid}), 201
    finally:
        cur.close(); conn.close()


@v4_bp.route('/api/fixed-incomes/<int:fid>', methods=['PUT'])
def update_fixed_income(fid):
    p = _auth()
    if not p: return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    data = request.get_json() or {}
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("SELECT wallet_id, user_id FROM fixed_incomes WHERE id=?", (fid,))
        f = cur.fetchone()
        if not f: return jsonify({'error': 'not_found'}), 404
        if not _wallet_ok(cur, f[0], uid):
            return jsonify({'error': 'forbidden'}), 403
        fields, vals = [], []
        for field in ('label','amount','category_id','frequency','next_date',
                      'auto_insert','note','active','income_type'):
            if field in data:
                fields.append(f"{field}=?")
                vals.append(data[field])
        if not fields: return jsonify({'error': 'nothing_to_update'}), 400
        vals.append(fid)
        cur.execute(f"UPDATE fixed_incomes SET {', '.join(fields)} WHERE id=?", vals)
        conn.commit()
        return jsonify({'ok': True})
    finally:
        cur.close(); conn.close()


@v4_bp.route('/api/fixed-incomes/<int:fid>', methods=['DELETE'])
def delete_fixed_income(fid):
    p = _auth()
    if not p: return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("SELECT wallet_id FROM fixed_incomes WHERE id=?", (fid,))
        f = cur.fetchone()
        if not f: return jsonify({'error': 'not_found'}), 404
        if not _wallet_ok(cur, f[0], uid):
            return jsonify({'error': 'forbidden'}), 403
        cur.execute("DELETE FROM fixed_incomes WHERE id=?", (fid,))
        conn.commit()
        return jsonify({'ok': True})
    finally:
        cur.close(); conn.close()


@v4_bp.route('/api/fixed-incomes/<int:fid>/receive', methods=['POST'])
def receive_fixed_income(fid):
    """Enregistre la reception d'un revenu fixe.
    CAF/variable : meme montant chaque mois, revision tous les 3 mois.
    """
    p = _auth()
    if not p: return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    data = request.get_json() or {}
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("""
            SELECT fi.wallet_id, fi.label, fi.amount, fi.category_id,
                   fi.frequency, fi.next_date, fi.income_type
            FROM fixed_incomes fi WHERE fi.id=?
        """, (fid,))
        f = cur.fetchone()
        if not f: return jsonify({'error': 'not_found'}), 404
        wid = f[0]
        if not _wallet_ok(cur, wid, uid):
            return jsonify({'error': 'forbidden'}), 403
        amount = float(data.get('amount') or f[2] or 0)
        if amount <= 0: return jsonify({'error': 'invalid_amount'}), 400
        recv_date = date.today().strftime('%Y-%m-%d')
        income_type = f[6] or 'regular'
        cur.execute("""
            INSERT INTO transactions
                (wallet_id, user_id, amount, type, category_id, label, note, date)
            VALUES (?,?,?,?,?,?,?,?)
        """, (wid, uid, amount, 'income', f[3], f[1],
              'Versement CAF / allocation' if income_type == 'variable' else 'Revenu fixe',
              recv_date))
        # CAF : prochaine insertion dans 1 mois (meme montant)
        # Revision : tous les 3 mois via le rappel
        if income_type == 'variable':
            new_next = _next_date_calc(recv_date, 'monthly')
        else:
            new_next = _next_date_calc(f[5], f[4])
        cur.execute("UPDATE fixed_incomes SET next_date=?, amount=? WHERE id=?",
                    (new_next, amount, fid))
        # Mettre a jour le rappel de revision trimestriel
        if income_type == 'variable':
            try:
                m = date.today().month + 3
                y = date.today().year + (m - 1) // 12
                m = (m - 1) % 12 + 1
                import calendar as cal
                day = min(5, cal.monthrange(y, m)[1])
                next_rev = date(y, m, day).strftime('%Y-%m-%d')
                cur.execute("""
                    UPDATE income_reminders SET last_asked=?, last_amount=?
                    WHERE wallet_id=? AND label LIKE ?
                """, (recv_date, amount, wid, f[1]))
            except Exception:
                pass
        conn.commit()
        cur.execute("""
            SELECT COALESCE(SUM(CASE WHEN type='income' THEN amount ELSE -amount END),0)
            FROM transactions WHERE wallet_id=?
        """, (wid,))
        balance = round(cur.fetchone()[0], 2)
        return jsonify({'ok': True, 'next_date': new_next, 'balance': balance})
    finally:
        cur.close(); conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# RAPPELS CAF / REVENUS VARIABLES
# ═══════════════════════════════════════════════════════════════════════════════
@v4_bp.route('/api/wallets/<int:wid>/reminders', methods=['GET'])
def list_reminders(wid):
    p = _auth()
    if not p: return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    conn = get_conn(); cur = conn.cursor()
    try:
        if not _wallet_ok(cur, wid, uid):
            return jsonify({'error': 'forbidden'}), 403
        cur.execute("""
            SELECT id, label, description, frequency, day_of_period,
                   last_asked, last_amount, active
            FROM income_reminders
            WHERE wallet_id=? AND active=1
            ORDER BY day_of_period ASC
        """, (wid,))
        rows = cur.fetchall()
        today = date.today()
        result = []
        for r in rows:
            # Vérifier si le rappel doit être affiché aujourd'hui
            should_ask = False
            day_of_period = r[4] or 5
            freq = r[3] or 'quarterly'
            if freq == 'quarterly':
                # Les mois 1, 4, 7, 10 le jour indiqué
                if today.month in (1, 4, 7, 10) and today.day >= day_of_period:
                    last = r[5]
                    if not last or last[:7] != today.strftime('%Y-%m'):
                        should_ask = True
            elif freq == 'monthly':
                if today.day >= day_of_period:
                    last = r[5]
                    if not last or last[:7] != today.strftime('%Y-%m'):
                        should_ask = True
            result.append({
                'id': r[0], 'label': r[1], 'description': r[2],
                'frequency': r[3], 'day_of_period': r[4],
                'last_asked': r[5], 'last_amount': r[6],
                'active': bool(r[7]), 'should_ask': should_ask
            })
        return jsonify(result)
    finally:
        cur.close(); conn.close()


@v4_bp.route('/api/wallets/<int:wid>/reminders', methods=['POST'])
def create_reminder(wid):
    p = _auth()
    if not p: return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    data = request.get_json() or {}
    conn = get_conn(); cur = conn.cursor()
    try:
        if not _wallet_ok(cur, wid, uid):
            return jsonify({'error': 'forbidden'}), 403
        next_rev = (data.get('next_revision_date') or '').strip()
        cur.execute("""
            INSERT INTO income_reminders
                (wallet_id, user_id, label, description, frequency, day_of_period, last_asked)
            VALUES (?,?,?,?,?,?,?)
        """, (wid, uid,
              (data.get('label') or '').strip(),
              (data.get('description') or '').strip(),
              data.get('frequency', 'quarterly'),
              int(data.get('day_of_period', 5)),
              None))
        # Stocker la date de révision dans une notification
        if next_rev:
            cur.execute("""
                UPDATE income_reminders SET last_asked=NULL
                WHERE id=last_insert_rowid()
            """)
        conn.commit()
        return jsonify({'id': cur.lastrowid}), 201
    finally:
        cur.close(); conn.close()


@v4_bp.route('/api/reminders/<int:rid>/answer', methods=['POST'])
def answer_reminder(rid):
    """Enregistre la réponse au rappel CAF et crée la transaction"""
    p = _auth()
    if not p: return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    data = request.get_json() or {}
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("""
            SELECT wallet_id, label FROM income_reminders WHERE id=?
        """, (rid,))
        r = cur.fetchone()
        if not r: return jsonify({'error': 'not_found'}), 404
        wid = r[0]
        if not _wallet_ok(cur, wid, uid):
            return jsonify({'error': 'forbidden'}), 403
        amount = float(data.get('amount', 0))
        if amount <= 0: return jsonify({'error': 'invalid_amount'}), 400
        today = date.today().strftime('%Y-%m-%d')
        # Créer la transaction
        cur.execute("""
            INSERT INTO transactions
                (wallet_id, user_id, amount, type, category_id, label, note, date)
            VALUES (?,?,?,?,?,?,?,?)
        """, (wid, uid, amount, 'income', None,
              r[1], data.get('note', 'Allocation / Aide'), today))
        # Mettre à jour le rappel
        cur.execute("""
            UPDATE income_reminders
            SET last_asked=?, last_amount=?
            WHERE id=?
        """, (today, amount, rid))
        conn.commit()
        cur.execute("""
            SELECT COALESCE(SUM(CASE WHEN type='income' THEN amount ELSE -amount END),0)
            FROM transactions WHERE wallet_id=?
        """, (wid,))
        balance = round(cur.fetchone()[0], 2)
        return jsonify({'ok': True, 'balance': balance})
    finally:
        cur.close(); conn.close()


@v4_bp.route('/api/reminders/<int:rid>', methods=['DELETE'])
def delete_reminder(rid):
    p = _auth()
    if not p: return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("SELECT wallet_id FROM income_reminders WHERE id=?", (rid,))
        r = cur.fetchone()
        if not r: return jsonify({'error': 'not_found'}), 404
        if not _wallet_ok(cur, r[0], uid):
            return jsonify({'error': 'forbidden'}), 403
        cur.execute("DELETE FROM income_reminders WHERE id=?", (rid,))
        conn.commit()
        return jsonify({'ok': True})
    finally:
        cur.close(); conn.close()


@v4_bp.route('/api/wallets/<int:wid>/reminders/check', methods=['GET'])
def check_reminders(wid):
    """Retourne les rappels qui doivent être affichés aujourd'hui"""
    p = _auth()
    if not p: return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    conn = get_conn(); cur = conn.cursor()
    try:
        if not _wallet_ok(cur, wid, uid):
            return jsonify({'error': 'forbidden'}), 403
        today = date.today()
        cur.execute("""
            SELECT id, label, description, frequency, day_of_period, last_asked, last_amount
            FROM income_reminders
            WHERE wallet_id=? AND active=1
        """, (wid,))
        rows = cur.fetchall()
        pending = []
        for r in rows:
            day_of_period = r[4] or 5
            freq = r[3] or 'quarterly'
            last_asked = r[5]
            should_ask = False

            if freq == 'quarterly':
                # Vérifier si aujourd'hui >= jour révision du mois trimestriel
                caf_months = {1, 4, 7, 10}
                if today.month in caf_months and today.day >= day_of_period:
                    if not last_asked or last_asked[:7] != today.strftime('%Y-%m'):
                        should_ask = True
            elif freq == 'monthly':
                if today.day >= day_of_period:
                    if not last_asked or last_asked[:7] != today.strftime('%Y-%m'):
                        should_ask = True

            if should_ask:
                pending.append({
                    'id': r[0], 'label': r[1], 'description': r[2],
                    'last_amount': r[6]
                })
        return jsonify({'pending': pending, 'count': len(pending)})
    finally:
        cur.close(); conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# AUTO-INSERTION DES REVENUS FIXES ÉCHUS
# ═══════════════════════════════════════════════════════════════════════════════
@v4_bp.route('/api/wallets/<int:wid>/fixed-incomes/process', methods=['POST'])
def process_fixed_incomes(wid):
    """Insère automatiquement les revenus fixes échus dont auto_insert=1"""
    p = _auth()
    if not p: return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    conn = get_conn(); cur = conn.cursor()
    try:
        if not _wallet_ok(cur, wid, uid):
            return jsonify({'error': 'forbidden'}), 403
        today = date.today().strftime('%Y-%m-%d')
        cur.execute("""
            SELECT id, label, amount, category_id, frequency, next_date
            FROM fixed_incomes
            WHERE wallet_id=? AND auto_insert=1 AND active=1
              AND amount IS NOT NULL AND amount > 0
              AND next_date <= ?
        """, (wid, today))
        due = cur.fetchall()
        inserted = 0
        for f in due:
            # Insérer la transaction de revenu
            cur.execute("""
                INSERT INTO transactions
                    (wallet_id, user_id, amount, type, category_id, label, note, date)
                VALUES (?,?,?,?,?,?,?,?)
            """, (wid, uid, f[2], 'income', f[3],
                  f[1], 'Revenu fixe automatique', today))
            # Calculer prochaine échéance
            new_next = _next_date_calc(f[5], f[4])
            cur.execute("UPDATE fixed_incomes SET next_date=? WHERE id=?",
                        (new_next, f[0]))
            inserted += 1
        conn.commit()
        return jsonify({'ok': True, 'inserted': inserted})
    finally:
        cur.close(); conn.close()
