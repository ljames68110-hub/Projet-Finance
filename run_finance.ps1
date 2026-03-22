# run_finance.ps1 — Lance FinanceApp
Set-StrictMode -Version Latest
$proj = "C:\Users\Yoann\Documents\Projet Finance"
Set-Location $proj

if (-not $env:JWT_SECRET)     { $env:JWT_SECRET     = "UneChaineTresLongueEtSecrete_ChangeThis" }
if (-not $env:REFRESH_SECRET) { $env:REFRESH_SECRET = "UneChaineTresLongueEtSecrete_Refresh" }

$python = Join-Path $proj ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "Python venv introuvable." -ForegroundColor Red; exit 1
}

Get-Process -Name python -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Milliseconds 300

Write-Host "Migration v1..." -ForegroundColor Cyan
& $python "$proj\migrate_finance.py"
Write-Host "Migration v2..." -ForegroundColor Cyan
& $python "$proj\migrate_v2.py"
Write-Host "Migration v3..." -ForegroundColor Cyan
& $python "$proj\migrate_v3.py"

Write-Host ""
Write-Host "Demarrage FinanceApp..." -ForegroundColor Green
& $python "$proj\app_finance.py"