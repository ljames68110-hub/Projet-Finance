# check_migration.py
import sqlite3, pathlib
db = pathlib.Path("data") / "data.db"
conn = sqlite3.connect(db.as_posix())
cur = conn.cursor()
cur.execute("SELECT type, name FROM sqlite_master WHERE type IN ('table','index') ORDER BY type, name")
for t, name in cur.fetchall():
    print(t, name)
conn.close()
