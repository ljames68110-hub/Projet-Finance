import sqlite3
conn = sqlite3.connect("app.db")
cur = conn.cursor()
cols = [r[1] for r in cur.execute("PRAGMA table_info(users)").fetchall()]
if "password_hash" not in cols:
    cur.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
    print("added_column: password_hash")
cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_login_nocase ON users(LOWER(login))")
print("index_created: idx_users_login_nocase")
conn.commit()
conn.close()
