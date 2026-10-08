# Prépare le kit d'installation manuelle d'un poste pilote (sans GPO, sans MSI) :
# construit l'agent (tests compris), puis assemble dans une archive tout ce qu'il faut copier
# sur le poste : dist\gisuivi-agent\, les scripts d'installation, la configuration à poser, le
# mode d'emploi.
#   .\preparer-kit.ps1                                  # config = config.exemple.json
#   .\preparer-kit.ps1 -Config .\config-pilote.json     # config du pilote (racines, url_api)
#   .\preparer-kit.ps1 -SansConstruction                # réutilise dist\ tel quel
param(
    [string]$Config = (Join-Path $PSScriptRoot 'config.exemple.json'),
    [string]$Destination = 'C:\dev\livraisons\agent',
    [switch]$SansConstruction
)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

if (-not $SansConstruction) { .\construire.ps1 -Tester | Select-Object -Last 3 }
if (-not (Test-Path .\dist\gisuivi-agent\gisuivi-agent.exe)) { throw "dist\gisuivi-agent\gisuivi-agent.exe introuvable : lancer .\construire.ps1 -Tester." }
if (-not (Test-Path $Config)) { throw "Configuration introuvable : $Config" }

$version = (Select-String -Path gisuivi_agent\__init__.py -Pattern '__version__\s*=\s*"([^"]+)"').Matches[0].Groups[1].Value
$kit = Join-Path $env:TEMP "GiSuivi-agent-$version-poste"
if (Test-Path $kit) { Remove-Item $kit -Recurse -Force }
New-Item -ItemType Directory -Path $kit | Out-Null
& robocopy.exe .\dist\gisuivi-agent "$kit\dist\gisuivi-agent" /E /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "Copie de dist en echec." }
Copy-Item .\installer-poste.ps1, .\desinstaller-poste.ps1, .\arreter-agent.ps1, .\LISEZMOI-poste.md, .\CONTROLE.md $kit
# La configuration livrée est écrite sans BOM : l'agent la lit telle quelle
$json = Get-Content $Config -Raw -Encoding UTF8
[IO.File]::WriteAllText("$kit\config.json", $json, (New-Object Text.UTF8Encoding $false))

New-Item -ItemType Directory -Force $Destination | Out-Null
$zip = Join-Path $Destination "GiSuivi-agent-$version-poste.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path "$kit\*" -DestinationPath $zip
Remove-Item $kit -Recurse -Force
Write-Host ("Kit : {0} ({1:N1} Mo)" -f $zip, ((Get-Item $zip).Length / 1MB))
Write-Host "Sur le poste : decompresser, puis en administrateur : .\installer-poste.ps1   (voir LISEZMOI-poste.md)"
