# add_and_mark_must_reset.py
import sqlite3, pathlib
db = pathlib.Path("data") / "data.db"
conn = sqlite3.connect(db.as_posix())
cur = conn.cursor()
# ajouter la colonne must_reset si elle n'existe pas
try:
    cur.execute("ALTER TABLE users ADD COLUMN must_reset INTEGER DEFAULT 0")
    print("Colonne must_reset ajoutée.")
except Exception as e:
    print("Colonne must_reset déjà présente ou erreur:", e)
# marquer les comptes à réinitialiser (sans modifier les mots de passe)
cur.execute("UPDATE users SET must_reset=1 WHERE email LIKE '%@local.invalid' OR password_hash IS NULL OR LENGTH(password_hash)=0")
conn.commit()
print("Comptes marqués pour reset:", cur.rowcount)
conn.close()
