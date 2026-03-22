# add_password_column.py
import sqlite3
from pathlib import Path

db = Path("data") / "data.db"
db.parent.mkdir(exist_ok=True)

conn = sqlite3.connect(db.as_posix())
cur = conn.cursor()
try:
    cur.execute("ALTER TABLE users ADD COLUMN password_hash BLOB")
    conn.commit()
    print("Colonne password_hash ajoutée.")
except sqlite3.OperationalError:
    print("La colonne existe déjà ou modification impossible.")
finally:
    conn.close()