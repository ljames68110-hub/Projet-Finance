# FinanceApp 💳

Application de gestion de comptes personnels — multi-portefeuilles, PWA installable, temps réel.

## 🚀 Installation

```powershell
# 1. Cloner le repo
git clone https://github.com/TON_PSEUDO/gestion_dettes.git
cd gestion_dettes

# 2. Créer l'environnement Python
python -m venv .venv
.\.venv\Scripts\pip install -r requirements_finance.txt

# 3. Lancer
.\run_finance.ps1
```

Ouvrir **http://127.0.0.1:5000** — installer comme PWA via le menu du navigateur (⋮ → Installer FinanceApp).

---

## 🔄 Mise à jour

```powershell
# Arrêter le serveur (Ctrl+C), puis :
git pull origin main
.\.venv\Scripts\pip install -r requirements_finance.txt --upgrade
.\run_finance.ps1
# La migration est automatique au démarrage
```

---

## 📁 Structure

```
├── app_finance.py          # Point d'entrée Flask
├── finance_routes.py       # API : wallets, transactions, stats, admin
├── auth.py                 # Authentification bcrypt
├── jwt_utils.py            # Création/vérification JWT
├── db.py                   # Connexion SQLite
├── config.py               # Configuration (DB, SMTP, JWT)
├── migrate_finance.py      # Migrations DB
├── run_finance.ps1         # Script de démarrage Windows
├── requirements_finance.txt
├── static/
│   ├── index.html          # PWA complète (SPA)
│   ├── manifest.json       # Config PWA
│   └── sw.js               # Service Worker (offline)
└── .gitignore
```

---

## ⚙️ Configuration

Variables d'environnement (ou fichier `.env`) :

| Variable | Description | Défaut |
|---|---|---|
| `JWT_SECRET` | Clé secrète JWT | ⚠️ À changer |
| `DB_PATH` | Chemin base de données | `app.db` |
| `SMTP_HOST` | Serveur mail | `smtp.exemple.com` |
| `SMTP_PORT` | Port SMTP | `587` |
| `SMTP_USER` | Email expéditeur | — |
| `SMTP_PASS` | Mot de passe SMTP | — |

---

## 🔒 Sécurité

- Mots de passe hashés avec **bcrypt**
- Authentification par **JWT** (expiration 60 min)
- Les fichiers `.db`, `.env`, `Utilisateurs.csv` sont exclus du dépôt git
- Ne jamais committer `config.py` avec de vrais secrets — utiliser des variables d'environnement

---

## 📱 PWA

L'application est installable :
- **Chrome/Edge PC** : icône d'installation dans la barre d'adresse
- **Android** : Menu ⋮ → "Ajouter à l'écran d'accueil"
- **iOS Safari** : Partager → "Sur l'écran d'accueil"
