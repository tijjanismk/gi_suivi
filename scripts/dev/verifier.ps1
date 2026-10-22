# Les contrôles de la CI (.github/workflows/ci.yml), sur le poste, avant chaque envoi vers GitHub.
#   .\scripts\dev\verifier.ps1
# S'arrête au premier échec. Ne pousser que si la dernière ligne dit « Tout est vert ».
# Prérequis : .venv à la racine (pip install -e ".[dev]") et la base locale (scripts\dev\creer_base_dev.sql).
$ErrorActionPreference = 'Stop'
$racine = Resolve-Path (Join-Path $PSScriptRoot '..\..')
Set-Location $racine
$py = Join-Path $racine '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { throw "Environnement absent : py -3.14 -m venv .venv ; .venv\Scripts\pip install -e "".[dev]""" }

function Etape([string]$nom, [scriptblock]$commande) {
    Write-Host "`n=== $nom" -ForegroundColor Cyan
    & $commande
    if ($LASTEXITCODE -ne 0) { Write-Host "ÉCHEC : $nom" -ForegroundColor Red; exit 1 }
}

Etape 'Lint (ruff check)' { & $py -m ruff check . }
Etape 'Format (ruff format --check)' { & $py -m ruff format --check . }
Etape 'Migrations à jour' { & $py manage.py makemigrations --check --dry-run }
Etape 'deploy/requirements.txt à jour (serveur sans outil de développement)' {
    & $py scripts\dev\exporter_dependances.py --verifier
}
Etape 'Tests moteur et Django' {
    & $py -m pytest --cov=moteur --cov=suivi --cov=identite --cov=administratif --cov=referentiel --cov=references --cov-report=term-missing -m "not e2e and not windows" -q
}
Etape 'Parcours de bout en bout' {
    & $py -m pytest -m e2e -q
    if ($LASTEXITCODE -eq 5) { $global:LASTEXITCODE = 0 }  # aucun test e2e encore : normal avant la phase 4
}
Etape 'Agent (tests hors Windows)' { & $py -m pytest agent/tests -m "not windows" -q }

Write-Host "`nTout est vert : on peut pousser." -ForegroundColor Green
