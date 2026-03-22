from flask import Flask, request, jsonify
from auth import authenticate
from jwt_utils import create_token, verify_token

app = Flask(__name__)

@app.route("/", methods=["GET"])
def root():
    return "OK", 200

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json(force=True)
    identifier = (data.get("identifier") or "").strip()
    password = data.get("password") or ""
    if not identifier or not password:
        return jsonify({"status":"error","message":"identifier and password required"}), 400
    user, err = authenticate(identifier, password)
    if user:
        token = create_token(user)
        return jsonify({"status":"ok","user":user,"token":token}), 200
    return jsonify({"status":"error","message":err}), 401

@app.route("/protected", methods=["GET"])
def protected():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return jsonify({"status":"error","message":"missing token"}), 401
    token = auth.split(" ", 1)[1]
    payload = verify_token(token)
    if not payload:
        return jsonify({"status":"error","message":"invalid token"}), 401
    return jsonify({"status":"ok","payload":payload}), 200

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
