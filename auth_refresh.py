# auth_refresh.py
import os
import datetime
import uuid
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
import jwt
from werkzeug.security import check_password_hash

# Configuration
APP_SECRET = os.environ.get("APP_SECRET", "change_me_app")
JWT_SECRET = os.environ.get("JWT_SECRET", "change_me_access")
REFRESH_SECRET = os.environ.get("REFRESH_SECRET", "change_me_refresh")
ACCESS_EXP_MIN = int(os.environ.get("ACCESS_EXP_MIN", 15))
REFRESH_EXP_DAYS = int(os.environ.get("REFRESH_EXP_DAYS", 7))
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./refresh_tokens.db")

# Flask + DB
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# Models
class RefreshToken(db.Model):
    __tablename__ = "refresh_tokens"
    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(64), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    revoked = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)

    def is_expired(self):
        return datetime.datetime.utcnow() >= self.expires_at

# Dummy user store for example
USERS = {
    "Yoann": {
        "id": 1,
        "username": "Yoann",
        # Replace with a real hashed password in production
        "password_hash": "pbkdf2:sha256:150000$example$..."
    }
}

# Helpers
def create_access_token(user_id, email=None, role="user"):
    now = datetime.datetime.utcnow()
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + datetime.timedelta(minutes=ACCESS_EXP_MIN)).timestamp())
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def create_refresh_token(user_id):
    now = datetime.datetime.utcnow()
    jti = str(uuid.uuid4())
    payload = {
        "sub": str(user_id),
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int((now + datetime.timedelta(days=REFRESH_EXP_DAYS)).timestamp())
    }
    token = jwt.encode(payload, REFRESH_SECRET, algorithm="HS256")
    rt = RefreshToken(
        jti=jti,
        user_id=user_id,
        revoked=False,
        created_at=now,
        expires_at=now + datetime.timedelta(days=REFRESH_EXP_DAYS)
    )
    db.session.add(rt)
    db.session.commit()
    return token

def revoke_refresh_token_jti(jti):
    rt = RefreshToken.query.filter_by(jti=jti).first()
    if rt:
        rt.revoked = True
        db.session.commit()
        return True
    return False

def verify_refresh_token(token):
    try:
        payload = jwt.decode(token, REFRESH_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None, "expired"
    except Exception:
        return None, "invalid"

    jti = payload.get("jti")
    sub = payload.get("sub")
    if not jti or not sub:
        return None, "invalid"

    rt = RefreshToken.query.filter_by(jti=jti).first()
    if not rt:
        return None, "not_found"
    if rt.revoked:
        return None, "revoked"
    if rt.is_expired():
        return None, "expired_db"
    return payload, None

# Routes
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    identifier = data.get("identifier")
    password = data.get("password")
    if not identifier or not password:
        return jsonify({"status":"error","message":"missing credentials"}), 400

    user = USERS.get(identifier)
    if not user:
        return jsonify({"status":"error","message":"invalid credentials"}), 401

    # Replace with check_password_hash(user["password_hash"], password) in real app
    access = create_access_token(user_id=user["id"], email=f"{identifier.lower()}@example.com", role="admin")
    refresh = create_refresh_token(user_id=user["id"])
    return jsonify({"status":"ok","access_token": access, "refresh_token": refresh})

@app.route("/token/refresh", methods=["POST"])
def token_refresh():
    data = request.get_json() or {}
    refresh_token = data.get("refresh_token")
    if not refresh_token:
        return jsonify({"status":"error","message":"missing refresh token"}), 400

    payload, err = verify_refresh_token(refresh_token)
    if err:
        return jsonify({"status":"error","message": f"refresh token {err}"}), 401

    old_jti = payload["jti"]
    user_id = int(payload["sub"])

    revoke_refresh_token_jti(old_jti)

    new_access = create_access_token(user_id=user_id, email=None, role="user")
    new_refresh = create_refresh_token(user_id=user_id)

    return jsonify({"status":"ok","access_token": new_access, "refresh_token": new_refresh})

@app.route("/logout", methods=["POST"])
def logout():
    data = request.get_json() or {}
    refresh_token = data.get("refresh_token")
    if not refresh_token:
        return jsonify({"status":"error","message":"missing refresh token"}), 400

    try:
        payload = jwt.decode(refresh_token, REFRESH_SECRET, algorithms=["HS256"])
    except Exception:
        return jsonify({"status":"error","message":"invalid token"}), 400

    jti = payload.get("jti")
    if jti:
        revoke_refresh_token_jti(jti)
    return jsonify({"status":"ok","message":"logged out"})

@app.route("/protected", methods=["GET"])
def protected():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return jsonify({"status":"error","message":"missing token"}), 401
    token = auth.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return jsonify({"status":"error","message":"token expired"}), 401
    except Exception:
        return jsonify({"status":"error","message":"invalid token"}), 401
    return jsonify({"status":"ok","payload": payload})

# DB init helper (fixed: create tables inside app context)
def init_db():
    with app.app_context():
        db.create_all()

if __name__ == "__main__":
    init_db()
    app.run(port=5000)