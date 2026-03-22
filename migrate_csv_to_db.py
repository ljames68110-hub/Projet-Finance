# migrate_csv_to-db.py  (remplace entièrement le contenu existant)
import csv
from pathlib import Path
from db import ensure_db, create_user_with_password

CSV_PATH = Path("Utilisateurs.csv")
ensure_db()

def normalize_email(e: str, login: str) -> str:
    if not e or not e.strip():
        return f"{login.lower()}@local.invalid"
    return e.replace(",", ".").strip()

with CSV_PATH.open(encoding="utf-8-sig") as f:
    reader = csv.DictReader(f, delimiter=';')
    for row in reader:
        login = (row.get("Login") or "").strip()
        password = (row.get("Password") or "").strip()
        email_raw = row.get("Email") or ""
        status = (row.get("Status") or "").strip()
        if not login:
            print(f"Skip (login manquant) : {row}")
            continue
        email = normalize_email(email_raw, login)
        pwd = password if password else "changeme"
        uid = create_user_with_password(login, email, pwd, status)
        print(f"Importé: {login} (email: {email}, status: {status}) -> id {uid}")