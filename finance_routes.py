# finance_routes.py — Blueprint Flask : wallets, transactions, catégories, stats, export, SSE
from flask import Blueprint, request, jsonify, Response, stream_with_context
from db import get_conn
from jwt_utils import verify_token
import json, queue, threading, csv, io
from datetime import datetime

finance_bp = Blueprint('finance', __name__)

# ── SSE broadcast ─────────────────────────────────────────────────────────────
_subscribers: dict[int, list[queue.Queue]] = {}
_lock = threading.Lock()

def _notify(wallet_id: int, event_type: str, data: dict):
    msg = "data: " + json.dumps({'type': event_type, 'wallet_id': wallet_id, **data}) + "\n\n"
    with _lock:
        for uid, qs in list(_subscribers.items()):
            for q in qs:
                try:
                    q.put_nowait(msg)
                except queue.Full:
                    pass

# ── Auth helper ───────────────────────────────────────────────────────────────
def _auth():
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return None
    return verify_token(auth.split(' ', 1)[1])

def _uid(payload) -> int:
    return int(payload.get('sub') or payload.get('id') or 0)

# ── Wallet access check ───────────────────────────────────────────────────────
def _wallet_access(cur, wallet_id: int, user_id: int):
    cur.execute("SELECT id, owner_id, is_shared, name, currency, color, icon FROM wallets WHERE id=?", (wallet_id,))
    w = cur.fetchone()
    if not w:
        return None, False
    if w[1] == user_id:
        return w, True
    cur.execute("SELECT can_write FROM wallet_members WHERE wallet_id=? AND user_id=?", (wallet_id, user_id))
    m = cur.fetchone()
    if m:
        return w, bool(m[0])
    return None, False

# ═══════════════════════════════════════════════════════════════════════════════
# SSE — temps réel
# ═══════════════════════════════════════════════════════════════════════════════
@finance_bp.route('/api/events')
def sse_stream():
    # EventSource ne supporte pas les headers custom -> token en query param
    token_qs = request.args.get('token')
    if token_qs:
        from jwt_utils import verify_token as _vt
        p = _vt(token_qs)
    else:
        p = _auth()
    if not p:
        return jsonify({'error': 'unauthorized'}), 401
    user_id = _uid(p)
    q: queue.Queue = queue.Queue(maxsize=100)
    with _lock:
        _subscribers.setdefault(user_id, []).append(q)

    def generate():
        try:
            yield f"data: {json.dumps({'type':'connected','user_id':user_id})}\n\n"
            while True:
                try:
                    yield q.get(timeout=25)
                except queue.Empty:
                    yield ": ping\n\n"
        finally:
            with _lock:
                try:
                    _subscribers[user_id].remove(q)
                    if not _subscribers[user_id]:
                        del _subscribers[user_id]
                except Exception:
                    pass

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no', 'Connection': 'keep-alive'}
    )

