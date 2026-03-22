# init_db.py
import sqlite3
from pathlib import Path

db_path = Path("data") / "data.db"
db_path.parent.mkdir(exist_ok=True)

conn = sqlite3.connect(db_path.as_posix())
cur = conn.cursor()
cur.execute("PRAGMA journal_mode=WAL;")
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()
conn.close()
print("DB initialisée:", db_path)