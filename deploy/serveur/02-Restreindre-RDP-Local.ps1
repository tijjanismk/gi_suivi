<#
.SYNOPSIS
  P02 — Limite le Bureau à distance au réseau local et impose
  l'authentification au niveau du réseau (NLA). Ne désactive rien.

.USAGE
  Depuis la console du serveur (ou avec un accès physique possible),
  PowerShell en administrateur :
    .\02-Restreindre-RDP-Local.ps1                       # applique (réseau 192.168.2.0/24)
    .\02-Restreindre-RDP-Local.ps1 -Reseau 192.168.2.0/24,10.8.0.0/24   # LAN + plage VPN
    .\02-Restreindre-RDP-Local.ps1 -Annuler               # retour arrière complet

.PREALABLE
  Une sauvegarde de l'état du système doit exister (P01). Le script le
  vérifie et refuse de continuer sinon, sauf -IgnorerSauvegarde.
#>
param(
    [string[]]$Reseau = @("192.168.2.0/24"),
    [switch]$Annuler,
    [switch]$IgnorerSauvegarde,
    [string]$DossierConfig = "D:\SAUVEGARDES\config"
)

$ErrorActionPreference = "Stop"

# Groupe de règles : nom français ou anglais selon la langue du système
$groupe = "Bureau à distance"
if (-not (Get-NetFirewallRule -DisplayGroup $groupe -ErrorAction SilentlyContinue)) { $groupe = "Remote Desktop" }
$regles = Get-NetFirewallRule -DisplayGroup $groupe | Where-Object Enabled -eq True
if (-not $regles) { throw "Aucune règle de pare-feu active trouvée pour le groupe « $groupe »." }

$cleRdp = "HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp"
New-Item -ItemType Directory -Path $DossierConfig -Force | Out-Null
$export = Join-Path $DossierConfig "parefeu_rdp_avant.xml"

if ($Annuler) {
    Write-Host "Retour arrière : Bureau à distance accessible depuis toute adresse."
    $regles | Set-NetFirewallRule -RemoteAddress Any
    if (Test-Path "$DossierConfig\rdp_nla_avant.txt") {
        $nla = [int](Get-Content "$DossierConfig\rdp_nla_avant.txt")
        Set-ItemProperty $cleRdp -Name UserAuthentication -Value $nla
        Write-Host "NLA remis à sa valeur d'origine ($nla)."
    }
    Write-Host "Terminé."
    exit 0
}

# 0. Filet : une sauvegarde de l'état du système doit exister
if (-not $IgnorerSauvegarde) {
    $versions = & wbadmin get versions 2>&1 | Out-String
    if ($versions -notmatch "Heure de la sauvegarde|Backup time") {
        throw "Aucune sauvegarde Windows Server Backup trouvée. Faites P01 d'abord, ou relancez avec -IgnorerSauvegarde si vous l'assumez."
    }
    Write-Host "Sauvegarde trouvée : OK."
}

# 1. Sauvegarder l'état actuel des règles et du paramètre NLA
$regles | Export-Clixml $export
(Get-ItemProperty $cleRdp).UserAuthentication | Set-Content "$DossierConfig\rdp_nla_avant.txt"
Write-Host "État actuel sauvegardé dans $DossierConfig."

# 2. Restreindre
Write-Host "Restriction du Bureau à distance aux réseaux : $($Reseau -join ', ')"
$regles | Set-NetFirewallRule -RemoteAddress $Reseau
Set-ItemProperty $cleRdp -Name UserAuthentication -Value 1

# 3. Vérifier
Write-Host "`nRègles actives du groupe « $groupe » :"
$regles | ForEach-Object {
    $adr = ($_ | Get-NetFirewallAddressFilter).RemoteAddress -join ", "
    "{0,-55} {1}" -f $_.DisplayName, $adr
}
Write-Host "`nNLA : $((Get-ItemProperty $cleRdp).UserAuthentication)  (1 = exigée)"
Write-Host "`nTestez maintenant depuis un poste du bureau : mstsc /v:ad-serveur.giconseils.local"
Write-Host "Si la connexion échoue : .\02-Restreindre-RDP-Local.ps1 -Annuler"
