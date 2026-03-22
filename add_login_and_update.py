import sqlite3, csv, os, sys
fn = "Utilisateurs.csv"
if not os.path.exists(fn):
    print("error: file Utilisateurs.csv not found")
    sys.exit(1)

conn = sqlite3.connect("app.db")
cur = conn.cursor()

# Add login column if missing
cols = [r[1] for r in cur.execute("PRAGMA table_info(users)").fetchall()]
if "login" not in cols:
    cur.execute("ALTER TABLE users ADD COLUMN login TEXT")
    print("added_column: login")

inserted = []
updated = []
errors = []

with open(fn, encoding="utf-8") as f:
    reader = csv.DictReader(f, delimiter=';')
    for row in reader:
        login = (row.get("Login") or "").strip()
        raw_email = (row.get("Email") or "").strip()
        email = raw_email.replace(",", ".").strip()
        if email == "":
            email = f"{login.lower() or 'user'}@local"
        role = (row.get("Role") or "User").strip().lower()
        role = "admin" if role == "admin" else "user"
        try:
            cur.execute("SELECT id FROM users WHERE email = ?", (email,))
            r = cur.fetchone()
            if r:
                cur.execute("UPDATE users SET login = ?, role = ? WHERE id = ?", (login, role, r[0]))
                updated.append((login, email, role))
            else:
                cur.execute("INSERT INTO users(email, role, created_at, login) VALUES(?, ?, datetime('now'), ?)", (email, role, login))
                inserted.append((login, email, role))
        except Exception as e:
            errors.append((login, email, str(e)))

conn.commit()

print("RESULTS")
print("Added column login" if "login" in cols and False else "")
print("Inserted:", len(inserted))
for it in inserted:
    print(" +", it[0], "|", it[1], "|", it[2])
print("Updated:", len(updated))
for it in updated:
    print(" *", it[0], "|", it[1], "|", it[2])
print("Errors:", len(errors))
for it in errors:
    print(" !", it[0], "|", it[1], "|", it[2])

conn.close()
