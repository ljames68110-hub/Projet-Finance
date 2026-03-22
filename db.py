# db.py
import sqlite3
from pathlib import Path
from typing import List, Tuple, Optional
import config

DB_FILE = Path(config.DB_PATH)

def _get_sqlite_module():
    if config.USE_SQLCIPHER:
        from pysqlcipher3 import dbapi2 as sqlite3_mod
        return sqlite3_mod
    return sqlite3

def ensure_db():
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    sqlite_mod = _get_sqlite_module()
    conn = sqlite_mod.connect(DB_FILE.as_posix())
    try:
        cur = conn.cursor()
        if config.USE_SQLCIPHER:
            cur.execute(f"PRAGMA key = '{config.SQLCIPHER_KEY}';")
        cur.execute("PRAGMA journal_mode=WAL;")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            password_hash BLOB,
            status TEXT
        )
        """)
        conn.commit()
    finally:
        conn.close()

def get_conn():
    sqlite_mod = _get_sqlite_module()
    conn = sqlite_mod.connect(DB_FILE.as_posix(), detect_types=sqlite3.PARSE_DECLTYPES)
    if config.USE_SQLCIPHER:
        cur = conn.cursor()
        cur.execute(f"PRAGMA key = '{config.SQLCIPHER_KEY}';")
        cur.close()
    return conn

# fonctions liées aux mots de passe (utilise utils_password)
from utils_password import hash_password, check_password

def create_user_with_password(name: str, email: str, plain_password: str, status: str = "") -> Optional[int]:
    """
    Insère un utilisateur ou met à jour name, password_hash et status si l'email existe.
    Retourne l'id de l'utilisateur.
    """
    pwd_hash = hash_password(plain_password) if plain_password is not None else None
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE email = ?", (email,))
        row = cur.fetchone()
        if row:
            user_id = row[0]
            cur.execute(
                "UPDATE users SET name = ?, password_hash = ?, status = ? WHERE id = ?",
                (name, pwd_hash, status, user_id)
            )
            conn.commit()
            return user_id
        cur.execute(
            "INSERT INTO users (name, email, password_hash, status) VALUES (?, ?, ?, ?)",
            (name, email, pwd_hash, status)
        )
        conn.commit()
        return cur.lastrowid

def authenticate_user(email: str, plain_password: str) -> Optional[int]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, password_hash FROM users WHERE email = ?", (email,))
        row = cur.fetchone()
        if not row:
            return None
        user_id, stored_hash = row[0], row[1]
        if check_password(plain_password, stored_hash):
            return user_id
        return None

def upsert_user(name: str, email: str) -> int:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE email = ?", (email,))
        row = cur.fetchone()
        if row:
            user_id = row[0]
            cur.execute("UPDATE users SET name = ? WHERE id = ?", (name, user_id))
            conn.commit()
            return user_id
        cur.execute("INSERT INTO users (name, email) VALUES (?, ?)", (name, email))
        conn.commit()
        return cur.lastrowid

def delete_user_by_email(email: str) -> int:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE email = ?", (email,))
        conn.commit()
        return cur.rowcount

def list_users() -> List[Tuple]:
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name, email, status, created_at FROM users")
        return cur.fetchall()