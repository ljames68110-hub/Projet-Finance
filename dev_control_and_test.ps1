# dev_control_and_test.ps1
Set-StrictMode -Version Latest

# Projet
$proj = "C:\Users\Yoann\Desktop\Projet Finance"
Set-Location $proj

# Variables d'environnement par défaut pour cette session
$defaultJwt = "UneChaineTresLongueEtSecrete_ChangeThis"
$defaultRefresh = "UneChaineTresLongueEtSecrete_Refresh"
$defaultDb = "sqlite:///./refresh_tokens.db"

if (-not $env:JWT_SECRET) { $env:JWT_SECRET = $defaultJwt }
if (-not $env:REFRESH_SECRET) { $env:REFRESH_SECRET = $defaultRefresh }
if (-not $env:DATABASE_URL) { $env:DATABASE_URL = $defaultDb }

# Stopper tous les python en cours (silencieux)
Get-Process -Name python -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

# Vérifier l'existence du venv et du script serveur
$pythonPath = Join-Path $proj ".venv\Scripts\python.exe"
$serverScript = Join-Path $proj "auth_refresh.py"
if (-not (Test-Path $pythonPath)) {
    Write-Host "Erreur: python dans .venv introuvable:" $pythonPath
    exit 1
}
if (-not (Test-Path $serverScript)) {
    Write-Host "Erreur: script serveur introuvable:" $serverScript
    exit 1
}

# Démarrer le serveur en background job si pas déjà lancé
if (Get-Job -Name AuthServer -ErrorAction SilentlyContinue) {
    Write-Host "Job AuthServer déjà présent. Vérifie son état avec Get-Job."
} else {
    Start-Job -Name AuthServer -ScriptBlock {
        param($projPath, $jwtSecret, $refreshSecret, $dbUrl)
        Set-Location $projPath
        $env:JWT_SECRET = $jwtSecret
        $env:REFRESH_SECRET = $refreshSecret
        $env:DATABASE_URL = $dbUrl
        & "$projPath\.venv\Scripts\python.exe" "$projPath\auth_refresh.py"
    } -ArgumentList $proj, $env:JWT_SECRET, $env:REFRESH_SECRET, $env:DATABASE_URL | Out-Null

    Start-Sleep -Seconds 2
    Write-Host "Auth server démarré en job 'AuthServer'."
}

# Créer payload.json si absent
$payloadPath = Join-Path $proj "payload.json"
if (-not (Test-Path $payloadPath)) {
    $payload = @{
        identifier = "Yoann"
        password   = "Lk@09112004"
    } | ConvertTo-Json
    $payload | Set-Content -Path $payloadPath -Encoding utf8
    Write-Host "payload.json créé."
} else {
    Write-Host "payload.json existe."
}

# Helper pour appeler l'API et afficher erreurs
function Safe-PostJson($url, $bodyJson) {
    try {
        return Invoke-RestMethod -Uri $url -Method Post -ContentType "application/json" -Body $bodyJson -ErrorAction Stop
    } catch {
        Write-Host "Erreur HTTP POST vers $url"
        Write-Host $_.Exception.Message
        return $null
    }
}

function Safe-Get($url, $headers) {
    try {
        return Invoke-RestMethod -Uri $url -Method Get -Headers $headers -ErrorAction Stop
    } catch {
        Write-Host "Erreur HTTP GET vers $url"
        Write-Host $_.Exception.Message
        return $null
    }
}

# 1) Login -> récupérer tokens
$loginBody = Get-Content $payloadPath -Raw
$loginResp = Safe-PostJson "http://127.0.0.1:5000/login" $loginBody
if (-not $loginResp -or -not $loginResp.access_token) {
    Write-Host "Login échoué. Affichage de la réponse brute (si disponible):"
    if ($loginResp) { $loginResp | ConvertTo-Json -Depth 5 | Write-Host } 
    exit 1
}
$access = $loginResp.access_token
$refresh = $loginResp.refresh_token
Write-Host "Access token récupéré."
Write-Host "Refresh token récupéré."

# 2) Appel /protected avec access token
Write-Host "Appel de /protected..."
$hdr = @{ Authorization = "Bearer $access" }
$protectedResp = Safe-Get "http://127.0.0.1:5000/protected" $hdr
if ($protectedResp) {
    $protectedResp | ConvertTo-Json -Depth 5 | Write-Host
} else {
    Write-Host "/protected a échoué."
}

# 3) Refresh tokens
Write-Host "Appel de /token/refresh..."
$refreshBody = @{ refresh_token = $refresh } | ConvertTo-Json
$refResp = Safe-PostJson "http://127.0.0.1:5000/token/refresh" $refreshBody
if ($refResp) {
    Write-Host "Réponse refresh:"
    $refResp | ConvertTo-Json -Depth 5 | Write-Host
} else {
    Write-Host "Refresh échoué."
}

# 4) Logout (utilise le refresh retourné par refresh si présent, sinon l'ancien)
$logoutToken = if ($refResp -and $refResp.refresh_token) { $refResp.refresh_token } else { $refresh }
Write-Host "Appel de /logout..."
$logoutBody = @{ refresh_token = $logoutToken } | ConvertTo-Json
$logoutResp = Safe-PostJson "http://127.0.0.1:5000/logout" $logoutBody
if ($logoutResp) {
    $logoutResp | ConvertTo-Json -Depth 5 | Write-Host
} else {
    Write-Host "Logout échoué."
}

Write-Host "Terminé. Pour voir la sortie du job serveur :"
Write-Host "  Get-Job -Name AuthServer"
Write-Host "  Receive-Job -Name AuthServer -Keep"
Write-Host "Pour arrêter le serveur job : Stop-Job -Name AuthServer ; Remove-Job -Name AuthServer"