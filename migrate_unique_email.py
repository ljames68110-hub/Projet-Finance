# migrate_unique_email.py
import sqlite3, pathlib
db = pathlib.Path("data") / "data.db"
conn = sqlite3.connect(db.as_posix())
cur = conn.cursor()
cur.execute("SELECT email, COUNT(*) FROM users GROUP BY email HAVING COUNT(*)>1")
dups = cur.fetchall()
if dups:
    print("Doublons détectés, corrigez-les avant d'ajouter l'index:")
    for email, cnt in dups:
        print(email, cnt)
else:
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique ON users(email)")
    conn.commit()
    print("Index UNIQUE créé")
conn.close()
