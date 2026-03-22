# github_push.ps1 — Pousser le code sur GitHub
# Usage : .\github_push.ps1 "Message du commit"
param(
    [string]$Message = "mise a jour"
)

Set-StrictMode -Version Latest
$proj = "C:\Users\Yoann\Documents\Projet Finance"
Set-Location $proj

# Vérifier que git est installé
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "Git n'est pas installe. Telechargez-le sur https://git-scm.com"
    exit 1
}

# Initialiser git si pas encore fait
if (-not (Test-Path ".git")) {
    Write-Host "Initialisation du repo git..."
    git init
    git branch -M main

    $remote = Read-Host "URL du repo GitHub (ex: https://github.com/Yoann/gestion_dettes.git)"
    git remote add origin $remote
}

# Ajouter tous les fichiers (le .gitignore exclut les DB et secrets)
git add -A

# Vérifier s'il y a des changements
$status = git status --porcelain
if (-not $status) {
    Write-Host "Aucun changement a committer."
    exit 0
}

# Commit
$date = Get-Date -Format "yyyy-MM-dd HH:mm"
$fullMessage = "$Message [$date]"
git commit -m $fullMessage

# Push
Write-Host "Push vers GitHub..."
git push -u origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host "Code pousse avec succes !" -ForegroundColor Green
} else {
    Write-Host "Erreur lors du push. Verifie tes identifiants GitHub." -ForegroundColor Red
    Write-Host "Conseil : utilise un Personal Access Token (PAT) comme mot de passe."
    Write-Host "https://github.com/settings/tokens"
}
