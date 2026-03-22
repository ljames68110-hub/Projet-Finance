# routes_v2.py — Blueprint v2 : dettes, budgets, notifications, profil, recherche, PDF
from flask import Blueprint, request, jsonify, Response
from db import get_conn
from jwt_utils import verify_token
from datetime import datetime, date
import json

v2_bp = Blueprint('v2', __name__)

# ── Auth ──────────────────────────────────────────────────────────────────────
def _auth():
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return None
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

def _push_notif(conn, cur, user_id, type_, title, body='', link=''):
    try:
        cur.execute(
            "INSERT INTO notifications (user_id,type,title,body,link) VALUES (?,?,?,?,?)",
            (user_id, type_, title, body, link)
        )
        conn.commit()
    except Exception:
        pass

# ═══════════════════════════════════════════════════════════════════════════════
# PROFIL UTILISATEUR
# ═══════════════════════════════════════════════════════════════════════════════
@v2_bp.route('/api/profile', methods=['GET'])
def get_profile():
    p = _auth()
    if not p: return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, COALESCE(display_name,login,email,'') as display_name,
                   email, COALESCE(login,'') as login, role,
                   COALESCE(avatar_color,'#6366f1') as avatar_color,
                   COALESCE(phone,'') as phone,
                   COALESCE(notify_email,1) as notify_email,
                   COALESCE(notify_app,1) as notify_app,
                   created_at
            FROM users WHERE id=?
        """, (uid,))
        r = cur.fetchone()
        if not r: return jsonify({'error': 'not_found'}), 404
        return jsonify({
            'id': r[0], 'display_name': r[1], 'email': r[2], 'login': r[3],
            'role': r[4], 'avatar_color': r[5], 'phone': r[6],
            'notify_email': bool(r[7]), 'notify_app': bool(r[8]), 'created_at': r[9]
        })
    finally:
        cur.close(); conn.close()


@v2_bp.route('/api/profile', methods=['PUT'])
def update_profile():
    p = _auth()
    if not p: return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    data = request.get_json() or {}
    conn = get_conn(); cur = conn.cursor()
    try:
        fields, vals = [], []
        for f in ('display_name', 'avatar_color', 'phone', 'notify_email', 'notify_app'):
            if f in data:
                fields.append(f"{f}=?")
                vals.append(data[f])
        if 'password' in data and data['password']:
            import bcrypt
            if len(data['password']) < 4:
                return jsonify({'error': 'password_too_short'}), 400
            pw_hash = bcrypt.hashpw(data['password'].encode(), bcrypt.gensalt()).decode()
            fields.append("password_hash=?"); vals.append(pw_hash)
        if not fields:
            return jsonify({'error': 'nothing_to_update'}), 400
        vals.append(uid)
        cur.execute(f"UPDATE users SET {', '.join(fields)} WHERE id=?", vals)
        conn.commit()
        return jsonify({'ok': True})
    finally:
        cur.close(); conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# RECHERCHE GLOBALE
# ═══════════════════════════════════════════════════════════════════════════════
@v2_bp.route('/api/search', methods=['GET'])
def global_search():
    p = _auth()
    if not p: return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    q = request.args.get('q', '').strip()
    if len(q) < 2: return jsonify({'transactions': [], 'wallets': [], 'debts': []})
    conn = get_conn(); cur = conn.cursor()
    try:
        # Transactions
        cur.execute("""
            SELECT t.id, t.label, t.amount, t.type, t.date,
                   w.name as wallet_name, w.id as wallet_id,
                   COALESCE(c.icon,'📦') as cat_icon, COALESCE(c.color,'#6b7280') as cat_color
            FROM transactions t
            JOIN wallets w ON w.id=t.wallet_id
            LEFT JOIN categories c ON c.id=t.category_id
            WHERE (w.owner_id=? OR w.id IN (SELECT wallet_id FROM wallet_members WHERE user_id=?))
              AND (t.label LIKE ? OR t.note LIKE ?)
            ORDER BY t.date DESC LIMIT 20
        """, (uid, uid, f'%{q}%', f'%{q}%'))
        txs = [{'id':r[0],'label':r[1],'amount':r[2],'type':r[3],'date':r[4],
                'wallet_name':r[5],'wallet_id':r[6],'cat_icon':r[7],'cat_color':r[8]}
               for r in cur.fetchall()]

        # Wallets
        cur.execute("""
            SELECT w.id, w.name, w.icon, w.color,
                   COALESCE(SUM(CASE WHEN t.type='income' THEN t.amount ELSE -t.amount END),0) as balance
            FROM wallets w LEFT JOIN transactions t ON t.wallet_id=w.id
            WHERE (w.owner_id=? OR w.id IN (SELECT wallet_id FROM wallet_members WHERE user_id=?))
              AND w.name LIKE ?
            GROUP BY w.id LIMIT 10
        """, (uid, uid, f'%{q}%'))
        wallets = [{'id':r[0],'name':r[1],'icon':r[2],'color':r[3],'balance':round(r[4],2)}
                   for r in cur.fetchall()]

        # Dettes
        cur.execute("""
            SELECT d.id, d.description, d.amount, d.status, d.due_date,
                   COALESCE(d.debtor_name,'') as debtor_name, w.name as wallet_name
            FROM debts d JOIN wallets w ON w.id=d.wallet_id
            WHERE d.creditor_id=? AND (d.description LIKE ? OR d.debtor_name LIKE ?)
            LIMIT 10
        """, (uid, f'%{q}%', f'%{q}%'))
        debts = [{'id':r[0],'description':r[1],'amount':r[2],'status':r[3],
                  'due_date':r[4],'debtor_name':r[5],'wallet_name':r[6]}
                 for r in cur.fetchall()]

        return jsonify({'transactions': txs, 'wallets': wallets, 'debts': debts})
    finally:
        cur.close(); conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# DETTES / REMBOURSEMENTS
# ═══════════════════════════════════════════════════════════════════════════════
@v2_bp.route('/api/wallets/<int:wid>/debts', methods=['GET'])
def list_debts(wid):
    p = _auth()
    if not p: return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    conn = get_conn(); cur = conn.cursor()
    try:
        if not _wallet_ok(cur, wid, uid):
            return jsonify({'error': 'forbidden'}), 403
        status_f = request.args.get('status', '')
        sql = """
            SELECT d.id, d.creditor_id, d.debtor_id, d.debtor_name, d.amount,
                   d.description, d.due_date, d.status, d.paid_at, d.created_at,
                   COALESCE(u.display_name, u.login, u.email, '') as debtor_user
            FROM debts d
            LEFT JOIN users u ON u.id=d.debtor_id
            WHERE d.wallet_id=?
        """
        params = [wid]
        if status_f: sql += " AND d.status=?"; params.append(status_f)
        sql += " ORDER BY d.created_at DESC"
        cur.execute(sql, params)
        rows = cur.fetchall()
        return jsonify([{
            'id':r[0],'creditor_id':r[1],'debtor_id':r[2],
            'debtor_name': r[10] if r[2] else r[3],
            'amount':r[4],'description':r[5],'due_date':r[6],
            'status':r[7],'paid_at':r[8],'created_at':r[9]
        } for r in rows])
    finally:
        cur.close(); conn.close()


@v2_bp.route('/api/wallets/<int:wid>/debts', methods=['POST'])
def create_debt(wid):
    p = _auth()
    if not p: return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    data = request.get_json() or {}
    try:
        amount = float(data.get('amount', 0))
    except (TypeError, ValueError):
        return jsonify({'error': 'invalid_amount'}), 400
    if amount <= 0: return jsonify({'error': 'invalid_amount'}), 400
    conn = get_conn(); cur = conn.cursor()
    try:
        if not _wallet_ok(cur, wid, uid):
            return jsonify({'error': 'forbidden'}), 403
        debtor_id = data.get('debtor_id')
        debtor_name = (data.get('debtor_name') or '').strip()
        due_date = data.get('due_date') or None
        description = (data.get('description') or '').strip()
        cur.execute("""
            INSERT INTO debts (wallet_id, creditor_id, debtor_id, debtor_name, amount, description, due_date)
            VALUES (?,?,?,?,?,?,?)
        """, (wid, uid, debtor_id, debtor_name, amount, description, due_date))
        conn.commit()
        debt_id = cur.lastrowid
        # Notif si debtor est un utilisateur enregistré
        if debtor_id:
            _push_notif(conn, cur, debtor_id, 'debt',
                        f'Vous devez {amount:.2f}€',
                        description or 'Nouvelle dette enregistrée')
        return jsonify({'id': debt_id}), 201
    finally:
        cur.close(); conn.close()


@v2_bp.route('/api/debts/<int:did>/pay', methods=['POST'])
def mark_debt_paid(did):
    p = _auth()
    if not p: return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("SELECT creditor_id, debtor_id, amount, description FROM debts WHERE id=?", (did,))
        d = cur.fetchone()
        if not d: return jsonify({'error': 'not_found'}), 404
        if d[0] != uid: return jsonify({'error': 'forbidden'}), 403
        cur.execute("UPDATE debts SET status='paid', paid_at=datetime('now') WHERE id=?", (did,))
        conn.commit()
        if d[1]:
            _push_notif(conn, cur, d[1], 'debt_paid',
                        f'Dette de {d[2]:.2f}€ marquée comme remboursée',
                        d[3] or '')
        return jsonify({'ok': True})
    finally:
        cur.close(); conn.close()


@v2_bp.route('/api/debts/<int:did>', methods=['DELETE'])
def delete_debt(did):
    p = _auth()
    if not p: return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("SELECT creditor_id FROM debts WHERE id=?", (did,))
        d = cur.fetchone()
        if not d: return jsonify({'error': 'not_found'}), 404
        if d[0] != uid: return jsonify({'error': 'forbidden'}), 403
        cur.execute("DELETE FROM debts WHERE id=?", (did,))
        conn.commit()
        return jsonify({'ok': True})
    finally:
        cur.close(); conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# BUDGETS MENSUELS
# ═══════════════════════════════════════════════════════════════════════════════
@v2_bp.route('/api/wallets/<int:wid>/budgets', methods=['GET'])
def list_budgets(wid):
    p = _auth()
    if not p: return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    month = request.args.get('month', date.today().strftime('%Y-%m'))
    conn = get_conn(); cur = conn.cursor()
    try:
        if not _wallet_ok(cur, wid, uid):
            return jsonify({'error': 'forbidden'}), 403
        cur.execute("""
            SELECT b.id, b.name, b.amount, b.category_id, b.alert_pct, b.month,
                   COALESCE(c.name,'Toutes catégories') as cat_name,
                   COALESCE(c.icon,'📦') as cat_icon, COALESCE(c.color,'#6b7280') as cat_color,
                   COALESCE((
                       SELECT SUM(t.amount) FROM transactions t
                       WHERE t.wallet_id=b.wallet_id
                         AND (b.category_id IS NULL OR t.category_id=b.category_id)
                         AND t.type='expense'
                         AND strftime('%Y-%m', t.date)=b.month
                   ),0) as spent
            FROM budgets b
            LEFT JOIN categories c ON c.id=b.category_id
            WHERE b.wallet_id=? AND b.month=?
            ORDER BY b.created_at DESC
        """, (wid, month))
        rows = cur.fetchall()
        result = []
        for r in rows:
            spent = round(r[9], 2)
            budget = r[2]
            pct = round((spent / budget * 100) if budget > 0 else 0, 1)
            # Alerte dépassement
            if pct >= r[4] and pct < 100:
                _push_notif(conn, cur, uid, 'budget_alert',
                            f'Budget « {r[1] }» à {pct}%',
                            f'{spent:.2f}€ / {budget:.2f}€ dépensés')
            elif pct >= 100:
                _push_notif(conn, cur, uid, 'budget_exceeded',
                            f'Budget « {r[1]} » dépassé !',
                            f'{spent:.2f}€ / {budget:.2f}€')
            result.append({
                'id':r[0],'name':r[1],'amount':budget,'category_id':r[3],
                'alert_pct':r[4],'month':r[5],'cat_name':r[6],'cat_icon':r[7],
                'cat_color':r[8],'spent':spent,'pct':pct,
                'status': 'exceeded' if pct>=100 else ('warning' if pct>=r[4] else 'ok')
            })
        return jsonify(result)
    finally:
        cur.close(); conn.close()


@v2_bp.route('/api/wallets/<int:wid>/budgets', methods=['POST'])
def create_budget(wid):
    p = _auth()
    if not p: return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    data = request.get_json() or {}
    try:
        amount = float(data.get('amount', 0))
    except (TypeError, ValueError):
        return jsonify({'error': 'invalid_amount'}), 400
    if amount <= 0: return jsonify({'error': 'invalid_amount'}), 400
    name = (data.get('name') or '').strip()
    if not name: return jsonify({'error': 'name_required'}), 400
    month = data.get('month') or date.today().strftime('%Y-%m')
    conn = get_conn(); cur = conn.cursor()
    try:
        if not _wallet_ok(cur, wid, uid):
            return jsonify({'error': 'forbidden'}), 403
        cur.execute("""
            INSERT INTO budgets (wallet_id, user_id, category_id, name, amount, month, alert_pct)
            VALUES (?,?,?,?,?,?,?)
        """, (wid, uid, data.get('category_id') or None, name, amount,
              month, int(data.get('alert_pct', 80))))
        conn.commit()
        return jsonify({'id': cur.lastrowid}), 201
    finally:
        cur.close(); conn.close()


@v2_bp.route('/api/budgets/<int:bid>', methods=['DELETE'])
def delete_budget(bid):
    p = _auth()
    if not p: return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("SELECT user_id FROM budgets WHERE id=?", (bid,))
        b = cur.fetchone()
        if not b: return jsonify({'error': 'not_found'}), 404
        if b[0] != uid: return jsonify({'error': 'forbidden'}), 403
        cur.execute("DELETE FROM budgets WHERE id=?", (bid,))
        conn.commit()
        return jsonify({'ok': True})
    finally:
        cur.close(); conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════════════════════
@v2_bp.route('/api/notifications', methods=['GET'])
def get_notifications():
    p = _auth()
    if not p: return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, type, title, body, link, read, created_at
            FROM notifications WHERE user_id=?
            ORDER BY created_at DESC LIMIT 50
        """, (uid,))
        rows = cur.fetchall()
        unread = sum(1 for r in rows if not r[5])
        return jsonify({
            'notifications': [{'id':r[0],'type':r[1],'title':r[2],'body':r[3],
                               'link':r[4],'read':bool(r[5]),'created_at':r[6]}
                              for r in rows],
            'unread': unread
        })
    finally:
        cur.close(); conn.close()


