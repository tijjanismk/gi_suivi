<#
.SYNOPSIS
  S07 (a) — Enregistrements DNS des sites de l'application et SPN Kerberos
  sur le compte de service. Sans SPN correct, IIS retombe en NTLM ou demande
  un mot de passe.

.USAGE
    .\06-DNS-SPN.ps1 -WhatIf
    .\06-DNS-SPN.ps1
    .\06-DNS-SPN.ps1 -Noms suivi,suivi-test -AdresseIP 192.168.2.250 -CompteService svc-application
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [string[]]$Noms = @("suivi", "suivi-test"),
    [string]$AdresseIP = "192.168.2.250",
    [string]$CompteService = "svc-application"
)
$ErrorActionPreference = "Stop"
Import-Module ActiveDirectory; Import-Module DnsServer
$zone = (Get-ADDomain).DNSRoot     # giconseils.local
$dom  = (Get-ADDomain).NetBIOSName

foreach ($n in $Noms) {
    $existe = Get-DnsServerResourceRecord -ZoneName $zone -Name $n -RRType A -ErrorAction SilentlyContinue
    if (-not $existe) {
        if ($PSCmdlet.ShouldProcess("$n.$zone -> $AdresseIP", "Créer l'enregistrement A")) {
            Add-DnsServerResourceRecordA -ZoneName $zone -Name $n -IPv4Address $AdresseIP -TimeToLive 01:00:00
        }
    } else { Write-Host "DNS existant : $n.$zone -> $($existe.RecordData.IPv4Address)" }

    # SPN HTTP/<nom complet> et HTTP/<nom court> sur le compte de service
    foreach ($spn in "HTTP/$n.$zone", "HTTP/$n") {
        $porteur = & setspn -Q $spn 2>$null | Select-String "CN=" | ForEach-Object { $_.ToString().Trim() }
        if ($porteur -and ($porteur -notmatch $CompteService)) {
            Write-Warning "$spn est déjà enregistré sur un autre compte : $porteur. Kerberos échouera tant que ce doublon existe (setspn -D)."
        } elseif (-not $porteur) {
            if ($PSCmdlet.ShouldProcess("$spn -> $dom\$CompteService", "Enregistrer le SPN")) { & setspn -S $spn "$dom\$CompteService" | Out-Null }
        } else { Write-Host "SPN existant : $spn" }
    }
}

Write-Host "`nSPN du compte $CompteService :"
& setspn -L "$dom\$CompteService"
Write-Host "`nTest depuis un poste du domaine : nslookup suivi.$zone  puis, après 08, https://suivi.$zone/identite/qui-suis-je"
Write-Host "Vérifier Kerberos côté poste : klist  (un ticket HTTP/suivi.$zone doit apparaître après la première visite)."
