# migrate_v4.py — Revenus fixes + rappels CAF
import sqlite3, pathlib, config

db = pathlib.Path(config.DB_PATH)
conn = sqlite3.connect(db.as_posix())
cur = conn.cursor()
cur.execute("PRAGMA journal_mode=WAL;")
print(f"Migration v4 sur : {db.as_posix()}")

# ── Revenus fixes ─────────────────────────────────────────────────────────────
cur.execute("""
CREATE TABLE IF NOT EXISTS fixed_incomes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_id     INTEGER NOT NULL,
    user_id       INTEGER NOT NULL,
    label         TEXT    NOT NULL,
    amount        REAL,
    category_id   INTEGER,
    frequency     TEXT    DEFAULT 'monthly',
    next_date     TEXT    NOT NULL,
    auto_insert   INTEGER DEFAULT 0,
    note          TEXT    DEFAULT '',
    active        INTEGER DEFAULT 1,
    income_type   TEXT    DEFAULT 'regular',
    created_at    TEXT    DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (wallet_id)   REFERENCES wallets(id),
    FOREIGN KEY (user_id)     REFERENCES users(id),
    FOREIGN KEY (category_id) REFERENCES categories(id)
)
""")

# ── Rappels CAF / revenus variables ──────────────────────────────────────────
cur.execute("""
CREATE TABLE IF NOT EXISTS income_reminders (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_id     INTEGER NOT NULL,
    user_id       INTEGER NOT NULL,
    label         TEXT    NOT NULL,
    description   TEXT    DEFAULT '',
    frequency     TEXT    DEFAULT 'quarterly',
    day_of_period INTEGER DEFAULT 5,
    last_asked    TEXT,
    last_amount   REAL,
    active        INTEGER DEFAULT 1,
    created_at    TEXT    DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (wallet_id) REFERENCES wallets(id),
    FOREIGN KEY (user_id)   REFERENCES users(id)
)
""")

# ── Index ─────────────────────────────────────────────────────────────────────
cur.execute("CREATE INDEX IF NOT EXISTS idx_fi_wallet   ON fixed_incomes(wallet_id)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_fi_next     ON fixed_incomes(next_date)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_ir_wallet   ON income_reminders(wallet_id)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_ir_active   ON income_reminders(active)")

# ── Rappels CAF par défaut (insérés une seule fois) ───────────────────────────
# Ces rappels sont créés globalement, pas par utilisateur
# Chaque user peut en créer dans ses portefeuilles

conn.commit()
conn.close()
print("✅ Migration v4 terminée")
