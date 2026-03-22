# app_finance.py — Compatible Railway + local
from flask import Flask, request, jsonify, send_from_directory, send_file
from auth import authenticate
from jwt_utils import create_token, verify_token
from finance_routes import finance_bp
from routes_v2 import v2_bp
from routes_v3 import v3_bp
from admin_routes import admin_bp
from db import ensure_db
import os, io, pathlib
from pathlib import Path

def _load_dotenv():
    env_file = Path(__file__).parent / '.env'
    if not env_file.exists(): return
    with open(env_file, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line: continue
            key, _, val = line.partition('=')
            key = key.strip(); val = val.strip().strip('"').strip("'")
            if key and key not in os.environ: os.environ[key] = val
    print("✅ Fichier .env chargé")

_load_dotenv()

if not os.environ.get('DB_PATH'):
    data_dir = Path('/data') if Path('/data').exists() else Path('.')
    os.environ['DB_PATH'] = str(data_dir / 'app.db')

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.register_blueprint(finance_bp)
app.register_blueprint(v2_bp)
app.register_blueprint(v3_bp)
app.register_blueprint(admin_bp)

# ── ENDPOINT TEMPORAIRE MIGRATION DB ─────────────────────────────────────────
@app.route('/admin/db/upload', methods=['GET', 'POST'])
def db_upload():
    secret = request.args.get('secret', '')
    jwt_secret = os.getenv('JWT_SECRET', '')
    if not jwt_secret or secret != jwt_secret:
        return 'forbidden', 403
    if request.method == 'GET':
        html = """<!DOCTYPE html>
<html><head><title>Upload DB</title><meta charset="UTF-8"></head>
<body style="font-family:sans-serif;padding:40px;background:#0f172a;color:#f1f5f9;max-width:500px;margin:0 auto">
<h2>📦 Migration DB vers Railway</h2>
<p style="color:#94a3b8;margin-bottom:24px">Selectionne ton fichier <strong>app.db</strong> local</p>
<form method="POST" enctype="multipart/form-data">
  <input type="file" name="db" accept=".db,.sqlite"
         style="display:block;margin-bottom:20px;color:#f1f5f9;font-size:14px">
  <button type="submit"
          style="background:#6366f1;color:#fff;border:none;padding:14px 28px;
                 border-radius:10px;font-size:16px;cursor:pointer;font-weight:700">
    ⬆ Uploader la DB
  </button>
</form>
</body></html>"""
        return html, 200, {'Content-Type': 'text/html; charset=utf-8'}
    # POST
    if 'db' not in request.files:
        return 'Aucun fichier', 400
    f = request.files['db']
    db_path = os.getenv('DB_PATH', 'app.db')
    pathlib.Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    f.save(db_path)
    return """<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family:sans-serif;padding:40px;background:#0f172a;color:#f1f5f9;text-align:center">
<h2 style="color:#22c55e">✅ Base de données migrée avec succès !</h2>
<p style="color:#94a3b8;margin:20px 0">Toutes tes données sont maintenant sur Railway.</p>
<a href="/" style="background:#6366f1;color:#fff;padding:14px 28px;border-radius:10px;
   text-decoration:none;font-weight:700;font-size:16px">🚀 Ouvrir FinanceApp</a>
</body></html>""", 200, {'Content-Type': 'text/html; charset=utf-8'}

# ── SPA ───────────────────────────────────────────────────────────────────────
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_spa(path):
    static_dir = os.path.join(app.root_path, 'static')
    full = os.path.join(static_dir, path)
    if path and os.path.isfile(full):
        return send_from_directory(static_dir, path)
    return send_from_directory(static_dir, 'index.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json(force=True) or {}
    identifier = (data.get('identifier') or '').strip()
    password   = data.get('password') or ''
    if not identifier or not password:
        return jsonify({'status': 'error', 'message': 'identifier and password required'}), 400
    user, err = authenticate(identifier, password)
    if user:
        token = create_token(user)
        return jsonify({'status': 'ok', 'user': user, 'token': token}), 200
    return jsonify({'status': 'error', 'message': err}), 401

@app.route('/protected', methods=['GET'])
def protected():
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return jsonify({'status': 'error', 'message': 'missing token'}), 401
    payload = verify_token(auth.split(' ', 1)[1])
    if not payload:
        return jsonify({'status': 'error', 'message': 'invalid token'}), 401
    return jsonify({'status': 'ok', 'payload': payload}), 200

# Point d'entrée local
if __name__ == '__main__':
    ensure_db()
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', '5000'))
    print(f"\n🚀 FinanceApp démarré sur http://{host}:{port}")
    print(f"   Local  : http://127.0.0.1:{port}")
    import socket
    try:
        ip = socket.gethostbyname(socket.gethostname())
        print(f"   Réseau : http://{ip}:{port}")
    except Exception:
        pass
    print(f"   Ctrl+C pour arrêter\n")
    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)

try:
    ensure_db()
except Exception:
    pass
