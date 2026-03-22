@echo off
title FinanceApp
color 0B
echo.
echo  ==========================================
echo   💳  FinanceApp — Lancement en cours...
echo  ==========================================
echo.
echo  Connexion au serveur Railway...
echo.

:: Ouvrir directement dans le navigateur par défaut
start "" "https://projet-finance-production.up.railway.app"

echo  ✅ FinanceApp ouvert dans votre navigateur !
echo.
echo  URL : https://projet-finance-production.up.railway.app
echo.
timeout /t 3 /nobreak >nul
exit
