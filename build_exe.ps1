# build_exe.ps1 — Crée le vrai logiciel FinanceApp.exe
Set-StrictMode -Version Latest
$proj = "C:\Users\Yoann\Documents\Projet Finance"
Set-Location $proj

$python = Join-Path $proj ".venv\Scripts\python.exe"
$pip    = Join-Path $proj ".venv\Scripts\pip.exe"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Construction de FinanceApp.exe" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Installer les dépendances
Write-Host "📦 Installation des dépendances..." -ForegroundColor Yellow
& $pip install pyinstaller pywebview --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "Erreur installation dépendances" -ForegroundColor Red
    exit 1
}

# Créer le fichier spec PyInstaller
$spec = @"
# -*- mode: python ; coding: utf-8 -*-
block_cipher = None

a = Analysis(
    ['FinanceApp_Portable.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'webview',
        'webview.platforms.winforms',
        'clr',
        'tkinter',
        'tkinter.ttk',
        'urllib.request',
        'threading',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='FinanceApp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
"@

$spec | Set-Content -Path "FinanceApp.spec" -Encoding utf8
Write-Host "✅ Fichier spec créé" -ForegroundColor Green

# Lancer PyInstaller
Write-Host ""
Write-Host "🔨 Compilation en cours (1-3 minutes)..." -ForegroundColor Yellow
& (Join-Path $proj ".venv\Scripts\pyinstaller.exe") `
    --clean `
    --noconfirm `
    "FinanceApp.spec"

if ($LASTEXITCODE -eq 0) {
    $exePath = Join-Path $proj "dist\FinanceApp.exe"
    $desktop = [Environment]::GetFolderPath('Desktop')
    $desktopExe = Join-Path $desktop "FinanceApp.exe"

    # Copier sur le bureau
    Copy-Item $exePath $desktopExe -Force

    Write-Host ""
    Write-Host "============================================" -ForegroundColor Green
    Write-Host "  ✅ FinanceApp.exe créé avec succès !" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  📁 Fichier : $exePath" -ForegroundColor Cyan
    Write-Host "  🖥️  Bureau  : $desktopExe" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Double-clique sur FinanceApp.exe pour lancer !" -ForegroundColor Yellow
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "❌ Erreur lors de la compilation" -ForegroundColor Red
    Write-Host "Vérifie les logs ci-dessus pour plus de détails" -ForegroundColor Yellow
}

# Nettoyage
Remove-Item -Path "FinanceApp.spec" -ErrorAction SilentlyContinue
Remove-Item -Path "build" -Recurse -ErrorAction SilentlyContinue