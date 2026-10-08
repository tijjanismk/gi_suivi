<#
.SYNOPSIS
  P04 — Crée dans l'annuaire : l'OU GIC, les six groupes de sécurité, le
  compte de service de l'application, et des comptes d'administration
  nominatifs. Idempotent : ne recrée pas ce qui existe.

.USAGE
    .\04-Comptes-et-groupes.ps1 -WhatIf                 # montre sans faire
    .\04-Comptes-et-groupes.ps1
    .\04-Comptes-et-groupes.ps1 -Administrateurs "tdiallo","okeita"   # crée adm-tdiallo, adm-okeita
    .\04-Comptes-et-groupes.ps1 -Membres @{ "GI-Direction"=@("ODICKO"); "GI-Offres"=@("OHASSANE","AMAIGA") }

.APRES
  - Le mot de passe du compte de service est dans C:\GIC\secrets\svc-application.txt
    (lisible par les administrateurs seulement). Le noter dans le gestionnaire
    de mots de passe du bureau, puis supprimer le fichier si souhaité.
  - Donner au compte de service le droit « Ouvrir une session en tant que
    service » : NSSM le fait lors de la création du service ; sinon
    secpol.msc > Stratégies locales > Attribution des droits utilisateur.
  - Cesser d'utiliser le compte Administrateur intégré au quotidien.
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [string[]]$Administrateurs = @(),
    [hashtable]$Membres = @{},
    [string]$CompteService = "svc-application"
)
$ErrorActionPreference = "Stop"
Import-Module ActiveDirectory
$journaux = "D:\SAUVEGARDES\journaux"; New-Item -ItemType Directory -Path $journaux -Force | Out-Null
Start-Transcript -Path "$journaux\04-comptes_$(Get-Date -Format yyyyMMdd_HHmm).log" | Out-Null

$domaine = Get-ADDomain
$dn      = $domaine.DistinguishedName          # DC=GICONSEILS,DC=LOCAL
$ouGic   = "OU=GIC,$dn"
$ouGrp   = "OU=Groupes,$ouGic"
$ouSvc   = "OU=Comptes de service,$ouGic"
$ouAdm   = "OU=Administration,$ouGic"

function Assurer-OU($nom, $parent) {
    $chemin = "OU=$nom,$parent"
    if (-not (Get-ADOrganizationalUnit -LDAPFilter "(ou=$nom)" -SearchBase $parent -SearchScope OneLevel -ErrorAction SilentlyContinue)) {
        if ($PSCmdlet.ShouldProcess($chemin, "Créer l'OU")) { New-ADOrganizationalUnit -Name $nom -Path $parent -ProtectedFromAccidentalDeletion $true }
    } else { Write-Host "OU existante : $chemin" }
}
Assurer-OU "GIC" $dn
Assurer-OU "Groupes" $ouGic
Assurer-OU "Comptes de service" $ouGic
Assurer-OU "Administration" $ouGic

# Groupes de sécurité (globaux). Description = usage, pour qu'on sache dans deux ans.
$groupes = [ordered]@{
    "GI-Direction"     = "Direction générale : tableaux de bord, validation, décisions"
    "GI-Direction-Lecture" = "Consultation seule des tableaux de bord GI-SUIVI (aucune action) — compte visionneuse"
    "GI-Offres"        = "Réponse aux avis : références, barèmes, justificatifs"
    "GI-Ingenieurs"    = "Personnel technique : missions, livrables"
    "GI-Administratif" = "Secrétariat et comptabilité : pièces administratives, finances"
    "GI-Terrain"       = "Agents de terrain : missions en cours (accès VPN)"
    "GI-Application"   = "Comptes de service de l'application (lecture des partages)"
}
foreach ($g in $groupes.Keys) {
    if (-not (Get-ADGroup -Filter "Name -eq '$g'" -ErrorAction SilentlyContinue)) {
        if ($PSCmdlet.ShouldProcess($g, "Créer le groupe")) {
            New-ADGroup -Name $g -SamAccountName $g -GroupScope Global -GroupCategory Security -Path $ouGrp -Description $groupes[$g]
        }
    } else { Write-Host "Groupe existant : $g" }
}