# ═══════════════════════════════════════════════════════════════════════════════
# WALLETS
# ═══════════════════════════════════════════════════════════════════════════════
@finance_bp.route('/api/wallets', methods=['GET'])
def api_list_wallets():
    p = _auth()
    if not p:
        return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT w.id, w.name, w.description, w.currency, w.owner_id, w.is_shared,
                   w.color, w.icon, w.created_at,
                   COALESCE(u.name, u.login, u.email, '') AS owner_name,
                   COALESCE(w.iban,'') as iban,
                   COALESCE((
                       SELECT SUM(CASE WHEN t.type='income' THEN t.amount ELSE -t.amount END)
                       FROM transactions t WHERE t.wallet_id = w.id
                   ), 0) AS balance,
                   COALESCE((SELECT COUNT(*) FROM transactions t WHERE t.wallet_id=w.id),0) AS tx_count,
                   COALESCE(w.wallet_type,'personal') as wallet_type
            FROM wallets w
            JOIN users u ON u.id = w.owner_id
            WHERE w.owner_id = ?
               OR w.id IN (SELECT wallet_id FROM wallet_members WHERE user_id = ?)
            ORDER BY w.created_at DESC
        """, (uid, uid))
        rows = cur.fetchall()
        return jsonify([{
            'id': r[0], 'name': r[1], 'description': r[2], 'currency': r[3],
            'owner_id': r[4], 'is_shared': bool(r[5]), 'color': r[6], 'icon': r[7],
            'created_at': r[8], 'owner_name': r[9], 'iban': r[10] or '',
            'balance': round(float(r[11] or 0), 2), 'tx_count': r[12],
            'is_mine': r[4] == uid,
            'wallet_type': r[13] or 'personal'
        } for r in rows])
    finally:
        cur.close(); conn.close()


@finance_bp.route('/api/wallets', methods=['POST'])
def api_create_wallet():
    p = _auth()
    if not p:
        return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name_required'}), 400
    conn = get_conn()
    cur = conn.cursor()
    try:
        iban = (data.get('iban') or '').strip().upper().replace(' ','')
        wallet_type = data.get('wallet_type', 'personal')
        icon_map = {'personal':'💳','savings':'🏦','crypto':'₿','investment':'📈','cash':'💵','joint':'👫'}
        icon = data.get('icon') or icon_map.get(wallet_type, '💳')
        cur.execute("""
            INSERT INTO wallets (name, description, currency, owner_id, is_shared,
                                 color, icon, iban, wallet_type)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, (name, data.get('description',''), data.get('currency','EUR'),
              uid, 1 if wallet_type=='joint' else 0,
              data.get('color','#6366f1'), icon, iban, wallet_type))
        conn.commit()
        wid = cur.lastrowid
        if not wid:
            return jsonify({'error': 'insert_failed'}), 500
        # Si compte joint : ajouter le partenaire automatiquement
        partner = (data.get('partner') or '').strip()
        if wallet_type == 'joint' and partner:
            cur.execute("""
                SELECT id FROM users
                WHERE email=? OR login=? OR name=?
                LIMIT 1
            """, (partner, partner, partner))
            p_row = cur.fetchone()
            if p_row and p_row[0] != uid:
                cur.execute("""
                    INSERT OR IGNORE INTO wallet_members (wallet_id, user_id, can_write)
                    VALUES (?,?,1)
                """, (wid, p_row[0]))
                # Notification au partenaire
                try:
                    cur.execute("""
                        SELECT COALESCE(display_name,name,login,email,'') FROM users WHERE id=?
                    """, (uid,))
                    creator = cur.fetchone()
                    creator_name = creator[0] if creator else 'Votre partenaire'
                    cur.execute("""
                        INSERT INTO notifications (user_id, type, title, body)
                        VALUES (?,?,?,?)
                    """, (p_row[0], 'joint_wallet',
                          f'Compte joint ajouté',
                          f'{creator_name} vous a ajouté au compte joint « {name} »'))
                except Exception:
                    pass
                conn.commit()
        return jsonify({'id': wid, 'name': name, 'wallet_type': wallet_type}), 201
    finally:
        cur.close(); conn.close()


@finance_bp.route('/api/wallets/<int:wid>', methods=['PUT'])
def api_update_wallet(wid):
    p = _auth()
    if not p:
        return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    data = request.get_json() or {}
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT owner_id FROM wallets WHERE id=?", (wid,))
        w = cur.fetchone()
        if not w or w[0] != uid:
            return jsonify({'error': 'forbidden'}), 403
        fields = []
        vals = []
        for f in ('name','description','currency','color','icon','iban'):
            if f in data:
                fields.append(f"{f}=?")
                vals.append(data[f])
        if not fields:
            return jsonify({'error': 'nothing_to_update'}), 400
        vals.append(wid)
        cur.execute(f"UPDATE wallets SET {', '.join(fields)} WHERE id=?", vals)
        conn.commit()
        return jsonify({'ok': True})
    finally:
        cur.close(); conn.close()


@finance_bp.route('/api/wallets/<int:wid>', methods=['DELETE'])
def api_delete_wallet(wid):
    p = _auth()
    if not p:
        return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT owner_id FROM wallets WHERE id=?", (wid,))
        w = cur.fetchone()
        if not w or w[0] != uid:
            return jsonify({'error': 'forbidden'}), 403
        cur.execute("DELETE FROM transactions WHERE wallet_id=?", (wid,))
        cur.execute("DELETE FROM wallet_members WHERE wallet_id=?", (wid,))
        cur.execute("DELETE FROM wallets WHERE id=?", (wid,))
        conn.commit()
        return jsonify({'ok': True})
    finally:
        cur.close(); conn.close()

# ── Membres ───────────────────────────────────────────────────────────────────
@finance_bp.route('/api/wallets/<int:wid>/members', methods=['GET'])
def api_get_members(wid):
    p = _auth()
    if not p:
        return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    conn = get_conn()
    cur = conn.cursor()
    try:
        w, _ = _wallet_access(cur, wid, uid)
        if not w:
            return jsonify({'error': 'forbidden'}), 403
        cur.execute("""
            SELECT wm.user_id, COALESCE(u.name,u.login,u.email,'') as uname, u.email, wm.can_write, wm.added_at
            FROM wallet_members wm JOIN users u ON u.id=wm.user_id
            WHERE wm.wallet_id=?
        """, (wid,))
        return jsonify([{'user_id':r[0],'name':r[1],'email':r[2],'can_write':bool(r[3]),'added_at':r[4]} for r in cur.fetchall()])
    finally:
        cur.close(); conn.close()


