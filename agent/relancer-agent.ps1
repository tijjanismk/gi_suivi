# Relance l'agent de la session courante, proprement : il écrit d'abord ses segments en attente
# dans le tampon (rien n'est perdu), puis le service GiSuivi le relance en moins de 15 s avec un
# compteur d'essais remis à zéro — utile quand l'icône reste grise « hors réseau » alors que le
# serveur est de nouveau joignable (après un échec, l'agent espace ses essais jusqu'à 30 min).
#   .\relancer-agent.ps1        (PowerShell, dans la session de la personne ; administrateur non requis)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'arreter-agent.ps1')
Stop-AgentProprement
$fin = (Get-Date).AddSeconds(30)
while (-not (Get-Process gisuivi-agent -ErrorAction SilentlyContinue) -and (Get-Date) -lt $fin) { Start-Sleep -Milliseconds 500 }
if (Get-Process gisuivi-agent -ErrorAction SilentlyContinue) {
    Write-Host "Agent relance par le service. Il envoie ses segments en attente dans les 3 minutes ; l'icone passe au vert des que le serveur a accepte un lot."
} else {
    Write-Warning "L'agent n'est pas revenu en 30 s : verifier le service GiSuivi (services.msc) et C:\ProgramData\GiSuivi\service.log."
}
Write-Host "Journal : $env:LOCALAPPDATA\GiSuivi\agent.log"
