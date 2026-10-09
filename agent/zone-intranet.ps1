# Place les sites GI-SUIVI dans la zone « Intranet local » du poste, pour tous ses utilisateurs.
# Sans cela, Edge/Chrome n'envoient pas le ticket Kerberos (le « badge » de la session Windows) et
# affichent une boîte de connexion que rien ne satisfait : l'application n'accepte que le ticket.
# installer-poste.ps1 fait déjà ceci ; ce script sert pour un poste où l'agent n'est pas installé,
# ou pour un poste installé avec un ancien kit.
#   .\zone-intranet.ps1            (PowerShell en administrateur)
# Ensuite : fermer complètement le navigateur et le rouvrir.
param(
    [string]$Domaine = 'giconseils.local',
    [string[]]$Sites = @('suivi', 'suivi-test')
)
$ErrorActionPreference = 'Stop'
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) { throw "A lancer en administrateur (clic droit sur PowerShell > Executer en tant qu'administrateur)." }

$base = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Internet Settings\ZoneMap"
# « Domains » : postes de travail ; « EscDomains » : serveurs avec la configuration de securite renforcee d'IE/Edge
foreach ($branche in 'Domains', 'EscDomains') {
    foreach ($site in $Sites) {
        $cle = Join-Path (Join-Path (Join-Path $base $branche) $Domaine) $site
        if (-not (Test-Path $cle)) { New-Item $cle -Force | Out-Null }
        Set-ItemProperty $cle -Name https -Value 1 -Type DWord
        Write-Host "Intranet local : https://$site.$Domaine ($branche)"
    }
}
Write-Host "`nTermine. Fermez completement Edge/Chrome puis rouvrez-le : la page https://suivi-test.$Domaine/moi doit s'ouvrir sans demander de mot de passe."