@finance_bp.route('/api/wallets/<int:wid>/members', methods=['POST'])
def api_add_member(wid):
    p = _auth()
    if not p:
        return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    data = request.get_json() or {}
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT owner_id FROM wallets WHERE id=?", (wid,))
        w = cur.fetchone()
        if not w or w[0] != uid:
            return jsonify({'error': 'forbidden'}), 403
        search = (data.get('identifier') or data.get('email') or '').strip()
        # Cherche par email, login, name, ou id numérique
        cur.execute("""
            SELECT id, COALESCE(name,login,email,'') as uname, email
            FROM users
            WHERE email=? OR login=? OR name=?
               OR CAST(id AS TEXT)=?
            LIMIT 1
        """, (search, search, search, search))
        t = cur.fetchone()
        if not t:
            return jsonify({'error': 'user_not_found'}), 404
        if t[0] == uid:
            return jsonify({'error': 'cannot_add_self'}), 400
        cur.execute("INSERT OR IGNORE INTO wallet_members (wallet_id,user_id,can_write) VALUES (?,?,?)",
                    (wid, t[0], int(data.get('can_write', 1))))
        cur.execute("UPDATE wallets SET is_shared=1 WHERE id=?", (wid,))
        conn.commit()
        return jsonify({'ok': True, 'member': {'id':t[0],'name':t[1],'email':t[2]}}), 201
    finally:
        cur.close(); conn.close()


@finance_bp.route('/api/wallets/<int:wid>/members/<int:mid>', methods=['DELETE'])
def api_remove_member(wid, mid):
    p = _auth()
    if not p:
        return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT owner_id FROM wallets WHERE id=?", (wid,))
        w = cur.fetchone()
        if not w or w[0] != uid:
            return jsonify({'error': 'forbidden'}), 403
        cur.execute("DELETE FROM wallet_members WHERE wallet_id=? AND user_id=?", (wid, mid))
        conn.commit()
        return jsonify({'ok': True})
    finally:
        cur.close(); conn.close()

