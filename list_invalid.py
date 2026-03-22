# list_invalid.py
import sqlite3, pathlib
db = pathlib.Path("data") / "data.db"
conn = sqlite3.connect(db.as_posix())
cur = conn.cursor()
cur.execute("SELECT id, name, email, status FROM users WHERE email LIKE '%@local.invalid'")
rows = cur.fetchall()
for r in rows:
    print(r)
conn.close()
