import sqlite3
tests = ["Yoann", "yoann", "l.yoann68@hotmail.fr"]
conn = sqlite3.connect("app.db")
cur = conn.cursor()
print("AUTH CHECK")
for t in tests:
    cur.execute("SELECT id,email,login,role,created_at FROM users WHERE email = ? COLLATE NOCASE", (t,))
    row = cur.fetchone()
    if not row:
        cur.execute("SELECT id,email,login,role,created_at FROM users WHERE login = ? COLLATE NOCASE", (t,))
        row = cur.fetchone()
    if row:
        print("FOUND for '{}': {} | {} | {} | {}".format(t, row[0], row[1], row[3], row[4]))
    else:
        print("NOT FOUND for '{}'".format(t))
conn.close()
