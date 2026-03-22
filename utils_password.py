# utils_password.py
import bcrypt

def hash_password(plain: str) -> bytes:
    return bcrypt.hashpw(plain.encode('utf-8'), bcrypt.gensalt())

def check_password(plain: str, hashed: bytes) -> bool:
    if hashed is None:
        return False
    return bcrypt.checkpw(plain.encode('utf-8'), hashed)