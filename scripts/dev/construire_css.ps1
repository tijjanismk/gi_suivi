# Compile le CSS du projet (ADR 0005, point 4) avec l'outil Tailwind autonome, sur le poste de
# développement seulement. Le résultat (interface/static/css/gic.css) est versionné : le serveur
# ne compile rien.
#   .\scripts\dev\construire_css.ps1            # une fois
#   .\scripts\dev\construire_css.ps1 -Surveiller # recompile à chaque modification de gabarit
param(
    [string]$Tailwind = 'C:\dev\outils\tailwind\tailwindcss.exe',
    [switch]$Surveiller
)
$ErrorActionPreference = 'Stop'
$racine = Resolve-Path (Join-Path $PSScriptRoot '..\..')
if (-not (Test-Path $Tailwind)) {
    throw "Outil Tailwind introuvable : $Tailwind (tailwindcss-windows-x64.exe, releases GitHub tailwindlabs/tailwindcss, v4)."
}
$entree = Join-Path $racine 'interface\tailwind\entree.css'
$sortie = Join-Path $racine 'interface\static\css\gic.css'
$args = @('-i', $entree, '-o', $sortie, '--minify')
if ($Surveiller) { $args += '--watch' }
& $Tailwind @args
if ($LASTEXITCODE -ne 0) { throw "Tailwind : echec ($LASTEXITCODE)." }
Write-Host ("CSS : {0} ({1:N1} Ko)" -f $sortie, ((Get-Item $sortie).Length / 1KB))
