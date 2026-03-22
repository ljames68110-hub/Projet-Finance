# revocation_redis.py
import os
import datetime
import uuid
import jwt
from flask import Flask, request, jsonify
import redis

app = Flask(__name__)

REFRESH_SECRET = os.environ.get("REFRESH_SECRET", "change_me_refresh")
JWT_SECRET = os.environ.get("JWT_SECRET", "change_me_access")
ACCESS_EXP_MIN = int(os.environ.get("ACCESS_EXP_MIN", 15))
REFRESH_EXP_DAYS = int(os.environ.get("REFRESH_EXP_DAYS", 7))

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
r = redis.from_url(REDIS_URL)

def store_jti_in_redis(jti, user_id, ttl_seconds):
    key = f"refresh_jti:{jti}"
    r.hset(key, mapping={"user_id": user_id})
    r.expire(key, ttl_seconds)

def revoke_jti_in_redis(jti):
    key = f"refresh_jti:{jti}"
    r.hset(key, "revoked", "1")

def is_jti_revoked(jti):
    key = f"refresh_jti:{jti}"
    if not r.exists(key):
        return True
    return r.hget(key, "revoked") == b"1"

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
    ttl = REFRESH_EXP_DAYS * 24 * 3600
    store_jti_in_redis(jti, user_id, ttl)
    return token

def verify_refresh_token(token):
    try:
        payload = jwt.decode(token, REFRESH_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None, "expired"
    except Exception:
        return None, "invalid"
    jti = payload.get("jti")
    if not jti:
        return None, "invalid"
    if is_jti_revoked(jti):
        return None, "revoked_or_missing"
    return payload, None

# Add endpoints similar to auth_refresh.py using these helpers
