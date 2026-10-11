@echo off
rem ============================================================================
rem  Installe ou met a jour l'agent GI-Suivi sur ce poste. Double-cliquer.
rem  - demande lui-meme les droits d'administrateur (fenetre de controle de compte) ;
rem  - copie d'abord le kit sur le disque local : une fenetre administrateur ne voit
rem    pas les lecteurs reseau (M:, Q:...) ouverts par l'utilisateur ;
rem  - debloque les scripts et lance installer-poste.ps1 sans changer la strategie
rem    d'execution de PowerShell du poste (option -ExecutionPolicy Bypass pour ce seul
rem    lancement).
rem  Le certificat du serveur (gic-serveur.cer) doit etre dans le meme dossier.
rem ============================================================================
setlocal
chcp 65001 >nul
set "LOCAL=%TEMP%\GiSuivi-kit"

rem 1. Deja administrateur et lance depuis la copie locale : on installe.
net session >nul 2>&1
if %errorlevel%==0 if /i "%~1"=="local" goto installer

rem 2. Sinon : copie locale (cette fenetre voit encore les lecteurs reseau), puis elevation.
echo Copie du kit dans %LOCAL% ...
robocopy "%~dp0." "%LOCAL%" /MIR /NFL /NDL /NJH /NJS /NP >nul
if %errorlevel% geq 8 (
    echo ECHEC : copie du kit impossible depuis %~dp0
    pause
    exit /b 1
)
echo Demande des droits d'administrateur...
powershell -NoProfile -Command "Start-Process -FilePath '%LOCAL%\%~nx0' -ArgumentList 'local' -Verb RunAs"
exit /b 0

:installer
cd /d "%~dp0"
if not exist "%~dp0gic-serveur.cer" (
    echo ATTENTION : gic-serveur.cer absent de ce dossier.
    echo Le navigateur et l'agent refuseront le serveur tant que son certificat n'est pas approuve.
    echo Copiez gic-serveur.cer a cote de ce fichier, puis relancez. Ou appuyez sur une touche pour continuer quand meme.
    pause
)
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-ChildItem -LiteralPath '%~dp0' -Recurse | Unblock-File"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0installer-poste.ps1"
if %errorlevel% neq 0 (
    echo.
    echo L'installation a signale une erreur : lisez les lignes ci-dessus.
) else (
    echo.
    echo Installation terminee. L'icone GI-Suivi apparait pres de l'horloge sous 15 secondes.
    echo Fermez completement le navigateur puis rouvrez-le pour la page « Mon activite du jour ».
)
pause
