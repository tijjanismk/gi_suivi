<#
.SYNOPSIS
  Poste du développeur — Produit l'archive d'un tag Git et la copie sur le
  partage, prête à être installée par deploy\installer.ps1.

.USAGE
    .\deploy\publier.ps1 -Tag v0.3.0
    .\deploy\publier.ps1 -Tag v0.3.0 -Destination \\AD-SERVEUR\GIC\deploy\app
    .\deploy\publier.ps1 -Branche main          # archive de l'état courant de main (tests et pilote seulement)
#>
param(
    [string]$Tag,
    [string]$Branche,
    [string]$Destination = "\\AD-SERVEUR\GIC\deploy\app"
)
$ErrorActionPreference = "Stop"
$racine = Split-Path $PSScriptRoot -Parent
Set-Location $racine

if (-not $Tag -and -not $Branche) { throw "Indiquez -Tag vX.Y.Z (production) ou -Branche (test)." }
$ref = if ($Tag) { $Tag } else { $Branche }
if ($Tag -and -not (git tag -l $Tag)) { throw "Le tag $Tag n'existe pas. Créez-le : git tag -a $Tag -m 'Version $Tag' ; git push --tags" }
if (git status --porcelain) { Write-Warning "Des modifications non commitées existent ; l'archive ne les contiendra pas (git archive)." }

$nom = if ($Tag) { "gic-$Tag.zip" } else { "gic-$Branche-$(Get-Date -Format yyyyMMdd_HHmm).zip" }
$local = Join-Path $env:TEMP $nom
git archive --format=zip --prefix=gic/ -o $local $ref
if (-not (Test-Path $local)) { throw "git archive a échoué." }

# Fichier de version lu par installer.ps1 et affiché par /api/sante
$version = @{ ref = $ref; commit = (git rev-parse --short $ref); date = (Get-Date -Format s); auteur = (git config user.name) } | ConvertTo-Json
$tmp = Join-Path $env:TEMP "gic_version"; New-Item -ItemType Directory -Path "$tmp\gic" -Force | Out-Null
$version | Set-Content "$tmp\gic\VERSION.json" -Encoding UTF8
Compress-Archive -Path "$tmp\gic" -DestinationPath $local -Update
Remove-Item $tmp -Recurse -Force

New-Item -ItemType Directory -Path $Destination -Force | Out-Null
Copy-Item $local (Join-Path $Destination $nom) -Force
Write-Host "Archive publiée : $(Join-Path $Destination $nom)"
Write-Host "Sur le serveur : .\deploy\installer.ps1 -Env test -Zip `"$(Join-Path $Destination $nom)`""
