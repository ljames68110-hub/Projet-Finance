# run_finance.ps1
Set-StrictMode -Version Latest
$proj = "C:\Users\Yoann\Documents\Projet Finance"
Set-Location $proj

if (-not $env:JWT_SECRET)     { $env:JWT_SECRET     = "UneChaineTresLongueEtSecrete_ChangeThis" }
if (-not $env:REFRESH_SECRET) { $env:REFRESH_SECRET = "UneChaineTresLongueEtSecrete_Refresh" }

$python = Join-Path $proj ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { Write-Host "Python venv introuvable." -ForegroundColor Red; exit 1 }

Get-Process -Name python -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 300

Write-Host "Migrations..." -ForegroundColor Cyan
& $python "$proj\migrate_finance.py"
& $python "$proj\migrate_v2.py"
& $python "$proj\migrate_v3.py"
& $python "$proj\migrate_v4.py"

Write-Host ""
Write-Host "Demarrage FinanceApp..." -ForegroundColor Green
& $python "$proj\app_finance.py"
