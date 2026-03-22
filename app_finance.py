# app_finance.py — Compatible Railway + local
from flask import Flask, request, jsonify, send_from_directory
from auth import authenticate
from jwt_utils import create_token, verify_token
from finance_routes import finance_bp
from routes_v2 import v2_bp
from routes_v3 import v3_bp
from admin_routes import admin_bp
from db import ensure_db
import os
from pathlib import Path

# ── Charger .env si présent (local seulement) ─────────────────────────────────
def _load_dotenv():
    env_file = Path(__file__).parent / '.env'
    if not env_file.exists():
        return
    with open(env_file, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, val = line.partition('=')
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val
    print("✅ Fichier .env chargé")

_load_dotenv()

# ── DB path : Railway utilise un volume persistant ────────────────────────────
# Sur Railway : DB_PATH=/data/app.db (volume monté)
# En local    : DB_PATH=app.db
if not os.environ.get('DB_PATH'):
    data_dir = Path('/data') if Path('/data').exists() else Path('.')
    os.environ['DB_PATH'] = str(data_dir / 'app.db')

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.register_blueprint(finance_bp)
app.register_blueprint(v2_bp)
app.register_blueprint(v3_bp)
app.register_blueprint(admin_bp)

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
    smtp = os.getenv('SMTP_HOST','')
    print(f"   SMTP   : {'✅ ' + os.getenv('SMTP_USER','') if smtp else '❌ non configuré'}")
    print(f"   Ctrl+C pour arrêter\n")
    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)

# Point d'entrée gunicorn (Railway)
# Migrations automatiques au démarrage gunicorn
try:
    ensure_db()
except Exception:
    pass
