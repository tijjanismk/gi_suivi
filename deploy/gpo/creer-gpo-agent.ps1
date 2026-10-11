<#
.SYNOPSIS
  Crée ou met à jour la GPO « GI-Suivi - Agent » qui installe l'agent sur les postes, sans MSI :
  un script de démarrage de l'ordinateur lit le kit publié dans SYSVOL et n'installe ou ne met à
  jour que si la version change.

  Ne vise QUE les ordinateurs du groupe « GI-Postes-Suivi » (filtrage de sécurité) : tant qu'un
  poste n'est pas dans ce groupe, la GPO ne fait rien chez lui. Ajoute seulement : un groupe, une
  GPO, un lien ; aucune GPO, aucun groupe existant n'est modifié.

.USAGE (contrôleur de domaine, PowerShell administrateur)
    .\creer-gpo-agent.ps1 -Kit \\AD-SERVEUR\DICKO\GiSuivi-agent-0.2.3-poste.zip
    .\creer-gpo-agent.ps1 -Kit ...\GiSuivi-agent-0.2.4-poste.zip     # mise à jour : même commande
    .\creer-gpo-agent.ps1 -Kit ... -WhatIf                             # montre sans faire

.ENSUITE
    Ajouter un poste : Utilisateurs et ordinateurs AD → GIC\Groupes\GI-Postes-Suivi → Ajouter
    l'ORDINATEUR (type d'objet : Ordinateurs). Puis redémarrer le poste (deux fois si besoin :
    l'appartenance au groupe n'est lue qu'au démarrage). Journal sur le poste :
    C:\ProgramData\GiSuivi\installation-gpo.log
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)][string]$Kit,                         # le zip produit par agent\preparer-kit.ps1
    [string]$Certificat = "C:\GIC\deploy\gic-serveur.cer",
    [string]$NomGpo = "GI-Suivi - Agent",
    [string]$Groupe = "GI-Postes-Suivi"
)
$ErrorActionPreference = "Stop"
Import-Module ActiveDirectory; Import-Module GroupPolicy
$domaine = Get-ADDomain; $dns = $domaine.DNSRoot; $dn = $domaine.DistinguishedName
if (-not (Test-Path $Kit)) { throw "Kit introuvable : $Kit" }
if (-not (Test-Path $Certificat)) { throw "Certificat introuvable : $Certificat (serveur\08-Python-IIS.ps1 -AutoSigne)." }