# ═══════════════════════════════════════════════════════════════════════════════
# CATÉGORIES
# ═══════════════════════════════════════════════════════════════════════════════
@finance_bp.route('/api/categories', methods=['GET'])
def api_categories():
    p = _auth()
    if not p:
        return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, name, type, color, icon FROM categories
            WHERE user_id IS NULL OR user_id=?
            ORDER BY type, name
        """, (uid,))
        return jsonify([{'id':r[0],'name':r[1],'type':r[2],'color':r[3],'icon':r[4]} for r in cur.fetchall()])
    finally:
        cur.close(); conn.close()


@finance_bp.route('/api/categories', methods=['POST'])
def api_create_category():
    p = _auth()
    if not p:
        return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    t = data.get('type', 'expense')
    if not name or t not in ('expense', 'income'):
        return jsonify({'error': 'invalid_data'}), 400
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO categories (name,type,color,icon,user_id) VALUES (?,?,?,?,?)",
                    (name, t, data.get('color','#6b7280'), data.get('icon','📦'), uid))
        conn.commit()
        return jsonify({'id': cur.lastrowid, 'name': name, 'type': t}), 201
    finally:
        cur.close(); conn.close()

# ═══════════════════════════════════════════════════════════════════════════════
# TRANSACTIONS
# ═══════════════════════════════════════════════════════════════════════════════
@finance_bp.route('/api/wallets/<int:wid>/transactions', methods=['GET'])
def api_list_transactions(wid):
    p = _auth()
    if not p:
        return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    conn = get_conn()
    cur = conn.cursor()
    try:
        w, _ = _wallet_access(cur, wid, uid)
        if not w:
            return jsonify({'error': 'forbidden'}), 403

        type_f   = request.args.get('type')
        cat_f    = request.args.get('category_id')
        date_from= request.args.get('from')
        date_to  = request.args.get('to')
        search   = request.args.get('q','').strip()
        limit    = min(int(request.args.get('limit', 50)), 500)
        offset   = int(request.args.get('offset', 0))

        sql = """
            SELECT t.id, t.amount, t.type, t.label, t.note, t.date, t.created_at,
                   t.user_id, COALESCE(u.name, u.login, u.email, '') AS author,
                   t.category_id, c.name, c.color, c.icon
            FROM transactions t
            LEFT JOIN users u      ON u.id = t.user_id
            LEFT JOIN categories c ON c.id = t.category_id
            WHERE t.wallet_id=?
        """
        params = [wid]
        if type_f:    sql += " AND t.type=?";          params.append(type_f)
        if cat_f:     sql += " AND t.category_id=?";   params.append(int(cat_f))
        if date_from: sql += " AND t.date>=?";         params.append(date_from)
        if date_to:   sql += " AND t.date<=?";         params.append(date_to)
        if search:    sql += " AND t.label LIKE ?";    params.append(f'%{search}%')
        sql += " ORDER BY t.date DESC, t.created_at DESC LIMIT ? OFFSET ?"
        params += [limit, offset]

        cur.execute(sql, params)
        txs = [{
            'id':r[0], 'amount':r[1], 'type':r[2], 'label':r[3], 'note':r[4],
            'date':r[5], 'created_at':r[6], 'user_id':r[7], 'author':r[8],
            'category_id':r[9], 'category_name':r[10] or 'Sans catégorie',
            'category_color':r[11] or '#6b7280', 'category_icon':r[12] or '📦'
        } for r in cur.fetchall()]

        cur.execute("SELECT COUNT(*) FROM transactions WHERE wallet_id=?", (wid,))
        total = cur.fetchone()[0]
        return jsonify({'transactions': txs, 'total': total, 'offset': offset, 'limit': limit})
    finally:
        cur.close(); conn.close()


@finance_bp.route('/api/wallets/<int:wid>/transactions', methods=['POST'])
def api_add_transaction(wid):
    p = _auth()
    if not p:
        return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    conn = get_conn()
    cur = conn.cursor()
    try:
        w, can_write = _wallet_access(cur, wid, uid)
        if not w or not can_write:
            return jsonify({'error': 'forbidden'}), 403
        data   = request.get_json() or {}
        try:
            amount = float(data.get('amount', 0))
        except (TypeError, ValueError):
            return jsonify({'error': 'invalid_amount'}), 400
        type_  = data.get('type', 'expense')
        label  = (data.get('label') or '').strip()
        if amount <= 0 or type_ not in ('expense','income') or not label:
            return jsonify({'error': 'invalid_data'}), 400
        date   = data.get('date') or datetime.now().strftime('%Y-%m-%d')
        cat_id = data.get('category_id') or None
        note   = (data.get('note') or '').strip()

        cur.execute("""
            INSERT INTO transactions (wallet_id,user_id,amount,type,category_id,label,note,date)
            VALUES (?,?,?,?,?,?,?,?)
        """, (wid, uid, amount, type_, cat_id, label, note, date))
        conn.commit()
        tx_id = cur.lastrowid

        # Solde mis à jour
        cur.execute("""
            SELECT COALESCE(SUM(CASE WHEN type='income' THEN amount ELSE -amount END),0)
            FROM transactions WHERE wallet_id=?
        """, (wid,))
        balance = round(cur.fetchone()[0], 2)

        # Récupérer catégorie pour la notif
        cat_name = cat_color = cat_icon = None
        if cat_id:
            cur.execute("SELECT name,color,icon FROM categories WHERE id=?", (cat_id,))
            cat_row = cur.fetchone()
            if cat_row:
                cat_name, cat_color, cat_icon = cat_row

        # Nom de l'auteur
        cur.execute("SELECT name FROM users WHERE id=?", (uid,))
        author_row = cur.fetchone()
        author = author_row[0] if author_row else ''

        _notify(wid, 'new_transaction', {
            'transaction': {
                'id': tx_id, 'wallet_id': wid, 'amount': amount, 'type': type_,
                'label': label, 'date': date, 'note': note,
                'category_id': cat_id, 'category_name': cat_name or 'Sans catégorie',
                'category_color': cat_color or '#6b7280', 'category_icon': cat_icon or '📦',
                'author': author, 'user_id': uid
            },
            'balance': balance
        })
        return jsonify({'id': tx_id, 'balance': balance}), 201
    finally:
        cur.close(); conn.close()


@finance_bp.route('/api/transactions/<int:tx_id>', methods=['PUT'])
def api_update_transaction(tx_id):
    p = _auth()
    if not p:
        return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    data = request.get_json() or {}
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT wallet_id, user_id FROM transactions WHERE id=?", (tx_id,))
        tx = cur.fetchone()
        if not tx:
            return jsonify({'error': 'not_found'}), 404
        wid = tx[0]
        cur.execute("SELECT owner_id FROM wallets WHERE id=?", (wid,))
        w = cur.fetchone()
        is_author = tx[1] == uid
        is_owner  = w and w[0] == uid
        cur.execute("SELECT id FROM wallet_members WHERE wallet_id=? AND user_id=?", (wid, uid))
        is_member = cur.fetchone() is not None
        if not (is_author or is_owner or is_member):
            return jsonify({'error': 'forbidden'}), 403

        fields, vals = [], []
        for f in ('amount','type','label','note','date','category_id'):
            if f in data:
                fields.append(f"{f}=?")
                vals.append(data[f])
        if not fields:
            return jsonify({'error': 'nothing_to_update'}), 400
        vals.append(tx_id)
        cur.execute(f"UPDATE transactions SET {', '.join(fields)} WHERE id=?", vals)
        conn.commit()

        cur.execute("SELECT COALESCE(SUM(CASE WHEN type='income' THEN amount ELSE -amount END),0) FROM transactions WHERE wallet_id=?", (wid,))
        balance = round(cur.fetchone()[0], 2)
        _notify(wid, 'update_transaction', {'transaction_id': tx_id, 'balance': balance})
        return jsonify({'ok': True, 'balance': balance})
    finally:
        cur.close(); conn.close()


@finance_bp.route('/api/transactions/<int:tx_id>', methods=['DELETE'])
def api_delete_transaction(tx_id):
    p = _auth()
    if not p:
        return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT wallet_id, user_id FROM transactions WHERE id=?", (tx_id,))
        tx = cur.fetchone()
        if not tx:
            return jsonify({'error': 'not_found'}), 404
        wid = tx[0]
        cur.execute("SELECT owner_id FROM wallets WHERE id=?", (wid,))
        w = cur.fetchone()
        # Peut supprimer si : auteur OU propriétaire OU n'importe quel membre du wallet
        is_author = tx[1] == uid
        is_owner  = w and w[0] == uid
        cur.execute("SELECT id FROM wallet_members WHERE wallet_id=? AND user_id=?", (wid, uid))
        is_member = cur.fetchone() is not None
        if not (is_author or is_owner or is_member):
            return jsonify({'error': 'forbidden'}), 403
        cur.execute("DELETE FROM transactions WHERE id=?", (tx_id,))
        conn.commit()
        cur.execute("SELECT COALESCE(SUM(CASE WHEN type='income' THEN amount ELSE -amount END),0) FROM transactions WHERE wallet_id=?", (wid,))
        balance = round(cur.fetchone()[0], 2)
        _notify(wid, 'delete_transaction', {'transaction_id': tx_id, 'balance': balance})
        return jsonify({'ok': True, 'balance': balance})
    finally:
        cur.close(); conn.close()

# ═══════════════════════════════════════════════════════════════════════════════
# STATS & SOLDE
# ═══════════════════════════════════════════════════════════════════════════════
@finance_bp.route('/api/wallets/<int:wid>/balance', methods=['GET'])
def api_balance(wid):
    p = _auth()
    if not p:
        return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    conn = get_conn()
    cur = conn.cursor()
    try:
        w, _ = _wallet_access(cur, wid, uid)
        if not w:
            return jsonify({'error': 'forbidden'}), 403
        cur.execute("""
            SELECT COALESCE(SUM(CASE WHEN type='income'  THEN amount ELSE 0 END),0),
                   COALESCE(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END),0)
            FROM transactions WHERE wallet_id=?
        """, (wid,))
        r = cur.fetchone()
        return jsonify({'income': round(r[0],2), 'expense': round(r[1],2), 'balance': round(r[0]-r[1],2)})
    finally:
        cur.close(); conn.close()


@finance_bp.route('/api/wallets/<int:wid>/stats', methods=['GET'])
def api_stats(wid):
    p = _auth()
    if not p:
        return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    conn = get_conn()
    cur = conn.cursor()
    try:
        w, _ = _wallet_access(cur, wid, uid)
        if not w:
            return jsonify({'error': 'forbidden'}), 403

        # Évolution mensuelle (12 derniers mois)
        cur.execute("""
            SELECT strftime('%Y-%m', date) AS month,
                   SUM(CASE WHEN type='income'  THEN amount ELSE 0 END),
                   SUM(CASE WHEN type='expense' THEN amount ELSE 0 END)
            FROM transactions WHERE wallet_id=?
            GROUP BY month ORDER BY month DESC LIMIT 12
        """, (wid,))
        monthly = [{'month':r[0], 'income':round(r[1],2), 'expense':round(r[2],2)} for r in cur.fetchall()]
        monthly.reverse()

        # Dépenses par catégorie
        cur.execute("""
            SELECT c.name, c.color, c.icon, SUM(t.amount) AS total
            FROM transactions t
            LEFT JOIN categories c ON c.id = t.category_id
            WHERE t.wallet_id=? AND t.type='expense'
            GROUP BY t.category_id ORDER BY total DESC LIMIT 10
        """, (wid,))
        by_cat = [{'name':r[0] or 'Sans catégorie','color':r[1] or '#6b7280','icon':r[2] or '📦','total':round(r[3],2)} for r in cur.fetchall()]

        # Revenus par catégorie
        cur.execute("""
            SELECT c.name, c.color, c.icon, SUM(t.amount) AS total
            FROM transactions t
            LEFT JOIN categories c ON c.id = t.category_id
            WHERE t.wallet_id=? AND t.type='income'
            GROUP BY t.category_id ORDER BY total DESC LIMIT 10
        """, (wid,))
        by_cat_income = [{'name':r[0] or 'Sans catégorie','color':r[1] or '#6b7280','icon':r[2] or '📦','total':round(r[3],2)} for r in cur.fetchall()]

        return jsonify({'monthly': monthly, 'by_category_expense': by_cat, 'by_category_income': by_cat_income})
    finally:
        cur.close(); conn.close()

# ═══════════════════════════════════════════════════════════════════════════════
# EXPORT CSV
# ═══════════════════════════════════════════════════════════════════════════════
@finance_bp.route('/api/wallets/<int:wid>/export/csv', methods=['GET'])
def api_export_csv(wid):
    p = _auth()
    if not p:
        return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    conn = get_conn()
    cur = conn.cursor()
    try:
        w, _ = _wallet_access(cur, wid, uid)
        if not w:
            return jsonify({'error': 'forbidden'}), 403
        cur.execute("SELECT name FROM wallets WHERE id=?", (wid,))
        wname = cur.fetchone()[0]
        cur.execute("""
            SELECT t.date, t.label, t.type, t.amount, c.name, t.note, u.name
            FROM transactions t
            LEFT JOIN categories c ON c.id=t.category_id
            LEFT JOIN users u      ON u.id=t.user_id
            WHERE t.wallet_id=?
            ORDER BY t.date DESC
        """, (wid,))
        buf = io.StringIO()
        w_csv = csv.writer(buf, delimiter=';')
        w_csv.writerow(['Date','Libellé','Type','Montant (€)','Catégorie','Note','Auteur'])
        for r in cur.fetchall():
            w_csv.writerow([r[0], r[1], 'Revenu' if r[2]=='income' else 'Dépense',
                            f'{r[3]:.2f}', r[4] or '', r[5] or '', r[6] or ''])
        buf.seek(0)
        fn = f"transactions_{wname.replace(' ','_')}.csv"
        return Response('\ufeff' + buf.getvalue(),
                        mimetype='text/csv; charset=utf-8-sig',
                        headers={'Content-Disposition': f'attachment; filename="{fn}"'})
    finally:
        cur.close(); conn.close()

# ═══════════════════════════════════════════════════════════════════════════════
# RECHERCHE UTILISATEURS (pour inviter dans un wallet)
# ═══════════════════════════════════════════════════════════════════════════════
@finance_bp.route('/api/users/search', methods=['GET'])
def api_search_users():
    p = _auth()
    if not p:
        return jsonify({'error': 'unauthorized'}), 401
    q = request.args.get('q','').strip()
    if len(q) < 2:
        return jsonify([])
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, COALESCE(name,login,email,'') as name, email FROM users WHERE name LIKE ? OR login LIKE ? OR email LIKE ? LIMIT 10",
                    (f'%{q}%', f'%{q}%', f'%{q}%'))
        return jsonify([{'id':r[0],'name':r[1],'email':r[2]} for r in cur.fetchall()])
    finally:
        cur.close(); conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN API ROUTES
# ═══════════════════════════════════════════════════════════════════════════════
import subprocess
from datetime import datetime

def _is_admin(p):
    if not p: return False
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("SELECT role FROM users WHERE id=?", (_uid(p),))
        row = cur.fetchone()
        return bool(row and row[0] == 'admin')
    finally:
        cur.close(); conn.close()

@finance_bp.route('/api/admin/users', methods=['GET'])
def admin_list_users():
    p = _auth()
    if not _is_admin(p): return jsonify({'error':'forbidden'}), 403
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("SELECT id, COALESCE(login,email,'') as login, email, role, created_at FROM users ORDER BY id")
        rows = cur.fetchall()
        return jsonify([{'id':r[0],'login':r[1],'email':r[2],'role':r[3],'created_at':r[4]} for r in rows])
    finally:
        cur.close(); conn.close()

@finance_bp.route('/api/admin/users', methods=['POST'])
def admin_create_user():
    p = _auth()
    if not _is_admin(p): return jsonify({'error':'forbidden'}), 403
    import bcrypt
    data = request.get_json() or {}
    login = (data.get('login') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    if not login or not email or len(password) < 4:
        return jsonify({'error':'invalid_data'}), 400
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (login, email, role, password_hash, created_at) VALUES (?,?,?,?,datetime('now'))",
            (login, email, data.get('role','user'), pw_hash)
        )
        conn.commit()
        return jsonify({'id': cur.lastrowid}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 409
    finally:
        cur.close(); conn.close()

@finance_bp.route('/api/admin/users/<int:uid>/role', methods=['PUT'])
def admin_update_role(uid):
    p = _auth()
    if not _is_admin(p): return jsonify({'error':'forbidden'}), 403
    role = (request.get_json() or {}).get('role','user')
    if role not in ('admin','user'): return jsonify({'error':'invalid_role'}), 400
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("UPDATE users SET role=? WHERE id=?", (role, uid))
        conn.commit()
        return jsonify({'ok': True})
    finally:
        cur.close(); conn.close()

@finance_bp.route('/api/admin/users/<int:uid>/password', methods=['PUT'])
def admin_reset_password(uid):
    p = _auth()
    if not _is_admin(p): return jsonify({'error':'forbidden'}), 403
    import bcrypt
    pw = (request.get_json() or {}).get('password','')
    if len(pw) < 4: return jsonify({'error':'too_short'}), 400
    pw_hash = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("UPDATE users SET password_hash=? WHERE id=?", (pw_hash, uid))
        conn.commit()
        return jsonify({'ok': True})
    finally:
        cur.close(); conn.close()

@finance_bp.route('/api/admin/users/<int:uid>', methods=['DELETE'])
def admin_delete_user(uid):
    p = _auth()
    if not _is_admin(p): return jsonify({'error':'forbidden'}), 403
    if uid == _uid(p): return jsonify({'error':'cannot_delete_self'}), 400
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("DELETE FROM users WHERE id=?", (uid,))
        conn.commit()
        return jsonify({'ok': True})
    finally:
        cur.close(); conn.close()

@finance_bp.route('/api/admin/config', methods=['GET'])
def admin_get_config():
    p = _auth()
    if not _is_admin(p): return jsonify({'error':'forbidden'}), 403
    import os, config as cfg
    # Priorité : variables d'environnement (chargées depuis .env) > config.py
    return jsonify({
        'smtp_host': os.getenv('SMTP_HOST') or getattr(cfg,'SMTP_HOST',''),
        'smtp_port': int(os.getenv('SMTP_PORT') or getattr(cfg,'SMTP_PORT',587)),
        'smtp_user': os.getenv('SMTP_USER') or getattr(cfg,'SMTP_USER',''),
    })

@finance_bp.route('/api/admin/config', methods=['PUT'])
def admin_save_config():
    p = _auth()
    if not _is_admin(p): return jsonify({'error':'forbidden'}), 403
    # Ecrit dans un fichier .env (non commité)
    data = request.get_json() or {}
    lines = []
    if 'smtp_host' in data: lines.append(f"SMTP_HOST={data['smtp_host']}")
    if 'smtp_port' in data: lines.append(f"SMTP_PORT={data['smtp_port']}")
    if 'smtp_user' in data: lines.append(f"SMTP_USER={data['smtp_user']}")
    if data.get('smtp_pass'):   lines.append(f"SMTP_PASS={data['smtp_pass']}")
    try:
        with open('.env', 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n')
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@finance_bp.route('/api/admin/smtp/test', methods=['POST'])
def admin_test_smtp():
    p = _auth()
    if not _is_admin(p): return jsonify({'error':'forbidden'}), 403
    import smtplib, os, config as cfg
    from email.message import EmailMessage

    host = os.getenv('SMTP_HOST') or getattr(cfg,'SMTP_HOST','')
    port = int(os.getenv('SMTP_PORT') or getattr(cfg,'SMTP_PORT',587))
    user = os.getenv('SMTP_USER') or getattr(cfg,'SMTP_USER','')
    pw   = os.getenv('SMTP_PASS') or getattr(cfg,'SMTP_PASS','')
    use_tls = os.getenv('SMTP_USE_TLS','').lower() in ('1','true','yes')

    if not host or not user:
        return jsonify({'ok': False, 'error': 'SMTP non configuré — vérifiez hôte et utilisateur'}), 200

    # Essai 1 : STARTTLS port 587
    errors = []
    for try_port, try_ssl in [(port, False), (465, True), (587, False), (25, False)]:
        try:
            if try_ssl or try_port == 465:
                with smtplib.SMTP_SSL(host, try_port, timeout=8) as s:
                    if pw: s.login(user, pw)
                    msg = EmailMessage()
                    msg['Subject'] = 'FinanceApp — Test SMTP ✓'
                    msg['From']    = user
                    msg['To']      = user
                    msg.set_content('Test de connexion SMTP depuis FinanceApp. Tout fonctionne !')
                    s.send_message(msg)
            else:
                with smtplib.SMTP(host, try_port, timeout=8) as s:
                    s.ehlo()
                    s.starttls()
                    s.ehlo()
                    if pw: s.login(user, pw)
                    msg = EmailMessage()
                    msg['Subject'] = 'FinanceApp — Test SMTP ✓'
                    msg['From']    = user
                    msg['To']      = user
                    msg.set_content('Test de connexion SMTP depuis FinanceApp. Tout fonctionne !')
                    s.send_message(msg)
            return jsonify({'ok': True, 'port_used': try_port,
                           'message': f'Email envoyé sur {user} via port {try_port}'})
        except Exception as e:
            errors.append(f'Port {try_port}: {str(e)}')
            continue

    return jsonify({'ok': False, 'error': ' | '.join(errors)}), 200

@finance_bp.route('/api/admin/db/stats', methods=['GET'])
def admin_db_stats():
    p = _auth()
    if not _is_admin(p): return jsonify({'error':'forbidden'}), 403
    conn = get_conn(); cur = conn.cursor()
    try:
        stats = {}
        for table in ('users','wallets','transactions','categories','wallet_members'):
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            stats[table] = cur.fetchone()[0]
        return jsonify(stats)
    finally:
        cur.close(); conn.close()

@finance_bp.route('/api/admin/db/purge', methods=['DELETE'])
def admin_purge():
    p = _auth()
    if not _is_admin(p): return jsonify({'error':'forbidden'}), 403
    days = int(request.args.get('days', 365))
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute(
            "DELETE FROM transactions WHERE date < date('now', ?)",
            (f'-{days} days',)
        )
        conn.commit()
        return jsonify({'ok': True, 'deleted': cur.rowcount})
    finally:
        cur.close(); conn.close()

@finance_bp.route('/api/admin/version', methods=['GET'])
def admin_version():
    p = _auth()
    if not _is_admin(p): return jsonify({'error':'forbidden'}), 403
    import config as cfg
    info = {'current': getattr(cfg,'APP_VERSION','1.0.0')}
    try:
        info['git_branch'] = subprocess.check_output(
            ['git','rev-parse','--abbrev-ref','HEAD'], stderr=subprocess.DEVNULL
        ).decode().strip()
        info['git_commit'] = subprocess.check_output(
            ['git','log','-1','--format=%h %s'], stderr=subprocess.DEVNULL
        ).decode().strip()
        info['git_remote'] = subprocess.check_output(
            ['git','remote','get-url','origin'], stderr=subprocess.DEVNULL
        ).decode().strip()
        info['last_updated'] = subprocess.check_output(
            ['git','log','-1','--format=%cd','--date=short'], stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        info['git_branch'] = 'non disponible'
        info['git_commit'] = '—'
        info['git_remote'] = 'non configuré'
        info['last_updated'] = '—'
    return jsonify(info)

@finance_bp.route('/api/admin/migrate', methods=['POST'])
def admin_migrate():
    p = _auth()
    if not _is_admin(p): return jsonify({'error':'forbidden'}), 403
    try:
        result = subprocess.run(
            ['python', 'migrate_finance.py'],
            capture_output=True, text=True, timeout=30
        )
        return jsonify({'ok': result.returncode == 0, 'output': result.stdout + result.stderr})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@finance_bp.route('/api/categories/<int:cat_id>', methods=['PUT'])
def api_update_category(cat_id):
    p = _auth()
    if not p: return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    data = request.get_json() or {}
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("SELECT user_id FROM categories WHERE id=?", (cat_id,))
        row = cur.fetchone()
        if not row: return jsonify({'error': 'not_found'}), 404
        # Can edit own categories or global (admin only)
        if row[0] is not None and row[0] != uid:
            return jsonify({'error': 'forbidden'}), 403
        fields, vals = [], []
        for f in ('name','type','icon','color'):
            if f in data:
                fields.append(f"{f}=?"); vals.append(data[f])
        if not fields: return jsonify({'error': 'nothing_to_update'}), 400
        vals.append(cat_id)
        cur.execute(f"UPDATE categories SET {', '.join(fields)} WHERE id=?", vals)
        conn.commit()
        return jsonify({'ok': True})
    finally:
        cur.close(); conn.close()

@finance_bp.route('/api/categories/<int:cat_id>', methods=['DELETE'])
def api_delete_category(cat_id):
    p = _auth()
    if not p: return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("SELECT user_id FROM categories WHERE id=?", (cat_id,))
        row = cur.fetchone()
        if not row: return jsonify({'error': 'not_found'}), 404
        if row[0] is not None and row[0] != uid:
            return jsonify({'error': 'forbidden'}), 403
        # Set transactions to null category instead of deleting
        cur.execute("UPDATE transactions SET category_id=NULL WHERE category_id=?", (cat_id,))
        cur.execute("DELETE FROM categories WHERE id=?", (cat_id,))
        conn.commit()
        return jsonify({'ok': True})
    finally:
        cur.close(); conn.close()

@finance_bp.route('/api/admin/users/<int:uid>/info', methods=['PUT'])
def admin_update_user_info(uid):
    p = _auth()
    if not _is_admin(p): return jsonify({'error':'forbidden'}), 403
    data = request.get_json() or {}
    conn = get_conn(); cur = conn.cursor()
    try:
        fields, vals = [], []
        for f in ('login', 'email', 'display_name', 'name'):
            if f in data and data[f]:
                fields.append(f"{f}=?")
                vals.append(data[f].strip())
        if not fields: return jsonify({'error': 'nothing_to_update'}), 400
        vals.append(uid)
        cur.execute(f"UPDATE users SET {', '.join(fields)} WHERE id=?", vals)
        conn.commit()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        cur.close(); conn.close()
