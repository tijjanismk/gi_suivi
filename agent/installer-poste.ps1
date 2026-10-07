# Installe l'agent GI-Suivi et son service de supervision sur CE poste (pilote, avant le MSI G07).
# À lancer en administrateur, depuis le dossier agent, après .\construire.ps1 -Tester.
#   .\installer-poste.ps1
# Ce que fait le script :
#   1. copie dist\gisuivi-agent\ dans C:\Program Files\GI-CONSEILS\GiSuivi\ (dossier non modifiable par l'utilisateur :
#      le service tourne en LocalSystem, il ne doit lancer qu'un exécutable protégé) ;
#   2. crée ou met à jour le service « GiSuivi » (démarrage automatique, relance en cas d'échec) ;
#   3. démarre le service, qui lance l'agent dans chaque session ouverte sous 15 s.
# Les données (%ProgramData%\GiSuivi : config.json, tampon, journaux) ne sont pas touchées.
param(
    [string]$Source = (Join-Path $PSScriptRoot 'dist\gisuivi-agent'),
    [string]$Cible = (Join-Path $env:ProgramFiles 'GI-CONSEILS\GiSuivi')
)
$ErrorActionPreference = 'Stop'
$service = 'GiSuivi'

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { throw "A lancer en administrateur." }
if (-not (Test-Path (Join-Path $Source 'gisuivi-agent.exe'))) { throw "Introuvable : $Source\gisuivi-agent.exe. Lancer d'abord .\construire.ps1 -Tester." }

# Arrêt de l'existant : service d'abord (sinon il relance l'agent), puis les agents
if (Get-Service $service -ErrorAction SilentlyContinue) {
    Stop-Service $service -Force
    Write-Host "Service $service arrete."
}
. (Join-Path $PSScriptRoot 'arreter-agent.ps1')
Stop-AgentProprement

New-Item -ItemType Directory -Force $Cible | Out-Null
& robocopy.exe $Source $Cible /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "Copie en echec (robocopy $LASTEXITCODE)." }
Write-Host "Copie : $Cible"

$exe = Join-Path $Cible 'gisuivi-agent.exe'
$binPath = "`"$exe`" --service"
# Pas de « sc.exe create binPath= ... » : PowerShell 5.1 transmet mal un argument qui contient
# à la fois des espaces et des guillemets. New-Service et le registre n'ont pas ce problème.
if (Get-Service $service -ErrorAction SilentlyContinue) {
    Set-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Services\$service" -Name ImagePath -Value $binPath
    Set-Service $service -StartupType Automatic
} else {
    New-Service -Name $service -BinaryPathName $binPath -StartupType Automatic `
        -DisplayName "GI-Suivi - supervision de l'agent" `
        -Description "Garde l'agent GI-Suivi ouvert dans chaque session (relance s'il est ferme). Ne mesure rien lui-meme." | Out-Null
}
# Si le service lui-même tombe : relance après 10 s, 10 s, puis 60 s ; compteur remis à zéro chaque jour
& sc.exe failure $service reset= 86400 actions= restart/10000/restart/10000/restart/60000 | Out-Null
if ($LASTEXITCODE -ne 0) { throw "sc.exe failure : echec ($LASTEXITCODE)." }

Start-Service $service
Write-Host "Service $service demarre. L'agent apparait dans la session sous 15 s."
Write-Host "Journal du service : $env:ProgramData\GiSuivi\service.log"