@v2_bp.route('/api/notifications/read', methods=['POST'])
def mark_notifs_read():
    p = _auth()
    if not p: return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    data = request.get_json() or {}
    conn = get_conn(); cur = conn.cursor()
    try:
        ids = data.get('ids')
        if ids:
            placeholders = ','.join('?' * len(ids))
            cur.execute(f"UPDATE notifications SET read=1 WHERE user_id=? AND id IN ({placeholders})",
                        [uid] + ids)
        else:
            cur.execute("UPDATE notifications SET read=1 WHERE user_id=?", (uid,))
        conn.commit()
        return jsonify({'ok': True})
    finally:
        cur.close(); conn.close()


@v2_bp.route('/api/notifications/<int:nid>', methods=['DELETE'])
def delete_notif(nid):
    p = _auth()
    if not p: return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    conn = get_conn(); cur = conn.cursor()
    try:
        cur.execute("DELETE FROM notifications WHERE id=? AND user_id=?", (nid, uid))
        conn.commit()
        return jsonify({'ok': True})
    finally:
        cur.close(); conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORT PDF (génération HTML → PDF via navigateur si reportlab absent)
# ═══════════════════════════════════════════════════════════════════════════════
@v2_bp.route('/api/wallets/<int:wid>/export/pdf', methods=['GET'])
def export_pdf(wid):
    p = _auth()
    if not p: return jsonify({'error': 'unauthorized'}), 401
    uid = _uid(p)
    conn = get_conn(); cur = conn.cursor()
    try:
        if not _wallet_ok(cur, wid, uid):
            return jsonify({'error': 'forbidden'}), 403
        cur.execute("SELECT name, currency FROM wallets WHERE id=?", (wid,))
        w = cur.fetchone()
        if not w: return jsonify({'error': 'not_found'}), 404
        wname, currency = w
        month = request.args.get('month', date.today().strftime('%Y-%m'))

        cur.execute("""
            SELECT t.date, t.label, t.type, t.amount,
                   COALESCE(c.icon,'') || ' ' || COALESCE(c.name,'Sans catégorie') as cat,
                   t.note, COALESCE(u.display_name, u.login, u.email,'') as author
            FROM transactions t
            LEFT JOIN categories c ON c.id=t.category_id
            LEFT JOIN users u ON u.id=t.user_id
            WHERE t.wallet_id=? AND strftime('%Y-%m', t.date)=?
            ORDER BY t.date DESC
        """, (wid, month))
        txs = cur.fetchall()

        cur.execute("""
            SELECT COALESCE(SUM(CASE WHEN type='income' THEN amount ELSE 0 END),0),
                   COALESCE(SUM(CASE WHEN type='expense' THEN amount ELSE 0 END),0)
            FROM transactions WHERE wallet_id=? AND strftime('%Y-%m', date)=?
        """, (wid, month))
        totals = cur.fetchone()
        income, expense = round(totals[0],2), round(totals[1],2)
        balance = round(income - expense, 2)
        sym = {'EUR':'€','USD':'$','GBP':'£','CHF':'₣'}.get(currency, currency)

        # Générer HTML imprimable (le navigateur fait le PDF via Ctrl+P)
        rows_html = ''.join(f"""
            <tr class="{'income' if t[2]=='income' else 'expense'}">
                <td>{t[0]}</td>
                <td>{t[1]}</td>
                <td>{t[4]}</td>
                <td class="amount">{'+'if t[2]=='income' else '-'}{t[3]:.2f} {sym}</td>
                <td>{t[5] or ''}</td>
                <td>{t[6]}</td>
            </tr>
        """ for t in txs)

        html = f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8">
