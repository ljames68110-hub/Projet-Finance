import sqlite3
conn = sqlite3.connect("app.db")
cur = conn.cursor()
cur.execute("SELECT id,email,role,created_at FROM users ORDER BY id")
rows = cur.fetchall()
print("USERS")
for r in rows:
    print(f"{r[0]} | {r[1]} | {r[2]} | {r[3]}")
conn.close()
