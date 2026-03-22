# app_finance.py — Point d'entrée principal (remplace app.py)
from flask import Flask, request, jsonify, send_from_directory
from auth import authenticate
from jwt_utils import create_token, verify_token
from finance_routes import finance_bp
from admin_routes import admin_bp
from db import ensure_db
import os

app = Flask(__name__, static_folder='static', static_url_path='/static')

# Blueprints
app.register_blueprint(finance_bp)
app.register_blueprint(admin_bp)

# ── Fichiers statiques (PWA) ──────────────────────────────────────────────────
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_spa(path):
    static_dir = os.path.join(app.root_path, 'static')
    full = os.path.join(static_dir, path)
    if path and os.path.isfile(full):
        return send_from_directory(static_dir, path)
    return send_from_directory(static_dir, 'index.html')

# ── Auth ──────────────────────────────────────────────────────────────────────
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

if __name__ == '__main__':
    ensure_db()
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False, threaded=True)
