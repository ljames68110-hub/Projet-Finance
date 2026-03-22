import sqlite3
conn = sqlite3.connect("app.db")
cur = conn.cursor()
cur.execute("SELECT id, email, password_hash IS NOT NULL FROM users WHERE email = ?", ("l.yoann68@hotmail.fr",))
print(cur.fetchone())
conn.close()
