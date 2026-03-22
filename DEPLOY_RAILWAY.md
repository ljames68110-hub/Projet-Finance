# 🚀 Déploiement Railway — FinanceApp

## Étapes (15 minutes)

### 1. Pousser le code sur GitHub
```powershell
cd "C:\Users\Yoann\Documents\Projet Finance"
.\github_push.ps1 "deploy railway"
```

### 2. Créer un compte Railway
- Va sur **https://railway.app**
- Connecte-toi avec ton compte GitHub

### 3. Créer le projet
- Clique **"New Project"**
- Choisis **"Deploy from GitHub repo"**
- Sélectionne **"Projet-Finance"**
- Railway détecte automatiquement Python et lance le déploiement

### 4. Ajouter un volume persistant pour la DB
- Dans ton projet Railway → clique **"+ New"** → **"Volume"**
- Mount path : `/data`
- Valide

### 5. Configurer les variables d'environnement
Dans Railway → ton service → onglet **"Variables"**, ajoute :

| Variable | Valeur |
|---|---|
| `JWT_SECRET` | Une longue chaîne secrète (ex: `MonSecretFinanceApp2024!`) |
| `DB_PATH` | `/data/app.db` |
| `SMTP_HOST` | `smtp.office365.com` (quand tu auras configuré le SMTP) |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | ton email |
| `SMTP_PASS` | ton mot de passe |

### 6. Obtenir ton URL permanente
- Railway → ton service → onglet **"Settings"**
- Section **"Domains"** → clique **"Generate Domain"**
- Tu obtiens une URL comme `projet-finance-production.up.railway.app`
- **C'est ton URL permanente** — donne-la à ta femme, ça ne changera jamais !

### 7. Installer comme PWA
- Ouvre l'URL sur iPhone → Safari → Partager → **"Sur l'écran d'accueil"**
- Sur Android → Chrome → menu ⋮ → **"Ajouter à l'écran d'accueil"**
- Sur Windows → Edge/Chrome → icône d'installation dans la barre d'adresse

## Mises à jour
À chaque modification, fais juste :
```powershell
.\github_push.ps1 "description"
```
Railway redéploie automatiquement en 2 minutes !

## Migration de données
Si tu as déjà des données en local et veux les transférer sur Railway :
1. Copie ton `app.db` local
2. Dans Railway → Volume → Upload file → `/data/app.db`
