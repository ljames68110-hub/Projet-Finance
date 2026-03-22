# export_invalid_emails.py
import sqlite3, pathlib, csv
db = pathlib.Path("data") / "data.db"
conn = sqlite3.connect(db.as_posix())
cur = conn.cursor()
cur.execute("SELECT id, name, email, status FROM users WHERE email LIKE '%@local.invalid'")
rows = cur.fetchall()
with open("invalid_emails.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f, delimiter=';')
    w.writerow(["id","name","email","status"])
    for r in rows:
        w.writerow(r)
for r in rows:
    print(r)
conn.close()
