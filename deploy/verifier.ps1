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
    # Le code qui répond est-il celui qui est installé ? (un processus orphelin servirait l'ancien)
    $attendu = $null; try { $attendu = (Get-Content "$base\app\VERSION.json" -Raw | ConvertFrom-Json).commit } catch { }
    $servi = $null; try { $servi = ($r.Content | ConvertFrom-Json).version } catch { }
    if ($attendu) { Point "Code en service = code installé" ($servi -eq $attendu) "installé $attendu, en service $(if ($servi) { $servi } else { 'inconnu (ancienne version ?)' })" -Bloquant }
} catch { Point "Santé locale 127.0.0.1:$port" $false $_.Exception.Message -Bloquant }

# Feuille de style servie par IIS (statiques) : sans elle, les pages s'affichent sans mise en forme
try {
    $css = Invoke-WebRequest -Uri "https://$hote/static/css/gic.css" -UseBasicParsing -TimeoutSec 15
    Point "Statiques via IIS (gic.css)" ($css.StatusCode -eq 200) "$($css.StatusCode), $([math]::Round($css.RawContentLength / 1KB)) Ko"
} catch {
    $code = $null; try { $code = $_.Exception.Response.StatusCode.value__ } catch { }
    Point "Statiques via IIS (gic.css)" $false "$(if ($code) { $code } else { $_.Exception.Message }) — identité anonyme du site ou jonction site\static (08-Python-IIS.ps1)"
}

# Kerberos de bout en bout : la page d'identité, avec le ticket de la session qui lance ce script.
# 200/403 = authentifié (403 : ce compte n'a pas de rôle) ; 401 = ticket refusé ou non présenté.
try {
    $q = Invoke-WebRequest -Uri "https://$hote/identite/qui-suis-je" -UseBasicParsing -UseDefaultCredentials -TimeoutSec 15
    Point "Kerberos (qui-suis-je)" $true "$($q.StatusCode) authentifié"
} catch {
    $code = $null; try { $code = $_.Exception.Response.StatusCode.value__ } catch { }
    $serveur = $null; try { $serveur = $_.Exception.Response.Headers['Server'] } catch { }
    $aide = if ($code -eq 403) { ' authentifié, sans rôle' } elseif ($code -eq 401 -and "$serveur" -like '*HTTPAPI*') { ' refusé par http.sys (ancienne configuration) : 08-Python-IIS.ps1 redémarre les sites' } elseif ($code -eq 401) { ' ticket refusé par l''application : journal gic.log' } else { '' }
    Point "Kerberos (qui-suis-je)" ($code -eq 403) "$(if ($code) { $code } else { $_.Exception.Message })$aide"
}

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
