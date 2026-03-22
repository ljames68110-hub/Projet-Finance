# add_status_column.py
import sqlite3, pathlib
db = pathlib.Path("data") / "data.db"
db.parent.mkdir(parents=True, exist_ok=True)
conn = sqlite3.connect(db.as_posix())
cur = conn.cursor()
try:
    cur.execute("ALTER TABLE users ADD COLUMN status TEXT")
    conn.commit()
    print("Colonne status ajoutée.")
except sqlite3.OperationalError:
    print("La colonne status existe déjà ou modification impossible.")
finally:
    conn.close()
