<#
.SYNOPSIS
  Voie rapide : enchaîne, dans l'ordre et sans question, tout ce qu'il faut pour l'environnement
  test de GI-SUIVI sur AD-SERVEUR — sauvegarde, comptes et groupes, DNS/SPN, PostgreSQL, Python,
  IIS (certificat auto-signé), service, application, tâches planifiées, racines, vérification.
  Chaque étape reste un script lisible de ce dossier ; celui-ci ne fait que les appeler avec les
  bons paramètres et s'arrêter à la première erreur en indiquant le journal.

.USAGE (PowerShell administrateur, depuis C:\GIC\depot\deploy\serveur)
    .\Tout-en-un.ps1 -Directeur IBOUBACAR -Administrateur IBOUBACAR
    .\Tout-en-un.ps1 -Directeur IBOUBACAR -Administrateur IBOUBACAR -SansSauvegarde   # une sauvegarde du jour existe déjà
    .\Tout-en-un.ps1 ... -Simuler       # affiche les étapes et les fichiers trouvés, ne lance rien

.PREALABLES
    Dans C:\GIC\installateurs\ : postgresql-18.*-windows-x64.exe, python-3.14.*-amd64.exe,
    rewrite_amd64_*.msi, requestRouter_amd64.msi, nssm-2.24\win64\nssm.exe (zip décompressé).
    Rien d'autre : aucun outil de développement sur le serveur.

.CE QUI N'EST PAS FAIT ICI (volontairement)
    02 (RDP limité au LAN) et 03 (mises à jour Windows) : -AvecRDP / -AvecMisesAJour.
    05 (partage D:\GIC) : -AvecPartageGIC — inutile au pilote, l'équipe travaille sur les partages
    existants, qui sont les racines.
#>
param(
    [Parameter(Mandatory)][string]$Directeur,                 # login AD du directeur -> GI-Direction
    [string[]]$Lecture = @("ODICKO"),                         # consultation seule -> GI-Direction-Lecture
    [Parameter(Mandatory)][string]$Administrateur,            # login AD -> compte adm-<login> créé par 04
    [string]$Installateurs = "C:\GIC\installateurs",
    [string]$Ref = "main",
    [switch]$SansSauvegarde, [switch]$AvecRDP, [switch]$AvecMisesAJour, [switch]$AvecPartageGIC,
    [switch]$Simuler
)
$ErrorActionPreference = "Stop"
$ici = $PSScriptRoot; $deploy = Split-Path $ici -Parent
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { throw "À lancer en administrateur." }

function Trouver($motif, $obligatoire = $true) {
    $f = Get-ChildItem $Installateurs -Recurse -Filter $motif -ErrorAction SilentlyContinue | Sort-Object Name -Descending | Select-Object -First 1
    if (-not $f -and $obligatoire) { throw "Introuvable dans $Installateurs : $motif (voir docs\exploitation\liste-de-controle-serveur.md § 0)." }
    if ($f) { $f.FullName } else { $null }
}
$pgInstalle = [bool](Get-Service "postgresql-x64-18" -ErrorAction SilentlyContinue)
$postgres = Trouver "postgresql-18*-windows-x64.exe" (-not $pgInstalle)
if ($pgInstalle) { Write-Host "PostgreSQL 18 déjà installé (service postgresql-x64-18) : rôle et bases seulement." }
$python   = Trouver "python-3.14*-amd64.exe"
$rewrite  = Trouver "rewrite_amd64*.msi"
$arr      = Trouver "requestRouter_amd64*.msi"
$nssm     = Trouver "nssm.exe"
if ($nssm -notmatch "win64") { Write-Warning "nssm.exe trouvé hors d'un dossier win64 : $nssm" }

Write-Host "`n=== GI-SUIVI — environnement test, tout-en-un ===" -ForegroundColor Cyan
Write-Host "Directeur : $Directeur   Consultation : $($Lecture -join ', ')   Administrateur : adm-$Administrateur"
Write-Host "PostgreSQL : $postgres`nPython     : $python`nURL Rewrite: $rewrite`nARR        : $arr`nNSSM       : $nssm"

