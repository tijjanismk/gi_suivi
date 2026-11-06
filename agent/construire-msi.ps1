# Construit le MSI de l'agent (G07) à partir de dist\gisuivi-agent\ (lancer .\construire.ps1 -Tester avant).
#   .\construire-msi.ps1 -Wix C:\dev\outils\wix314
# -Wix : dossier des binaires WiX 3 (heat.exe, candle.exe, light.exe), sans installation.
# Résultat : dist\GiSuivi-<version>.msi, NON SIGNÉ tant qu'il n'y a pas de certificat de signature de code (A7).
param([Parameter(Mandatory)][string]$Wix)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

$version = (Select-String -Path gisuivi_agent\__init__.py -Pattern '__version__\s*=\s*"([^"]+)"').Matches[0].Groups[1].Value
$source = Join-Path $PSScriptRoot 'dist\gisuivi-agent'
if (-not (Test-Path "$source\gisuivi-agent.exe")) { throw "Introuvable : $source\gisuivi-agent.exe. Lancer d'abord .\construire.ps1 -Tester." }
# Pont MCP de Claude Desktop (ADR 0016), construit par construire.ps1 à côté de l'agent
foreach ($f in "pont-mcp.exe", "_pont", "claude_desktop_config.exemple.json") {
    if (-not (Test-Path "$source\$f")) { throw "Introuvable : $source\$f (pont MCP). Relancer .\construire.ps1 -Tester." }
}
$obj = Join-Path $PSScriptRoot 'build\msi'
New-Item -ItemType Directory -Force $obj | Out-Null

# 1. Moissonner _internal (plusieurs centaines de fichiers PyInstaller)
& "$Wix\heat.exe" dir "$source\_internal" -nologo -cg FichiersInternes -dr INTERNAL -srd -sreg -gg -g1 -ag -var var.SourceInternes -platform x64 -out "$obj\Internes.wxs"
if ($LASTEXITCODE -ne 0) { throw "heat : echec." }
# 1 bis. Moissonner _pont (bibliotheques du pont MCP) ; identifiants prefixes « pont_ » : memes noms que dans _internal
& "$Wix\heat.exe" dir "$source\_pont" -nologo -cg FichiersPont -dr PONT -srd -sreg -gg -g1 -ag -var var.SourcePont -platform x64 -t msi\prefixer-pont.xslt -out "$obj\Pont.wxs"
if ($LASTEXITCODE -ne 0) { throw "heat (_pont) : echec." }
# 2. Compiler
& "$Wix\candle.exe" -nologo -arch x64 -ext WixUtilExtension "-dVersion=$version" "-dSource=$source" "-dSourceInternes=$source\_internal" "-dSourcePont=$source\_pont" -out "$obj\\" msi\Produit.wxs "$obj\Internes.wxs" "$obj\Pont.wxs"
if ($LASTEXITCODE -ne 0) { throw "candle : echec." }
# 3. Lier
$msi = Join-Path $PSScriptRoot "dist\GiSuivi-$version.msi"
& "$Wix\light.exe" -nologo -ext WixUtilExtension -cultures:fr-FR -spdb -out $msi "$obj\Produit.wixobj" "$obj\Internes.wixobj" "$obj\Pont.wixobj"
if ($LASTEXITCODE -ne 0) { throw "light : echec." }
Write-Host "MSI : $msi (non signe)"
Write-Host "Installer   : msiexec /i `"$msi`" /qn /l*v `"$obj\installation.log`""
Write-Host "Desinstaller: msiexec /x `"$msi`" /qn /l*v `"$obj\desinstallation.log`""
