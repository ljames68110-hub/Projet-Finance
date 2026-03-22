# migrate_add_role.py
import sqlite3, pathlib
db = pathlib.Path("data") / "data.db"
conn = sqlite3.connect(db.as_posix())
cur = conn.cursor()
try:
    cur.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
    print("role ajoutée")
except Exception as e:
    print("role existe ou erreur:", e)
conn.commit()
conn.close()
