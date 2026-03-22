import jwt
import datetime
import os

JWT_SECRET = os.environ.get("JWT_SECRET", "change_me")
JWT_ALGO = "HS256"
JWT_EXP_MIN = 60

def create_token(user):
    payload = {
        "sub": str(user["id"]),
        "email": user["email"],
        "role": user["role"],
        "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=JWT_EXP_MIN)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

def verify_token(token):
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except Exception:
        return None