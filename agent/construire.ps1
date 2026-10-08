<#
.SYNOPSIS
  Poste Windows de construction — Construit l'agent (PyInstaller, --onedir).
  Le MSI (WiX) viendra avec le ticket G07 ; ce script produit déjà un dossier
  dist\gisuivi-agent\ exécutable, suffisant pour le poste de test et le pilote.

.USAGE
    cd <dépôt>\agent
    .\construire.ps1              # construit dist\gisuivi-agent\gisuivi-agent.exe
    .\construire.ps1 -Tester      # lance d'abord les tests (dont ceux marqués windows)
#>
param([switch]$Tester)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$depot = Split-Path $PSScriptRoot -Parent

# Python 3.14 de préférence (version du projet) ; sinon le python par défaut, avec avertissement
$py = "python"
if (Get-Command py -ErrorAction SilentlyContinue) {
    $versions = & py -0 2>$null | Out-String
    if ($versions -match "3\.14") { $py = "py -3.14" } else { Write-Warning "Python 3.14 absent ; construction avec la version par défaut ($(python --version)). Si une bibliothèque refuse de s'installer, installez Python 3.14 depuis python.org." }
}
if (-not (Test-Path .venv)) { Invoke-Expression "$py -m venv .venv" }
& .\.venv\Scripts\python.exe -m pip install --upgrade pip --quiet
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt --quiet

# Le moteur partagé est pris dans le dépôt : PYTHONPATH sur la racine
$env:PYTHONPATH = "$depot;$PSScriptRoot"
# --noconftest : le conftest.py de la racine (fixtures Django) ne concerne pas l'agent, dont l'environnement n'a pas Django
if ($Tester) { & .\.venv\Scripts\python.exe -m pytest "$depot\moteur" tests -q --noconftest -p no:cacheprovider; if ($LASTEXITCODE -ne 0) { throw "Tests en échec." } }

$version = (Select-String -Path gisuivi_agent\__init__.py -Pattern '__version__ = "([^"]+)"').Matches[0].Groups[1].Value
Write-Host "Construction de gisuivi-agent $version ..."
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onedir --noconsole --name gisuivi-agent `
    --paths $depot --paths $PSScriptRoot `
    --hidden-import win32timezone --hidden-import pystray._win32 --hidden-import PIL.Image `
    --collect-submodules gisuivi_agent --collect-submodules moteur `
    lancer.py
Copy-Item config.exemple.json dist\gisuivi-agent\config.exemple.json -Force
Write-Host "`nTerminé : dist\gisuivi-agent\gisuivi-agent.exe"
Write-Host "Pour un test : copier config.exemple.json en dist\gisuivi-agent\config.json (ou en $env:ProgramData\GiSuivi\config.json), ajuster les racines, lancer l'exe."
Write-Host "Le premier config.json trouve l'emporte : a cote de l'exe, puis ProgramData. Le registre (GPO) passe avant les deux."
Write-Host "Empreinte : surveiller gisuivi-agent.exe dans le Gestionnaire des tâches (cible < 1 % CPU, < 80 Mo)."
