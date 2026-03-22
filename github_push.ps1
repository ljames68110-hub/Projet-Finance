# github_push.ps1 — Pousser le code sur GitHub
# Usage : .\github_push.ps1 "Message du commit"
param(
    [string]$Message = "mise a jour"
)

Set-StrictMode -Version Latest
$proj = "C:\Users\Yoann\Documents\Projet Finance"

# Aller dans le bon dossier
if (-not (Test-Path $proj)) {
    Write-Host "Dossier introuvable : $proj" -ForegroundColor Red
    exit 1
}
Set-Location $proj
Write-Host "Dossier : $proj" -ForegroundColor Cyan

# Verifier git
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "Git n'est pas installe. Telechargez-le : https://git-scm.com" -ForegroundColor Red
    exit 1
}

# Initialiser git si necessaire
if (-not (Test-Path ".git")) {
    Write-Host "Initialisation du repo git..." -ForegroundColor Yellow
    git init
    git branch -M main
    $remote = Read-Host "URL du repo GitHub (ex: https://github.com/Yoann/gestion_dettes.git)"
    git remote add origin $remote
    Write-Host "Remote configure." -ForegroundColor Green
}

# Verifier remote
$remoteUrl = git remote get-url origin 2>$null
if (-not $remoteUrl) {
    $remote = Read-Host "URL du repo GitHub"
    git remote add origin $remote
}

# Ajouter fichiers (le .gitignore exclut DB et secrets)
git add -A

# Verifier s'il y a des changements
$status = git status --porcelain
if (-not $status) {
    Write-Host "Aucun changement a committer." -ForegroundColor Yellow
    exit 0
}

Write-Host "Fichiers modifies :" -ForegroundColor Cyan
git status --short

# Commit
$date = Get-Date -Format "yyyy-MM-dd HH:mm"
$fullMessage = "$Message [$date]"
git commit -m $fullMessage
Write-Host "Commit : $fullMessage" -ForegroundColor Green

# Push
Write-Host "Push vers GitHub..." -ForegroundColor Cyan
git push -u origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host "Code pousse avec succes !" -ForegroundColor Green
    Write-Host "Voir sur : $remoteUrl" -ForegroundColor Cyan
} else {
    Write-Host "" 
    Write-Host "Erreur lors du push. Solutions :" -ForegroundColor Red
    Write-Host "  1. Va sur https://github.com/settings/tokens" -ForegroundColor Yellow
    Write-Host "  2. Cree un Personal Access Token (classic) avec acces 'repo'" -ForegroundColor Yellow
    Write-Host "  3. Utilise ce token comme mot de passe quand git te le demande" -ForegroundColor Yellow
}