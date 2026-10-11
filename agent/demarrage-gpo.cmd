@echo off
rem Lance par la GPO « GI-Suivi - Agent » au demarrage de l'ordinateur (compte SYSTEM).
rem Un fichier .cmd plutot qu'un script PowerShell direct : la strategie d'execution des postes
rem bloquerait un .ps1 ; ici PowerShell est lance en Bypass pour ce seul script.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0demarrage-gpo.ps1"
exit /b %errorlevel%