<title>Rapport {wname} — {month}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Segoe UI',sans-serif;color:#1e293b;padding:32px;font-size:13px}}
  h1{{font-size:24px;font-weight:800;color:#6366f1;margin-bottom:4px}}
  h2{{font-size:14px;color:#64748b;font-weight:400;margin-bottom:24px}}
  .stats{{display:flex;gap:20px;margin-bottom:28px}}
  .stat{{background:#f8fafc;border:1px solid #e2e8f0;border-radius:10px;padding:16px 24px;flex:1}}
  .stat-label{{font-size:11px;text-transform:uppercase;color:#94a3b8;font-weight:600;margin-bottom:4px}}
  .stat-val{{font-size:22px;font-weight:800}}
  .stat-val.green{{color:#22c55e}}.stat-val.red{{color:#ef4444}}.stat-val.blue{{color:#6366f1}}
  table{{width:100%;border-collapse:collapse}}
  thead tr{{background:#f1f5f9}}
  th{{padding:10px 12px;text-align:left;font-size:11px;text-transform:uppercase;color:#64748b;font-weight:600;border-bottom:2px solid #e2e8f0}}
  td{{padding:10px 12px;border-bottom:1px solid #f1f5f9;vertical-align:middle}}
  tr.income td.amount{{color:#22c55e;font-weight:700}}
  tr.expense td.amount{{color:#ef4444;font-weight:700}}
  td.amount{{font-weight:600;white-space:nowrap}}
  .footer{{margin-top:24px;text-align:center;font-size:11px;color:#94a3b8}}
  @media print{{body{{padding:16px}}.no-print{{display:none}}}}
</style>
</head><body>
<div class="no-print" style="margin-bottom:20px">
  <button onclick="window.print()" style="background:#6366f1;color:#fff;border:none;padding:10px 20px;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer">🖨️ Imprimer / Enregistrer en PDF</button>
</div>
<h1>💳 {wname}</h1>
<h2>Rapport financier — {month}</h2>
<div class="stats">
  <div class="stat"><div class="stat-label">Revenus</div><div class="stat-val green">+{income:.2f} {sym}</div></div>
  <div class="stat"><div class="stat-label">Dépenses</div><div class="stat-val red">-{expense:.2f} {sym}</div></div>
  <div class="stat"><div class="stat-label">Solde du mois</div><div class="stat-val blue">{'+' if balance>=0 else ''}{balance:.2f} {sym}</div></div>
  <div class="stat"><div class="stat-label">Transactions</div><div class="stat-val">{len(txs)}</div></div>
</div>
<table>
  <thead><tr>
    <th>Date</th><th>Libellé</th><th>Catégorie</th><th>Montant</th><th>Note</th><th>Auteur</th>
  </tr></thead>
  <tbody>{rows_html if txs else '<tr><td colspan="6" style="text-align:center;padding:40px;color:#94a3b8">Aucune transaction ce mois</td></tr>'}</tbody>
</table>
<div class="footer">Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')} — FinanceApp</div>
</body></html>"""

        return Response(html, mimetype='text/html; charset=utf-8')
    finally:
        cur.close(); conn.close()
