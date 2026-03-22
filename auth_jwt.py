# auth_jwt.py
import jwt
from flask import request
from db import get_conn
import config

JWT_SECRET = getattr(config, "JWT_SECRET", "change_this_secret")

def get_user_from_jwt():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload.get("user_id")
    except Exception:
        return None

def is_admin_from_jwt():
    user_id = get_user_from_jwt()
    if not user_id:
        return False
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute("SELECT role FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        return bool(row and row[0] == "admin")
    finally:
        cur.close(); conn.close()