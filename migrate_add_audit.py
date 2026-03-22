# migrate_add_audit.py
import sqlite3, pathlib
db = pathlib.Path("data") / "data.db"
conn = sqlite3.connect(db.as_posix())
cur = conn.cursor()

# SQL à exécuter
cur.execute("""
CREATE TABLE IF NOT EXISTS email_change_audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  old_email TEXT,
  new_email TEXT,
  changed_by INTEGER NOT NULL,
  changed_at TEXT NOT NULL
)
""")

cur.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_user ON email_change_audit(user_id)")

conn.commit()
print('Migration exécutée : table et index créés si nécessaire.')
conn.close()
