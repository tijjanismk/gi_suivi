<#
.SYNOPSIS
  Serveur — Crée ou met à jour le service Windows GIC-Test / GIC-Prod qui
  exécute Uvicorn sous le compte de service, avec NSSM.

.USAGE
    .\service.ps1 -Env test -Nssm C:\...\nssm.exe -Creer     # première fois (copie nssm dans C:\GIC\outils)
    .\service.ps1 -Env prod -Creer
    .\service.ps1 -Env prod -Etat
    .\service.ps1 -Env prod -Supprimer
#>
param(
    [Parameter(Mandatory)][ValidateSet("test", "prod")][string]$Env,
    [string]$Nssm,
    [switch]$Creer, [switch]$Etat, [switch]$Supprimer,
    [int]$Travailleurs = 1,      # un seul processus : suffisant pour le pilote, et un arrêt du service arrête tout le code
                                 # (avec plusieurs, les processus de travail survivaient et gardaient l'ancienne version sur le port)
    [string]$CompteService = "svc-application"
)
$ErrorActionPreference = "Stop"
$base = "C:\GIC\$Env"; $service = "GIC-$($Env.Substring(0,1).ToUpper() + $Env.Substring(1))"
$port = if ($Env -eq "prod") { 8000 } else { 8001 }
$outils = "C:\GIC\outils"; New-Item -ItemType Directory -Path $outils -Force | Out-Null
$nssm = "$outils\nssm.exe"
# Copie de nssm.exe seulement s'il manque ou diffère : en service, le fichier est verrouillé
if ($Nssm -and (Test-Path $Nssm)) {
    $memeFichier = (Test-Path $nssm) -and ((Get-FileHash $Nssm).Hash -eq (Get-FileHash $nssm).Hash)
    if (-not $memeFichier) {
        try { Copy-Item $Nssm $nssm -Force }
        catch { if (Test-Path $nssm) { Write-Warning "nssm.exe en cours d'utilisation : la copie existante est conservée." } else { throw } }
    }
}
. (Join-Path $PSScriptRoot 'liberer-port.ps1')
if (-not (Test-Path $nssm)) { throw "nssm.exe introuvable : passez -Nssm <chemin> la première fois (https://nssm.cc)." }

if ($Etat) { & $nssm status $service; Get-Service $service | Format-List Name, Status, StartType; exit 0 }
if ($Supprimer) { & $nssm stop $service 2>$null; & $nssm remove $service confirm; exit 0 }
if (-not $Creer) { throw "Indiquez -Creer, -Etat ou -Supprimer." }

$mdpFichier = "C:\GIC\secrets\$CompteService.txt"
if (-not (Test-Path $mdpFichier)) { throw "$mdpFichier absent (serveur\04-Comptes-et-groupes.ps1)." }
$compte = (Get-Content $mdpFichier)[0]; $mdp = (Get-Content $mdpFichier)[1]
$py = "$base\venv\Scripts\python.exe"
New-Item -ItemType Directory -Path "$base\journaux" -Force | Out-Null

# --no-proxy-headers : l'application ne croit X-Remote-User que s'il vient de 127.0.0.1 (IIS/ARR).
# Avec --proxy-headers, Uvicorn remplacerait l'adresse de l'appelant par celle du poste (X-Forwarded-For)
# et l'identité serait ignorée (« Identité Windows absente »). Le HTTPS est signalé par X-Forwarded-Proto,
# lu par Django directement (SECURE_PROXY_SSL_HEADER).
$args = "-m uvicorn config.asgi:application --host 127.0.0.1 --port $port --workers $Travailleurs --no-proxy-headers --log-level info"
if (-not (Get-Service $service -ErrorAction SilentlyContinue)) {
    & $nssm install $service $py $args | Out-Null
    Write-Host "Service $service créé."
} else {
    & $nssm set $service Application $py | Out-Null
    & $nssm set $service AppParameters $args | Out-Null
    Write-Host "Service $service mis à jour."
}
& $nssm set $service AppDirectory "$base\app" | Out-Null
& $nssm set $service DisplayName "GIC - Application ($Env)" | Out-Null
& $nssm set $service Description "GI-CONSEILS - suivi d'activité et avis - environnement $Env - port $port" | Out-Null
# Démarrage différé : sur le contrôleur de domaine, juste après un redémarrage, l'annuaire refusait
# encore le compte de service (« mot de passe incorrect », 23/10/2026). Relance par le gestionnaire
# de services si le démarrage échoue malgré tout.
& $nssm set $service Start SERVICE_DELAYED_AUTO_START | Out-Null
& sc.exe failure $service reset= 86400 actions= restart/60000/restart/60000/restart/120000 | Out-Null
if ($LASTEXITCODE -ne 0) { throw "sc.exe failure : échec ($LASTEXITCODE)." }
$pgService = (Get-Service | Where-Object Name -like "postgresql-x64-*" | Sort-Object Name -Descending | Select-Object -First 1).Name
if ($pgService) { & $nssm set $service DependOnService $pgService | Out-Null } else { Write-Warning "Aucun service postgresql-x64-* : dépendance non posée (serveur\07-PostgreSQL.ps1)." }
& $nssm set $service ObjectName $compte $mdp | Out-Null          # NSSM accorde le droit « ouvrir une session en tant que service »
& $nssm set $service AppEnvironmentExtra "DJANGO_SETTINGS_MODULE=config.settings.prod" "PYTHONUNBUFFERED=1" | Out-Null
& $nssm set $service AppStdout "$base\journaux\uvicorn.log" | Out-Null
& $nssm set $service AppStderr "$base\journaux\uvicorn.err.log" | Out-Null
& $nssm set $service AppRotateFiles 1 | Out-Null
& $nssm set $service AppRotateOnline 1 | Out-Null
& $nssm set $service AppRotateBytes 52428800 | Out-Null          # 50 Mo
& $nssm set $service AppExit Default Restart | Out-Null
& $nssm set $service AppRestartDelay 5000 | Out-Null
& $nssm set $service AppStopMethodConsole 10000 | Out-Null

if (Test-Path "$base\app\manage.py") {
    # Paramètres lus au démarrage seulement : arrêt, port libéré (un interpréteur orphelin le garderait,
    # Uvicorn ne pourrait pas s'y attacher et NSSM mettrait le service en pause), puis démarrage.
    & $nssm stop $service 2>&1 | Out-Null
    Liberer-Port $port
    & $nssm start $service 2>&1 | Out-Null
    Start-Sleep 4
    Write-Host "État : $((Get-Service $service).Status)"
} else {
    Write-Host "Application non encore installée dans $base\app : le service démarrera après installer.ps1."
}
