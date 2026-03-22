import sqlite3, csv, sys, os
fn = "Utilisateurs.csv"
if not os.path.exists(fn):
    print("error: file Utilisateurs.csv not found")
    sys.exit(1)

conn = sqlite3.connect("app.db")
cur = conn.cursor()

inserted = []
skipped = []
errors = []

with open(fn, encoding="utf-8") as f:
    reader = csv.DictReader(f, delimiter=';')
    for row in reader:
        login = (row.get("Login") or "").strip()
        role = (row.get("Role") or "User").strip().lower()
        raw_email = (row.get("Email") or "").strip()
        email = raw_email.replace(",", ".").strip()
        if email == "":
            email = f"{login.lower() or 'user'}@local"
        if role not in ("admin", "user"):
            role = "user"
        try:
            cur.execute("INSERT OR IGNORE INTO users(email, role, created_at) VALUES (?, ?, datetime('now'))", (email, "admin" if role=="admin" else "user"))
            if cur.rowcount:
                inserted.append((login, email, role))
            else:
                skipped.append((login, email, role))
        except Exception as e:
            errors.append((login, email, str(e)))

conn.commit()

print("RESULTS")
print("Inserted:", len(inserted))
for it in inserted:
    print(" +", it[0], "|", it[1], "|", it[2])
print("Skipped (already existed):", len(skipped))
for it in skipped:
    print(" -", it[0], "|", it[1], "|", it[2])
print("Errors:", len(errors))
for it in errors:
    print(" !", it[0], "|", it[1], "|", it[2])

conn.close()