# Membres fournis en paramètre
foreach ($g in $Membres.Keys) {
    foreach ($m in $Membres[$g]) {
        if ($PSCmdlet.ShouldProcess("$m -> $g", "Ajouter")) { Add-ADGroupMember -Identity $g -Members $m -ErrorAction SilentlyContinue }
    }
}

# Compte de service
function Nouveau-MotDePasse($longueur = 28) {
    $car = ([char[]](48..57) + [char[]](65..90) + [char[]](97..122) + "-_.:!".ToCharArray())
    -join (1..$longueur | ForEach-Object { $car | Get-Random })
}
$secrets = "C:\GIC\secrets"
if (-not (Test-Path $secrets)) {
    New-Item -ItemType Directory -Path $secrets -Force | Out-Null
    & icacls $secrets /inheritance:r /grant:r "BUILTIN\Administrateurs:(OI)(CI)F" "SYSTEM:(OI)(CI)F" | Out-Null
}
if (-not (Get-ADUser -Filter "SamAccountName -eq '$CompteService'" -ErrorAction SilentlyContinue)) {
    $mdp = Nouveau-MotDePasse
    if ($PSCmdlet.ShouldProcess($CompteService, "Créer le compte de service")) {
        New-ADUser -Name $CompteService -SamAccountName $CompteService -UserPrincipalName "$CompteService@$($domaine.DNSRoot)" `
            -Path $ouSvc -Description "Compte de service GIC (IIS, Uvicorn, tâches planifiées)" `
            -AccountPassword (ConvertTo-SecureString $mdp -AsPlainText -Force) -Enabled $true `
            -PasswordNeverExpires $true -CannotChangePassword $true
        Add-ADGroupMember -Identity "GI-Application" -Members $CompteService
        Set-Content -Path "$secrets\$CompteService.txt" -Value "GICONSEILS\$CompteService`r`n$mdp" -Encoding ASCII
        & icacls "$secrets\$CompteService.txt" /inheritance:r /grant:r "BUILTIN\Administrateurs:F" "SYSTEM:F" | Out-Null
        Write-Host "Compte de service créé ; mot de passe dans $secrets\$CompteService.txt"
    }
} else { Write-Host "Compte de service existant : $CompteService" }

# Comptes d'administration nominatifs : adm-<login>, membres de Admins du domaine
foreach ($login in $Administrateurs) {
    $adm = "adm-$login"
    if (-not (Get-ADUser -Filter "SamAccountName -eq '$adm'" -ErrorAction SilentlyContinue)) {
        $mdp = Nouveau-MotDePasse 20
        if ($PSCmdlet.ShouldProcess($adm, "Créer le compte d'administration")) {
            New-ADUser -Name $adm -SamAccountName $adm -UserPrincipalName "$adm@$($domaine.DNSRoot)" -Path $ouAdm `
                -Description "Compte d'administration nominatif de $login" `
                -AccountPassword (ConvertTo-SecureString $mdp -AsPlainText -Force) -Enabled $true -ChangePasswordAtLogon $true
            Add-ADGroupMember -Identity "Admins du domaine" -Members $adm
            Write-Host "Compte $adm créé. Mot de passe initial (à changer à la première ouverture) : $mdp"
        }
    } else { Write-Host "Compte existant : $adm" }
}

Write-Host "`nRécapitulatif :"
Get-ADGroup -SearchBase $ouGrp -Filter * | ForEach-Object {
    "  {0,-18} {1} membre(s)" -f $_.Name, (Get-ADGroupMember $_ | Measure-Object).Count
}
Stop-Transcript | Out-Null
