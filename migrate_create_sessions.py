# migrate_create_sessions.py
import sqlite3, pathlib
db = pathlib.Path("data") / "data.db"
conn = sqlite3.connect(db.as_posix())
cur = conn.cursor()
try:
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        session_token TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        valid INTEGER DEFAULT 1
    )
    """)
    conn.commit()
    print("Table sessions créée ou déjà existante")
except Exception as e:
    print("Erreur:", e)
finally:
    conn.close()
