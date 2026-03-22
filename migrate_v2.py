# migrate_v2.py — Migration v2 : dettes, budgets, notifications, profil
import sqlite3, pathlib, config

db = pathlib.Path(config.DB_PATH)
conn = sqlite3.connect(db.as_posix())
cur = conn.cursor()
cur.execute("PRAGMA journal_mode=WAL;")
print(f"Migration v2 sur : {db.as_posix()}")

# ── Profil utilisateur ────────────────────────────────────────────────────────
for col, defn in [
    ("display_name", "TEXT DEFAULT ''"),
    ("avatar_color", "TEXT DEFAULT '#6366f1'"),
    ("phone",        "TEXT DEFAULT ''"),
    ("notify_email", "INTEGER DEFAULT 1"),
    ("notify_app",   "INTEGER DEFAULT 1"),
]:
    existing = [r[1] for r in cur.execute("PRAGMA table_info(users)").fetchall()]
    if col not in existing:
        cur.execute(f"ALTER TABLE users ADD COLUMN {col} {defn}")
        print(f"  users.{col} ajouté")

# ── Dettes / Remboursements ───────────────────────────────────────────────────
cur.execute("""
CREATE TABLE IF NOT EXISTS debts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_id    INTEGER NOT NULL,
    creditor_id  INTEGER NOT NULL,
    debtor_id    INTEGER,
    debtor_name  TEXT    DEFAULT '',
    amount       REAL    NOT NULL,
    description  TEXT    DEFAULT '',
    due_date     TEXT,
    status       TEXT    DEFAULT 'pending',
    paid_at      TEXT,
    created_at   TEXT    DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (wallet_id)   REFERENCES wallets(id),
    FOREIGN KEY (creditor_id) REFERENCES users(id)
)
""")

# ── Budgets mensuels ──────────────────────────────────────────────────────────
cur.execute("""
CREATE TABLE IF NOT EXISTS budgets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_id   INTEGER NOT NULL,
    user_id     INTEGER NOT NULL,
    category_id INTEGER,
    name        TEXT    NOT NULL,
    amount      REAL    NOT NULL,
    period      TEXT    DEFAULT 'monthly',
    month       TEXT    NOT NULL,
    alert_pct   INTEGER DEFAULT 80,
    created_at  TEXT    DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (wallet_id)   REFERENCES wallets(id),
    FOREIGN KEY (user_id)     REFERENCES users(id),
    FOREIGN KEY (category_id) REFERENCES categories(id)
)
""")

# ── Notifications in-app ──────────────────────────────────────────────────────
cur.execute("""
CREATE TABLE IF NOT EXISTS notifications (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    type       TEXT    NOT NULL,
    title      TEXT    NOT NULL,
    body       TEXT    DEFAULT '',
    link       TEXT    DEFAULT '',
    read       INTEGER DEFAULT 0,
    created_at TEXT    DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
""")

# ── Index ─────────────────────────────────────────────────────────────────────
for stmt in [
    "CREATE INDEX IF NOT EXISTS idx_debts_wallet    ON debts(wallet_id)",
    "CREATE INDEX IF NOT EXISTS idx_debts_creditor  ON debts(creditor_id)",
    "CREATE INDEX IF NOT EXISTS idx_debts_status    ON debts(status)",
    "CREATE INDEX IF NOT EXISTS idx_budgets_wallet  ON budgets(wallet_id)",
    "CREATE INDEX IF NOT EXISTS idx_budgets_month   ON budgets(month)",
    "CREATE INDEX IF NOT EXISTS idx_notif_user      ON notifications(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_notif_read      ON notifications(read)",
]:
    cur.execute(stmt)

conn.commit()
conn.close()
print("✅ Migration v2 terminée")
