# check_passwords.py
import sqlite3, pathlib
db = pathlib.Path("data") / "data.db"
conn = sqlite3.connect(db.as_posix())
cur = conn.cursor()
cur.execute("SELECT id, name, email, status, password_hash IS NOT NULL as has_pwd, LENGTH(password_hash) FROM users")
for r in cur.fetchall():
    print(r)
conn.close()