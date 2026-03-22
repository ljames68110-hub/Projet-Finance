# setup_railway.py — Crée le premier compte admin sur la DB Railway
# Exécute ce script UNE SEULE FOIS après le premier déploiement
import sqlite3, bcrypt, pathlib, os, config

db = pathlib.Path(config.DB_PATH)
print(f"DB : {db.as_posix()}")

conn = sqlite3.connect(db.as_posix())
cur = conn.cursor()

# Données à personnaliser
users_to_create = [
    {
        "login":    "Yoann",
        "email":    "l.yoann68@hotmail.fr",
        "password": "Lk@09112004",   # ← ton vrai mot de passe
        "role":     "admin",
        "name":     "Yoann"
    },
    {
        "login":    "Linda",
        "email":    "Lynda_2207@hotmail.fr",
        "password": "Bb050925",  # ← à changer
        "role":     "user",
        "name":     "Linda"
    },
]

for u in users_to_create:
    pw_hash = bcrypt.hashpw(u["password"].encode(), bcrypt.gensalt()).decode()
    try:
        cur.execute("""
            INSERT OR IGNORE INTO users (login, email, password_hash, role, name, created_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
        """, (u["login"], u["email"], pw_hash, u["role"], u["name"]))
        if cur.rowcount:
            print(f"✅ Créé : {u['login']} ({u['role']})")
        else:
            print(f"⚠️  Existe déjà : {u['login']}")
    except Exception as e:
        print(f"❌ Erreur pour {u['login']} : {e}")

conn.commit()
conn.close()
print("\nTerminé ! Tu peux maintenant te connecter sur Railway.")
