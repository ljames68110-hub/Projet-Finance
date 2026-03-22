# config.py
import os

# ── Base de données ────────────────────────────────────────────────────────────
# IMPORTANT : toute l'appli utilise app.db (auth + finance)
USE_SQLCIPHER  = False
SQLCIPHER_KEY  = os.getenv("SQLCIPHER_KEY", "change_me_secure_key")
DB_PATH        = os.getenv("DB_PATH", "app.db")   # ← une seule DB

# ── JWT ────────────────────────────────────────────────────────────────────────
JWT_SECRET     = os.getenv("JWT_SECRET",     "UneChaineTresLongueEtSecrete_ChangeThis")
REFRESH_SECRET = os.getenv("REFRESH_SECRET", "UneChaineTresLongueEtSecrete_Refresh")

# ── SMTP ───────────────────────────────────────────────────────────────────────
SMTP_HOST    = os.getenv("SMTP_HOST",    "smtp.exemple.com")
SMTP_PORT    = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER    = os.getenv("SMTP_USER",    "no-reply@exemple.com")
SMTP_PASS    = os.getenv("SMTP_PASS",    "")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() in ("1","true","yes")

# ── Version ────────────────────────────────────────────────────────────────────
APP_VERSION = "1.0.0"
