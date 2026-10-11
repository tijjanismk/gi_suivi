@echo off
rem ============================================================================
rem  Relance l'agent GI-Suivi de la session : utile quand l'icone reste grise
rem  « hors reseau » alors que le serveur repond. Double-cliquer, dans la session
rem  de la personne (pas besoin d'etre administrateur). Les mesures en attente sont
rem  conservees et envoyees au premier essai reussi.
rem ============================================================================
setlocal
chcp 65001 >nul
klist purge >nul 2>&1
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-ChildItem -LiteralPath '%~dp0' -Filter *.ps1 | Unblock-File"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0relancer-agent.ps1"
pause
