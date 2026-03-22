# migrate_finance.py — Migration finance sur app.db (même DB que auth)
import sqlite3
import pathlib
import config

db = pathlib.Path(config.DB_PATH)
db.parent.mkdir(parents=True, exist_ok=True)
conn = sqlite3.connect(db.as_posix())
cur = conn.cursor()
cur.execute("PRAGMA journal_mode=WAL;")

print(f"Migration sur : {db.as_posix()}")

# S'assurer que la colonne 'name' existe dans users (app.db ne l'a pas toujours)
user_cols = [r[1] for r in cur.execute("PRAGMA table_info(users)").fetchall()]
if 'name' not in user_cols:
    cur.execute("ALTER TABLE users ADD COLUMN name TEXT DEFAULT ''")
    cur.execute("UPDATE users SET name = COALESCE(login, email) WHERE name IS NULL OR name = ''")
    conn.commit()
    print("Colonne 'name' ajoutee a users.")

cur.execute("""
CREATE TABLE IF NOT EXISTS wallets (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    description TEXT    DEFAULT '',
    currency    TEXT    DEFAULT 'EUR',
    owner_id    INTEGER NOT NULL,
    is_shared   INTEGER DEFAULT 0,
    color       TEXT    DEFAULT '#6366f1',
    icon        TEXT    DEFAULT '\U0001f4b3',
    iban        TEXT    DEFAULT '',
    created_at  TEXT    DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (owner_id) REFERENCES users(id)
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS wallet_members (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_id  INTEGER NOT NULL,
    user_id    INTEGER NOT NULL,
    can_write  INTEGER DEFAULT 1,
    added_at   TEXT    DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (wallet_id) REFERENCES wallets(id),
    FOREIGN KEY (user_id)   REFERENCES users(id),
    UNIQUE(wallet_id, user_id)
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS categories (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT NOT NULL,
    type    TEXT NOT NULL,
    color   TEXT DEFAULT '#6366f1',
    icon    TEXT DEFAULT '\U0001f4e6',
    user_id INTEGER,
    FOREIGN KEY (user_id) REFERENCES users(id)
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_id   INTEGER NOT NULL,
    user_id     INTEGER NOT NULL,
    amount      REAL    NOT NULL,
    type        TEXT    NOT NULL,
    category_id INTEGER,
    label       TEXT    NOT NULL,
    note        TEXT    DEFAULT '',
    date        TEXT    NOT NULL,
    created_at  TEXT    DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (wallet_id)   REFERENCES wallets(id),
    FOREIGN KEY (user_id)     REFERENCES users(id),
    FOREIGN KEY (category_id) REFERENCES categories(id)
)
""")

# Colonnes additives (DB existante)
safe_adds = [
    ("wallets", "iban",        "TEXT DEFAULT ''"),
    ("wallets", "description", "TEXT DEFAULT ''"),
    ("wallets", "is_shared",   "INTEGER DEFAULT 0"),
    ("wallets", "color",       "TEXT DEFAULT '#6366f1'"),
]
for table, col, defn in safe_adds:
    existing = [r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()]
    if col not in existing:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {defn}")
        print(f"Colonne {table}.{col} ajoutee.")

# Index
for stmt in [
    "CREATE INDEX IF NOT EXISTS idx_tx_wallet   ON transactions(wallet_id)",
    "CREATE INDEX IF NOT EXISTS idx_tx_user     ON transactions(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_tx_date     ON transactions(date)",
    "CREATE INDEX IF NOT EXISTS idx_wm_wallet   ON wallet_members(wallet_id)",
    "CREATE INDEX IF NOT EXISTS idx_wm_user     ON wallet_members(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_wallets_own ON wallets(owner_id)",
]:
    cur.execute(stmt)

# Categories par defaut
defaults = [
    ('Alimentation','expense','#ef4444','\U0001f6d2'),
    ('Transport','expense','#f97316','\U0001f697'),
    ('Logement','expense','#eab308','\U0001f3e0'),
    ('Sante','expense','#22c55e','\u2695\ufe0f'),
    ('Loisirs','expense','#3b82f6','\U0001f3ae'),
    ('Vetements','expense','#a855f7','\U0001f455'),
    ('Restaurants','expense','#ec4899','\U0001f37d\ufe0f'),
    ('Abonnements','expense','#14b8a6','\U0001f4f1'),
    ('Education','expense','#6366f1','\U0001f4da'),
    ('Autre depense','expense','#6b7280','\U0001f4e6'),
    ('Salaire','income','#22c55e','\U0001f4bc'),
    ('Freelance','income','#3b82f6','\U0001f4bb'),
    ('Investissement','income','#eab308','\U0001f4c8'),
    ('Cadeau','income','#ec4899','\U0001f381'),
    ('Remboursement','income','#14b8a6','\u21a9\ufe0f'),
    ('Autre revenu','income','#6b7280','\U0001f4b0'),
]
for name, t, color, icon in defaults:
    cur.execute("SELECT id FROM categories WHERE name=? AND type=? AND user_id IS NULL", (name, t))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO categories (name,type,color,icon,user_id) VALUES (?,?,?,?,NULL)",
            (name, t, color, icon)
        )


# Nettoyer les doublons existants (garde le plus ancien)
cur.execute("""
    DELETE FROM categories
    WHERE user_id IS NULL AND id NOT IN (
        SELECT MIN(id) FROM categories
        WHERE user_id IS NULL
        GROUP BY name, type
    )
""")
conn.commit()
print("Doublons de categories supprimes.")
conn.commit()
conn.close()
print("Migration finance terminee sur", db.as_posix())
