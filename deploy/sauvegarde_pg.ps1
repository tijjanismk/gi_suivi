<#
.SYNOPSIS
  Serveur — Sauvegarde PostgreSQL : pg_dump -Fc des bases gic et gic_test vers
  D:\SAUVEGARDES\pg\, 14 jours conservés. Lancé chaque nuit à 01:00 par la tâche
  « GIC - Sauvegarde PostgreSQL » (taches.ps1), sous SYSTEM ; se lance aussi à la main.

.USAGE
    .\sauvegarde_pg.ps1
    .\sauvegarde_pg.ps1 -Bases gic -Conserver 30

.RESTAURATION (test trimestriel, docs/exploitation.md § 3)
    createdb -U postgres -h localhost gic_restauration
    pg_restore -U postgres -h localhost -d gic_restauration D:\SAUVEGARDES\pg\gic_20261008_0100.dump
    psql -U postgres -h localhost -d gic_restauration -c "select count(*) from suivi_segment;"
    dropdb -U postgres -h localhost gic_restauration
#>
param(
    [string[]]$Bases = @("gic", "gic_test"),
    [string]$Destination = "D:\SAUVEGARDES\pg",
    [int]$Conserver = 14,
    [string]$Prefixe = "C:\Program Files\PostgreSQL\17",
    [string]$Secret = "C:\GIC\secrets\pg.env"
)
$ErrorActionPreference = "Stop"
New-Item -ItemType Directory -Path $Destination -Force | Out-Null
$journal = Join-Path $Destination "sauvegarde.log"
function Ecrire($texte) { $ligne = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $texte"; Write-Host $ligne; Add-Content $journal $ligne -Encoding UTF8 }

$pgDump = Join-Path $Prefixe "bin\pg_dump.exe"
if (-not (Test-Path $pgDump)) { Ecrire "ECHEC : pg_dump introuvable ($pgDump)"; exit 1 }
if (-not (Test-Path $Secret)) { Ecrire "ECHEC : $Secret absent (serveur\07-PostgreSQL.ps1)"; exit 1 }
$pg = @{}; Get-Content $Secret | ForEach-Object { if ($_ -match "^([^=]+)=(.*)$") { $pg[$matches[1]] = $matches[2] } }
$env:PGPASSWORD = $pg["PGPASSWORD"]

$echecs = 0
foreach ($base in $Bases) {
    $fichier = Join-Path $Destination "$($base)_$(Get-Date -Format yyyyMMdd_HHmm).dump"
    & $pgDump -U $pg["PGUSER"] -h localhost -Fc -f $fichier $base
    if ($LASTEXITCODE -eq 0 -and (Test-Path $fichier)) {
        Ecrire "OK $base -> $fichier ($([math]::Round((Get-Item $fichier).Length / 1MB, 1)) Mo)"
    } else {
        $echecs++; Ecrire "ECHEC $base (pg_dump code $LASTEXITCODE)"
    }
}
Remove-Item Env:\PGPASSWORD

# Rotation : au-delà de $Conserver jours, les fichiers sont supprimés (le dossier est repris par la
# sauvegarde système quotidienne, 01-Sauvegarde-Systeme.ps1 -Planifier)
Get-ChildItem $Destination -Filter "*.dump" | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$Conserver) } | ForEach-Object {
    Remove-Item $_.FullName -Force; Ecrire "Supprimé (> $Conserver j) : $($_.Name)"
}

if ($echecs) {
    if (-not [System.Diagnostics.EventLog]::SourceExists('GIC')) { New-EventLog -LogName Application -Source 'GIC' }
    Write-EventLog -LogName Application -Source 'GIC' -EntryType Error -EventId 1003 -Message "Sauvegarde PostgreSQL : $echecs base(s) en échec. Voir $journal"
    exit 1
}
exit 0
