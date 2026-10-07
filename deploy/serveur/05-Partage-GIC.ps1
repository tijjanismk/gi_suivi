<#
.SYNOPSIS
  P06 — Crée D:\GIC, son arborescence, le partage SMB « GIC » et les droits
  NTFS par groupe (matrice de l'état des lieux, section 6.2). Ne déplace
  aucun fichier existant : le déplacement est un geste humain (chantier 1 de
  la phase 0), fait dossier par dossier.

.USAGE
    .\05-Partage-GIC.ps1 -WhatIf
    .\05-Partage-GIC.ps1
    .\05-Partage-GIC.ps1 -Racine E:\GIC    # autre disque

.PREALABLE
  04-Comptes-et-groupes.ps1 exécuté (les groupes GI-* existent).
#>
[CmdletBinding(SupportsShouldProcess)]
param([string]$Racine = "D:\GIC", [string]$NomPartage = "GIC")
$ErrorActionPreference = "Stop"
$journaux = "D:\SAUVEGARDES\journaux"; New-Item -ItemType Directory -Path $journaux -Force | Out-Null
Start-Transcript -Path "$journaux\05-partage_$(Get-Date -Format yyyyMMdd_HHmm).log" | Out-Null

$dom = (Get-ADDomain).NetBIOSName
foreach ($g in "GI-Direction","GI-Offres","GI-Ingenieurs","GI-Administratif","GI-Terrain","GI-Application") {
    if (-not (Get-ADGroup -Filter "Name -eq '$g'" -ErrorAction SilentlyContinue)) { throw "Groupe $g absent : lancez 04 d'abord." }
}

# Arborescence
$dossiers = @(
    "REFERENCES\00_REGISTRE", "REFERENCES\01_SOURCES", "REFERENCES\02_JUSTIFICATIFS", "REFERENCES\03_A_CLASSER",
    "MISSIONS_EN_COURS", "AVIS\2026", "EXPERTS", "ADMINISTRATIF\2026", "VEILLE", "UTILISATEURS", "_ANCIEN",
    "deploy\agent"
)
foreach ($d in $dossiers) {
    $p = Join-Path $Racine $d
    if (-not (Test-Path $p)) { if ($PSCmdlet.ShouldProcess($p, "Créer")) { New-Item -ItemType Directory -Path $p -Force | Out-Null } }
}

# Droits NTFS : M = modification, RX = lecture/exécution, (OI)(CI) = s'applique aux fichiers et sous-dossiers
# Colonnes : Direction, Offres, Ingenieurs, Administratif, Terrain, Application
$matrice = [ordered]@{
    "REFERENCES"        = @("RX","M","RX","RX","-","RX")
    "MISSIONS_EN_COURS" = @("M","RX","M","RX","M","RX")
    "AVIS"              = @("M","M","RX","RX","-","RX")
    "EXPERTS"           = @("M","M","RX","RX","-","RX")
    "ADMINISTRATIF"     = @("M","RX","-","M","-","RX")
    "VEILLE"            = @("M","M","RX","-","-","RX")
    "UTILISATEURS"      = @("RX","RX","RX","RX","RX","-")
    "_ANCIEN"           = @("M","RX","RX","RX","-","-")
    "deploy"            = @("RX","RX","RX","RX","RX","RX")
}
$groupes = "GI-Direction","GI-Offres","GI-Ingenieurs","GI-Administratif","GI-Terrain","GI-Application"

function Appliquer-Droits($chemin, $droits) {
    if (-not $PSCmdlet.ShouldProcess($chemin, "Droits NTFS : " + ($droits -join ","))) { return }
    # Couper l'héritage, retirer Utilisateurs/Tout le monde, garder Administrateurs et SYSTEM
    & icacls $chemin /inheritance:d | Out-Null
    & icacls $chemin /remove:g "Utilisateurs" "BUILTIN\Utilisateurs" "Tout le monde" "Utilisateurs authentifiés" 2>$null | Out-Null
    & icacls $chemin /grant:r "BUILTIN\Administrateurs:(OI)(CI)F" "SYSTEM:(OI)(CI)F" | Out-Null
    for ($i = 0; $i -lt $groupes.Count; $i++) {
        $d = $droits[$i]
        if ($d -eq "-") { continue }
        & icacls $chemin /grant:r "$dom\$($groupes[$i]):(OI)(CI)$d" | Out-Null
    }
}

# Racine : lecture pour tous les groupes (pour traverser), rien d'autre
if ($PSCmdlet.ShouldProcess($Racine, "Droits racine")) {
    & icacls $Racine /inheritance:r /grant:r "BUILTIN\Administrateurs:(OI)(CI)F" "SYSTEM:(OI)(CI)F" | Out-Null
    foreach ($g in $groupes) { & icacls $Racine /grant:r "$dom\${g}:RX" | Out-Null }   # ce dossier seulement, pas (OI)(CI)
}
foreach ($d in $matrice.Keys) { Appliquer-Droits (Join-Path $Racine $d) $matrice[$d] }

# Exception : les justificatifs ne se modifient pas, ils se remplacent (Offres seulement)
$just = Join-Path $Racine "REFERENCES\02_JUSTIFICATIFS"
if ($PSCmdlet.ShouldProcess($just, "Lecture seule sauf GI-Offres")) {
    & icacls $just /inheritance:d | Out-Null
    & icacls $just /grant:r "$dom\GI-Offres:(OI)(CI)M" "$dom\GI-Direction:(OI)(CI)RX" "$dom\GI-Ingenieurs:(OI)(CI)RX" "$dom\GI-Administratif:(OI)(CI)RX" "$dom\GI-Application:(OI)(CI)RX" | Out-Null
}

# Partage SMB : pas de « Tout le monde », énumération basée sur l'accès, chiffrement
if (-not (Get-SmbShare -Name $NomPartage -ErrorAction SilentlyContinue)) {
    if ($PSCmdlet.ShouldProcess("\\$env:COMPUTERNAME\$NomPartage", "Créer le partage")) {
        New-SmbShare -Name $NomPartage -Path $Racine -Description "Documents du bureau GI-CONSEILS" `
            -FolderEnumerationMode AccessBased -EncryptData $true -CachingMode None `
            -ChangeAccess ($groupes | ForEach-Object { "$dom\$_" }) -FullAccess "BUILTIN\Administrateurs" | Out-Null
    }
} else {
    Write-Host "Partage existant : $NomPartage (droits de partage non modifiés)."
}

# Audit des suppressions sur REFERENCES (nécessite la stratégie « Auditer l'accès aux objets » : voir note)
if ($PSCmdlet.ShouldProcess((Join-Path $Racine "REFERENCES"), "Audit des suppressions")) {
    $acl = Get-Acl (Join-Path $Racine "REFERENCES")
    $regle = New-Object System.Security.AccessControl.FileSystemAuditRule("Tout le monde", "Delete,DeleteSubdirectoriesAndFiles", "ContainerInherit,ObjectInherit", "None", "Success")
    $acl.AddAuditRule($regle); Set-Acl (Join-Path $Racine "REFERENCES") $acl
    & auditpol /set /subcategory:"Système de fichiers" /success:enable 2>$null | Out-Null
}

Write-Host "`nPartage : \\$env:COMPUTERNAME\$NomPartage"
Get-SmbShareAccess -Name $NomPartage -ErrorAction SilentlyContinue | Format-Table -AutoSize
Write-Host "Droits NTFS des dossiers de premier niveau :"
Get-ChildItem $Racine -Directory | ForEach-Object { "`n[$($_.Name)]"; (& icacls $_.FullName | Select-String "GI-|Administrateurs" ) }
Write-Host "`nÉTAPE SUIVANTE (à la main) : déplacer les dossiers existants dans la nouvelle structure selon docs/phase0-collecte.md, chantier 1. Les anciens partages restent en place six semaines."
Stop-Transcript | Out-Null
