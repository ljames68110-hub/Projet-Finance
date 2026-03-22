import sqlite3
conn = sqlite3.connect("app.db")
c = conn.cursor()
c.executescript("""
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT UNIQUE NOT NULL,
  role TEXT NOT NULL DEFAULT 'user',
  created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  old_email TEXT,
  new_email TEXT,
  changed_by INTEGER,
  changed_at TEXT DEFAULT (datetime('now'))
);
""")
conn.commit()
conn.close()
print("tables_created")