$etapes = @()
if (-not $SansSauvegarde) { $etapes += @{ nom = "P01 Sauvegarde système (20 à 60 min)"; cmd = { & "$ici\01-Sauvegarde-Systeme.ps1" -Planifier } } }
if ($AvecRDP)             { $etapes += @{ nom = "P02 Bureau à distance limité au LAN"; cmd = { & "$ici\02-Restreindre-RDP-Local.ps1" } } }
if ($AvecMisesAJour)      { $etapes += @{ nom = "P03 Mises à jour Windows"; cmd = { & "$ici\03-Mises-a-jour.ps1" } } }
$etapes += @{ nom = "P04 OU, groupes, compte de service"; cmd = { & "$ici\04-Comptes-et-groupes.ps1" -Membres @{ "GI-Direction" = @($Directeur); "GI-Direction-Lecture" = $Lecture } -Administrateurs $Administrateur } }
if ($AvecPartageGIC)      { $etapes += @{ nom = "P06 Partage D:\GIC"; cmd = { & "$ici\05-Partage-GIC.ps1" } } }
$etapes += @{ nom = "S07 DNS et SPN"; cmd = { & "$ici\06-DNS-SPN.ps1" } }
if ($pgInstalle) { $etapes += @{ nom = "S07 PostgreSQL 18 : rôle gic et bases (mot de passe postgres demandé une fois)"; cmd = { & "$ici\07-PostgreSQL.ps1" -SeulementBases -Version 18 } } }
else             { $etapes += @{ nom = "S07 PostgreSQL 18"; cmd = { & "$ici\07-PostgreSQL.ps1" -Installateur $postgres -Version 18 } } }
$etapes += @{ nom = "S07 Python, IIS, certificat auto-signé"; cmd = { & "$ici\08-Python-IIS.ps1" -Python $python -UrlRewrite $rewrite -ARR $arr -AutoSigne } }
$etapes += @{ nom = "Service GIC-Test"; cmd = { & "$deploy\service.ps1" -Env test -Nssm $nssm -Creer } }
$etapes += @{ nom = "Application (Git, $Ref)"; cmd = { & "$deploy\installer.ps1" -Env test -Ref $Ref } }
$etapes += @{ nom = "Tâches planifiées"; cmd = { & "$deploy\taches.ps1" -Env test } }
$etapes += @{ nom = "Racines de classement (partages existants)"; cmd = {
    Push-Location C:\GIC\test\app
    $env:DJANGO_SETTINGS_MODULE = "config.settings.prod"
    & C:\GIC\test\venv\Scripts\python.exe manage.py suivi_racines agent\config-pilote.json
    $code = $LASTEXITCODE; Pop-Location
    if ($code -ne 0) { throw "suivi_racines : code $code" }
} }
$etapes += @{ nom = "Vérification"; cmd = { & "$deploy\verifier.ps1" -Env test } }

$n = 0
foreach ($e in $etapes) {
    $n++
    Write-Host "`n--- [$n/$($etapes.Count)] $($e.nom)" -ForegroundColor Cyan
    if ($Simuler) { continue }
    try { & $e.cmd }
    catch {
        Write-Host "`nARRÊT à l'étape « $($e.nom) » : $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "Journaux : D:\SAUVEGARDES\journaux\ (scripts 01-08) et C:\GIC\test\journaux\ (application)."
        Write-Host "Corriger, puis relancer ce script : chaque étape est idempotente (ce qui est fait n'est pas refait)."
        exit 1
    }
}
if ($Simuler) { Write-Host "`nSimulation : rien n'a été lancé." -ForegroundColor Yellow; exit 0 }

$zone = (Get-ADDomain).DNSRoot
Write-Host "`n=== Terminé ===" -ForegroundColor Green
Write-Host "1. Depuis un poste du domaine : https://suivi-test.$zone/identite/qui-suis-je (login et groupes sans mot de passe)."
Write-Host "2. Poste de Dicko : kit GiSuivi-agent-<version>-poste.zip + C:\GIC\deploy\gic-serveur.cer à côté d'installer-poste.ps1, puis installer-poste.ps1 en administrateur."
Write-Host "3. Sous 3 minutes, le poste apparaît dans https://suivi-test.$zone/suivi/postes/."
