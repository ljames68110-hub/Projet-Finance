# migrate_v3.py — Dépenses fixes + compte joint
import sqlite3, pathlib, config

db = pathlib.Path(config.DB_PATH)
conn = sqlite3.connect(db.as_posix())
cur = conn.cursor()
cur.execute("PRAGMA journal_mode=WAL;")
print(f"Migration v3 sur : {db.as_posix()}")

# ── Type de wallet : joint ────────────────────────────────────────────────────
existing = [r[1] for r in cur.execute("PRAGMA table_info(wallets)").fetchall()]
if 'wallet_type' not in existing:
    cur.execute("ALTER TABLE wallets ADD COLUMN wallet_type TEXT DEFAULT 'personal'")
    print("  wallets.wallet_type ajouté")

# ── Dépenses fixes ────────────────────────────────────────────────────────────
cur.execute("""
CREATE TABLE IF NOT EXISTS fixed_expenses (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_id     INTEGER NOT NULL,
    user_id       INTEGER NOT NULL,
    label         TEXT    NOT NULL,
    amount        REAL    NOT NULL,
    category_id   INTEGER,
    frequency     TEXT    DEFAULT 'monthly',
    next_date     TEXT    NOT NULL,
    auto_insert   INTEGER DEFAULT 0,
    note          TEXT    DEFAULT '',
    active        INTEGER DEFAULT 1,
    created_at    TEXT    DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (wallet_id)   REFERENCES wallets(id),
    FOREIGN KEY (user_id)     REFERENCES users(id),
    FOREIGN KEY (category_id) REFERENCES categories(id)
)
""")

# ── Index ─────────────────────────────────────────────────────────────────────
cur.execute("CREATE INDEX IF NOT EXISTS idx_fe_wallet ON fixed_expenses(wallet_id)")
cur.execute("CREATE INDEX IF NOT EXISTS idx_fe_next   ON fixed_expenses(next_date)")

conn.commit()
conn.close()
print("✅ Migration v3 terminée")
