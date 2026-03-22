# migrate_add_email_verified.py
import sqlite3, pathlib
db = pathlib.Path("data") / "data.db"
conn = sqlite3.connect(db.as_posix())
cur = conn.cursor()
try:
    cur.execute("ALTER TABLE users ADD COLUMN email_verified INTEGER DEFAULT 0")
    print("Colonne email_verified ajoutée")
except Exception as e:
    print("email_verified existe ou erreur:", e)
conn.commit()
conn.close()
