# print_audit.py
import sqlite3, pathlib
db = pathlib.Path("data") / "data.db"
conn = sqlite3.connect(db.as_posix())
cur = conn.cursor()
cur.execute("SELECT id, user_id, old_email, new_email, changed_by, changed_at FROM email_change_audit ORDER BY id DESC LIMIT 5")
for r in cur.fetchall():
    print(r)
conn.close()
