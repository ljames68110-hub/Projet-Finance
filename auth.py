# auth.py
import sqlite3
import bcrypt
from typing import Optional, Tuple, Dict, Any

DB = "app.db"

def _connect():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def find_user(identifier: str) -> Optional[sqlite3.Row]:
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, email, login, role, created_at, password_hash
            FROM users
            WHERE email = ? COLLATE NOCASE OR login = ? COLLATE NOCASE
            LIMIT 1
            """,
            (identifier, identifier),
        )
        return cur.fetchone()

def authenticate(identifier: str, password: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    row = find_user(identifier)
    if not row:
        return None, "Utilisateur non trouvé"
    stored_hash = row["password_hash"]
    if not stored_hash:
        return None, "Mot de passe non défini pour cet utilisateur"
    try:
        if bcrypt.checkpw(password.encode(), stored_hash.encode()):
            user = {
                "id": row["id"],
                "email": row["email"],
                "login": row["login"],
                "role": row["role"],
                "created_at": row["created_at"],
            }
            return user, None
        else:
            return None, "Mot de passe incorrect"
    except Exception as e:
        return None, f"Erreur lors de la vérification du mot de passe: {e}"

def set_password_for_email(email: str, plain_password: str) -> bool:
    hashed = bcrypt.hashpw(plain_password.encode(), bcrypt.gensalt()).decode()
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE users SET password_hash = ? WHERE email = ?", (hashed, email))
        conn.commit()
        return cur.rowcount > 0

def create_user(email: str, login: str, role: str = "user", plain_password: Optional[str] = None) -> Tuple[bool, str]:
    with _connect() as conn:
        cur = conn.cursor()
        try:
            pw_hash = None
            if plain_password:
                pw_hash = bcrypt.hashpw(plain_password.encode(), bcrypt.gensalt()).decode()
            cur.execute(
                "INSERT INTO users(email, role, created_at, login, password_hash) VALUES(?, ?, datetime('now'), ?, ?)",
                (email, role, login, pw_hash),
            )
            conn.commit()
            return True, "user_created"
        except sqlite3.IntegrityError as e:
            return False, f"integrity_error: {e}"
        except Exception as e:
            return False, f"error: {e}"

if __name__ == "__main__":
    tests = [
        ("Yoann", "TonMotDePasseSecurise"),
        ("l.yoann68@hotmail.fr", "TonMotDePasseSecurise"),
        ("yoann", "TonMotDePasseSecurise"),
        ("nonexistent", "x"),
    ]
    for ident, pw in tests:
        user, err = authenticate(ident, pw)
        if user:
            print("AUTH OK for", ident, "->", user)
        else:
            print("AUTH FAIL for", ident, ":", err)