# 1. Groupe d'ordinateurs ciblés
$ouGroupes = "OU=Groupes,OU=GIC,$dn"
if (-not (Get-ADGroup -Filter "Name -eq '$Groupe'" -ErrorAction SilentlyContinue)) {
    if ($PSCmdlet.ShouldProcess($Groupe, "Créer le groupe d'ordinateurs")) {
        New-ADGroup -Name $Groupe -SamAccountName $Groupe -GroupScope Global -GroupCategory Security -Path $ouGroupes `
            -Description "Ordinateurs qui reçoivent l'agent GI-Suivi par la GPO « $NomGpo »"
        Write-Host "Groupe $Groupe créé dans $ouGroupes."
    }
} else { Write-Host "Groupe existant : $Groupe" }

# 2. GPO
$gpo = Get-GPO -Name $NomGpo -ErrorAction SilentlyContinue
if (-not $gpo) {
    if (-not $PSCmdlet.ShouldProcess($NomGpo, "Créer la GPO")) { return }
    $gpo = New-GPO -Name $NomGpo -Comment "Installe ou met à jour l'agent GI-Suivi au démarrage (script). Ciblage : groupe $Groupe."
    Write-Host "GPO créée : $NomGpo {$($gpo.Id)}"
} else { Write-Host "GPO existante : $NomGpo {$($gpo.Id)}" }

# 3. Filtrage de sécurité : lecture pour les ordinateurs du domaine (nécessaire depuis MS16-072),
#    application pour le seul groupe ciblé ; plus d'application pour « Utilisateurs authentifiés »
$sidDomaine = $domaine.DomainSID.Value
$nomOrdinateurs = (New-Object Security.Principal.SecurityIdentifier "$sidDomaine-515").Translate([Security.Principal.NTAccount]).Value.Split('\')[-1]
$nomAuthentifies = (New-Object Security.Principal.SecurityIdentifier "S-1-5-11").Translate([Security.Principal.NTAccount]).Value.Split('\')[-1]
if ($PSCmdlet.ShouldProcess($NomGpo, "Filtrage de sécurité : $Groupe seulement")) {
    Set-GPPermission -Guid $gpo.Id -TargetName $Groupe -TargetType Group -PermissionLevel GpoApply | Out-Null
    Set-GPPermission -Guid $gpo.Id -TargetName $nomOrdinateurs -TargetType Group -PermissionLevel GpoRead | Out-Null
    Set-GPPermission -Guid $gpo.Id -TargetName $nomAuthentifies -TargetType Group -PermissionLevel GpoRead -Replace | Out-Null
    Write-Host "Filtrage : application pour $Groupe ; lecture pour $nomOrdinateurs et $nomAuthentifies."
}

# 4. Réglages par stratégie (registre) : attendre le réseau au démarrage (SYSVOL joignable pour le
#    script), authentification Windows silencieuse dans Edge et Chrome pour *.giconseils.local
if ($PSCmdlet.ShouldProcess($NomGpo, "Valeurs de registre")) {
    Set-GPRegistryValue -Guid $gpo.Id -Key "HKLM\Software\Policies\Microsoft\Windows NT\CurrentVersion\Winlogon" -ValueName SyncForegroundPolicy -Type DWord -Value 1 | Out-Null
    Set-GPRegistryValue -Guid $gpo.Id -Key "HKLM\Software\Policies\Microsoft\Edge" -ValueName AuthServerAllowlist -Type String -Value "*.$dns" | Out-Null
    Set-GPRegistryValue -Guid $gpo.Id -Key "HKLM\Software\Policies\Google\Chrome" -ValueName AuthServerAllowlist -Type String -Value "*.$dns" | Out-Null
    Write-Host "Stratégies : attente du réseau au démarrage ; AuthServerAllowlist = *.$dns (Edge, Chrome)."
}

# 5. Kit et script de démarrage dans le dossier SYSVOL de la GPO
$racineGpo = "\\$dns\SYSVOL\$dns\Policies\{$($gpo.Id)}"
$scripts = "$racineGpo\Machine\Scripts"
$demarrage = "$scripts\Startup"
if ($PSCmdlet.ShouldProcess($demarrage, "Publier le kit et le script de démarrage")) {
    $tmp = Join-Path $env:TEMP "gisuivi-kit-gpo"
    if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
    Expand-Archive -Path $Kit -DestinationPath $tmp
    Copy-Item $Certificat (Join-Path $tmp "gic-serveur.cer") -Force
    New-Item -ItemType Directory -Force "$demarrage\GiSuivi" | Out-Null
    & robocopy.exe $tmp "$demarrage\GiSuivi" /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "Copie du kit vers SYSVOL en échec (robocopy $LASTEXITCODE)." }
    foreach ($f in "demarrage-gpo.cmd", "demarrage-gpo.ps1") {
        $src = Join-Path $tmp $f
        if (-not (Test-Path $src)) { throw "$f absent du kit : régénérer le kit (agent\preparer-kit.ps1)." }
        Copy-Item $src $demarrage -Force
    }
    Remove-Item $tmp -Recurse -Force
    # scripts.ini : en Unicode (UTF-16 LE), comme l'écrit la console de gestion des stratégies
    $ini = "[Startup]`r`n0CmdLine=demarrage-gpo.cmd`r`n0Parameters=`r`n"
    [IO.File]::WriteAllText("$scripts\scripts.ini", $ini, [Text.Encoding]::Unicode)
    (Get-Item "$scripts\scripts.ini" -Force).Attributes = 'Hidden'
    Write-Host "Kit publié dans $demarrage\GiSuivi ; script de démarrage : demarrage-gpo.cmd"

    # Déclarer l'extension « Scripts » sur l'objet GPO et augmenter sa version (côté ordinateur)
    $objet = "CN={$($gpo.Id)},CN=Policies,CN=System,$dn"
    $ad = Get-ADObject $objet -Properties gPCMachineExtensionNames, versionNumber
    $paires = @()
    if ($ad.gPCMachineExtensionNames) { $paires = [regex]::Matches($ad.gPCMachineExtensionNames, '\[[^\]]+\]') | ForEach-Object { $_.Value } }
    $scriptsCse = "[{42B5FAAE-6536-11D2-AE5A-0000F87571E3}{40B6664F-4972-11D1-A7CA-0000F87571E3}]"
    if ($paires -notcontains $scriptsCse) { $paires += $scriptsCse }
    $extensions = ($paires | Sort-Object -Unique) -join ""
    $version = [int]$ad.versionNumber + 1
    Set-ADObject $objet -Replace @{ gPCMachineExtensionNames = $extensions; versionNumber = $version }
    $gpt = "$racineGpo\GPT.INI"
    $contenu = if (Test-Path $gpt) { Get-Content $gpt -Raw } else { "[General]`r`n" }
    if ($contenu -match '(?m)^Version=\d+') { $contenu = $contenu -replace '(?m)^Version=\d+', "Version=$version" } else { $contenu = $contenu.TrimEnd() + "`r`nVersion=$version`r`n" }
    [IO.File]::WriteAllText($gpt, $contenu, [Text.Encoding]::ASCII)
    Write-Host "GPO version $version (extension Scripts déclarée)."
}

# 6. Lien à la racine du domaine (le filtrage de sécurité limite l'effet au seul groupe)
$liens = @((Get-GPInheritance -Target $dn).GpoLinks | ForEach-Object { $_.DisplayName })
if ($liens -notcontains $NomGpo) {
    if ($PSCmdlet.ShouldProcess($dn, "Lier la GPO")) { New-GPLink -Guid $gpo.Id -Target $dn -LinkEnabled Yes | Out-Null; Write-Host "GPO liée à $dn." }
} else { Write-Host "Lien existant sur $dn." }

Write-Host "`nTerminé. Pour équiper un poste : ajouter l'ORDINATEUR au groupe $Groupe, puis redémarrer le poste."
Write-Host "Contrôle sur le poste : gpresult /r /scope computer (la GPO « $NomGpo » doit figurer) ; journal C:\ProgramData\GiSuivi\installation-gpo.log"
