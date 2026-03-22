# run_finance.ps1 — Lance FinanceApp (version avec portefeuilles)
Set-StrictMode -Version Latest
$proj = "C:\Users\Yoann\Documents\Projet Finance"
Set-Location $proj

# Variables d'environnement
if (-not $env:JWT_SECRET)     { $env:JWT_SECRET     = "UneChaineTresLongueEtSecrete_ChangeThis" }
if (-not $env:REFRESH_SECRET) { $env:REFRESH_SECRET = "UneChaineTresLongueEtSecrete_Refresh" }

$python = Join-Path $proj ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "❌ Python venv introuvable. Lance d'abord setup_env.ps1"
    exit 1
}

# 1) Migration finance (crée les tables si elles n'existent pas)
Write-Host "▶ Migration de la base de données..."
& $python "$proj\migrate_finance.py"
if ($LASTEXITCODE -ne 0) { Write-Host "⚠ Migration a renvoyé une erreur non fatale (colonnes déjà présentes probablement)." }

# 2) Stopper les vieux process Python
Get-Process -Name python -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 500

# 3) Lancer le serveur
Write-Host "▶ Démarrage du serveur sur http://127.0.0.1:5000 ..."
Write-Host "   Ouvrez http://127.0.0.1:5000 dans votre navigateur."
Write-Host "   Pour installer comme PWA : menu ⋮ → Installer FinanceApp"
Write-Host "   Ctrl+C pour arrêter."
& $python "$proj\app_finance.py"