<#
.SYNOPSIS
  Serveur — Vérifie un environnement après installation ou mise à jour : version déployée,
  service, réponse de /api/sante en local (Uvicorn) et à travers IIS (Kerberos), tâches
  planifiées, dernière sauvegarde PostgreSQL, espace disque, dernières lignes de journal.
  Ne modifie rien. Code de sortie 1 si un point bloquant échoue.

.USAGE
    .\verifier.ps1 -Env test
    .\verifier.ps1 -Env prod
#>
param(
    [Parameter(Mandatory)][ValidateSet("test", "prod")][string]$Env
)
$ErrorActionPreference = "Continue"
$base = "C:\GIC\$Env"; $service = "GIC-$($Env.Substring(0,1).ToUpper() + $Env.Substring(1))"
$port = if ($Env -eq "prod") { 8000 } else { 8001 }
$hote = if ($Env -eq "prod") { "suivi.giconseils.local" } else { "suivi-test.giconseils.local" }
$bloquants = 0

function Point($nom, $ok, $detail, [switch]$Bloquant) {
    $etat = if ($ok) { "OK   " } elseif ($Bloquant) { "ECHEC" } else { "AVERT" }
    $couleur = if ($ok) { "Green" } elseif ($Bloquant) { "Red" } else { "Yellow" }
    Write-Host ("{0} {1,-34} {2}" -f $etat, $nom, $detail) -ForegroundColor $couleur
    if (-not $ok -and $Bloquant) { $script:bloquants++ }
}

Write-Host "`n=== GIC $Env — $(Get-Date -Format 'yyyy-MM-dd HH:mm')`n"

# Version déployée
$version = Get-Content "$base\app\VERSION.json" -Raw -ErrorAction SilentlyContinue
$detailVersion = if ($version) { ("$version" -replace '\s+', ' ').Trim() } else { "$base\app\VERSION.json absent : installer.ps1 -Env $Env -Ref …" }
Point "Version (app\VERSION.json)" ([bool]$version) $detailVersion -Bloquant

# Service NSSM
$svc = Get-Service $service -ErrorAction SilentlyContinue
$detailSvc = if ($svc) { "$($svc.Status), démarrage $($svc.StartType)" } else { "inexistant (service.ps1 -Env $Env -Creer)" }
Point "Service $service" ($svc -and $svc.Status -eq "Running") $detailSvc -Bloquant

# Santé en local (Uvicorn, sans IIS)
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:$port/api/sante" -UseBasicParsing -TimeoutSec 10
    Point "Santé locale 127.0.0.1:$port" ($r.StatusCode -eq 200) "$($r.StatusCode) $($r.Content)" -Bloquant
} catch { Point "Santé locale 127.0.0.1:$port" $false $_.Exception.Message -Bloquant }

# Santé à travers IIS (Negotiate, identité de la console). Hors domaine ou sans certificat : avertissement
try {
    $r = Invoke-WebRequest -Uri "https://$hote/api/sante" -UseBasicParsing -UseDefaultCredentials -TimeoutSec 15
    Point "Santé via IIS https://$hote" ($r.StatusCode -eq 200) "$($r.StatusCode) $($r.Content)"
} catch { Point "Santé via IIS https://$hote" $false "$($_.Exception.Message) — DNS, certificat, site IIS ou Negotiate (08-Python-IIS.ps1)" }

# Tâches planifiées
$taches = Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.TaskName -like "GIC $Env -*" -or $_.TaskName -eq "GIC - Sauvegarde PostgreSQL" }
$enEchec = @()
foreach ($t in $taches) {
    $info = Get-ScheduledTaskInfo $t
    if ($info.LastTaskResult -notin 0, 267009, 267011) { $enEchec += "$($t.TaskName) ($($info.LastTaskResult))" }  # 267009 : en cours ; 267011 : jamais lancée
}
$detailTaches = "$($taches.Count), dernier résultat 0"
if ($taches.Count -lt 5) { $detailTaches = "$($taches.Count) trouvée(s) : taches.ps1 -Env $Env" }
elseif ($enEchec.Count) { $detailTaches = "dernier résultat en échec : $($enEchec -join ', ')" }
Point "Tâches planifiées" ($taches.Count -ge 5 -and $enEchec.Count -eq 0) $detailTaches

# Dernière sauvegarde PostgreSQL
$derniere = Get-ChildItem "D:\SAUVEGARDES\pg" -Filter "gic_*.dump" -ErrorAction SilentlyContinue | Where-Object Name -notlike "gic_test_*" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$detailPg = if ($derniere) { "$($derniere.Name), $([math]::Round($derniere.Length / 1MB, 1)) Mo" } else { "aucune (sauvegarde_pg.ps1 ou tâche 01:00)" }
Point "Sauvegarde PostgreSQL (base gic)" ($derniere -and $derniere.LastWriteTime -gt (Get-Date).AddHours(-26)) $detailPg

# Disques
foreach ($lettre in "C", "D") {
    $v = Get-Volume $lettre -ErrorAction SilentlyContinue
    if ($v) { $libre = [math]::Round(100 * $v.SizeRemaining / $v.Size); Point "Disque ${lettre}:" ($libre -ge 20) "$libre % libre ($([math]::Round($v.SizeRemaining / 1GB)) Go)" }
}

# Mémoire (ADR 0002 : 16 Go avant la production)
$go = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
$detailGo = "$go Go"; if ($Env -eq "prod" -and $go -lt 16) { $detailGo += " — 16 Go requis en production (ADR 0002)" }
Point "Mémoire" ($Env -ne "prod" -or $go -ge 16) $detailGo -Bloquant:($Env -eq "prod")

# Journaux
foreach ($j in "uvicorn.err.log", "uvicorn.log") {
    $f = "$base\journaux\$j"
    if (Test-Path $f) {
        Write-Host "`n--- $f (5 dernières lignes)" -ForegroundColor Cyan
        Get-Content $f -Tail 5
    }
}

Write-Host ""
if ($bloquants) { Write-Host "$bloquants point(s) bloquant(s). Retour arrière possible : .\installer.ps1 -Env $Env -RetourArriere" -ForegroundColor Red; exit 1 }
Write-Host "Environnement $Env sain. Depuis un poste du domaine : https://$hote/identite/qui-suis-je" -ForegroundColor Green
exit 0
