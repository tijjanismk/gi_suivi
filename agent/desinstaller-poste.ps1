# Retire l'agent GI-Suivi et son service de CE poste (pilote, avant le MSI G07). En administrateur.
#   .\desinstaller-poste.ps1            # garde les données (%ProgramData%\GiSuivi)
# Les données ne sont jamais supprimées par ce script : le tampon peut contenir des segments non envoyés.
param([string]$Cible = (Join-Path $env:ProgramFiles 'GI-CONSEILS\GiSuivi'))
$ErrorActionPreference = 'Stop'
$service = 'GiSuivi'

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { throw "A lancer en administrateur." }

if (Get-Service $service -ErrorAction SilentlyContinue) {
    Stop-Service $service -Force
    & sc.exe delete $service | Out-Null
    Write-Host "Service $service supprime."
}
. (Join-Path $PSScriptRoot 'arreter-agent.ps1')
Stop-AgentProprement
if (Test-Path $Cible) { Remove-Item $Cible -Recurse -Force -Confirm:$false; Write-Host "Supprime : $Cible" }
Write-Host "Donnees conservees : $env:ProgramData\GiSuivi"
