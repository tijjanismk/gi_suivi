<#
.SYNOPSIS
  Serveur — Installe ou met à jour l'application dans C:\GIC\<Env>\ depuis une
  archive produite par publier.ps1. Conserve la version précédente.

.USAGE
    .\installer.ps1 -Env test -Ref main          # depuis Git : C:\GIC\depot cloné puis mis à jour (recommandé)
    .\installer.ps1 -Env prod -Ref v1.0.0        # production : toujours un tag
    .\installer.ps1 -Env test -Zip \\AD-SERVEUR\GIC\deploy\app\gic-v0.3.0.zip   # ou depuis une archive de publier.ps1
    .\installer.ps1 -Env prod -RetourArriere

.GIT
  Le dépôt est privé : au premier clone, Git demande un identifiant GitHub et un jeton
  (fine-grained token, lecture seule du contenu de ce dépôt) ; le gestionnaire d'identifiants de
  Git pour Windows le mémorise pour le compte qui lance ce script. Git pour Windows doit être installé.

.ETAPES
  1. code dans app_nouveau\ (Git ou zip)  5. .env créé ou conservé
  2. venv créé ou mis à jour              6. manage.py check --deploy (bloquant en prod)
  3. pip install -e .                     7. migrate, collectstatic
  4. arrêt du service                     8. bascule app -> app_precedent, app_nouveau -> app, redémarrage
#>
param(
    [Parameter(Mandatory)][ValidateSet("test", "prod")][string]$Env,
    [string]$Ref,                                   # branche ou tag Git (main, v1.0.0)
    [string]$Zip,                                   # ou archive produite par publier.ps1
    [switch]$RetourArriere,
    [string]$Python = "C:\Python314\python.exe",
    [string]$Depot = "C:\GIC\depot",
    [string]$Url = "https://github.com/tijjanismk/gi_suivi.git"
)
$ErrorActionPreference = "Stop"
$base = "C:\GIC\$Env"; $app = "$base\app"; $prec = "$base\app_precedent"; $nouveau = "$base\app_nouveau"
$venv = "$base\venv"; $envFile = "$base\.env"; $service = "GIC-$($Env.Substring(0,1).ToUpper() + $Env.Substring(1))"
$port = if ($Env -eq "prod") { 8000 } else { 8001 }
$bdd  = if ($Env -eq "prod") { "gic" } else { "gic_test" }
$hote = if ($Env -eq "prod") { "suivi.giconseils.local" } else { "suivi-test.giconseils.local" }
New-Item -ItemType Directory -Path $base\journaux -Force | Out-Null
Start-Transcript -Path "$base\journaux\installer_$(Get-Date -Format yyyyMMdd_HHmm).log" | Out-Null

function Arreter-Service { if (Get-Service $service -ErrorAction SilentlyContinue) { Stop-Service $service -Force -ErrorAction SilentlyContinue; Start-Sleep 2 } }
function Demarrer-Service { if (Get-Service $service -ErrorAction SilentlyContinue) { Start-Service $service; Start-Sleep 3; Write-Host "Service $service : $((Get-Service $service).Status)" } else { Write-Warning "Service $service inexistant : lancez service.ps1 -Env $Env -Creer." } }

if ($RetourArriere) {
    if (-not (Test-Path $prec)) { throw "Aucune version précédente dans $prec." }
    Write-Host "Retour arrière vers la version précédente..."
    Arreter-Service
    if (Test-Path "$base\app_echec") { Remove-Item "$base\app_echec" -Recurse -Force }
    Rename-Item $app "app_echec"; Rename-Item $prec "app"
    Write-Host "Version active : $(Get-Content "$app\VERSION.json" -ErrorAction SilentlyContinue)"
    Write-Warning "Si la version retirée avait ajouté des migrations, exécutez la commande 'manage.py migrate <app> <migration>' notée dans sa pull request."
    Demarrer-Service
    Stop-Transcript | Out-Null; exit 0
}

if (-not $Ref -and (-not $Zip -or -not (Test-Path $Zip))) { throw "Indiquez -Ref <branche ou tag Git> ou -Zip <archive produite par publier.ps1>." }
if ($Ref -and $Env -eq "prod" -and $Ref -notmatch '^v\d+\.\d+\.\d+$') { throw "En production, -Ref doit être un tag vX.Y.Z (docs/git.md)." }
if (-not (Test-Path $Python)) { throw "Python introuvable : $Python (serveur\08-Python-IIS.ps1)." }

# 1. Le code dans app_nouveau\
if (Test-Path $nouveau) { Remove-Item $nouveau -Recurse -Force }
if ($Ref) {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "Git pour Windows absent : https://git-scm.com/download/win (puis rouvrir la console)." }
    if (-not (Test-Path "$Depot\.git")) {
        Write-Host "Premier clone de $Url dans $Depot (identifiant GitHub + jeton en lecture seule demandés une fois)..."
        git clone --quiet $Url $Depot
        if ($LASTEXITCODE -ne 0) { throw "git clone a échoué (jeton refusé ? réseau ?)." }
    }
    git -C $Depot fetch --all --tags --prune --quiet
    if ($LASTEXITCODE -ne 0) { throw "git fetch a échoué." }
    git -C $Depot checkout --detach --quiet "origin/$Ref" 2>$null
    if ($LASTEXITCODE -ne 0) { git -C $Depot checkout --detach --quiet $Ref; if ($LASTEXITCODE -ne 0) { throw "Référence Git introuvable : $Ref" } }
    New-Item -ItemType Directory -Path $nouveau -Force | Out-Null
    & robocopy.exe $Depot $nouveau /MIR /XD .git /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "Copie du dépôt en échec (robocopy $LASTEXITCODE)." }
    $commit = git -C $Depot rev-parse --short HEAD
    @{ ref = $Ref; commit = $commit; date = (Get-Date -Format s); source = "git" } | ConvertTo-Json | Set-Content "$nouveau\VERSION.json" -Encoding UTF8
} else {
    Expand-Archive -Path $Zip -DestinationPath "$base\_extraction" -Force
    Move-Item "$base\_extraction\gic" $nouveau; Remove-Item "$base\_extraction" -Recurse -Force
}
$version = Get-Content "$nouveau\VERSION.json" -Raw -ErrorAction SilentlyContinue
Write-Host "Version à installer : $version"

# 2-3. venv et dépendances
if (-not (Test-Path "$venv\Scripts\python.exe")) { & $Python -m venv $venv }
$py = "$venv\Scripts\python.exe"
& $py -m pip install --upgrade pip --quiet
Push-Location $nouveau
& $py -m pip install -e . --quiet
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "pip install a échoué." }
Pop-Location

# 5. .env : créé au premier déploiement, conservé ensuite
if (-not (Test-Path $envFile)) {
    $pgEnv = "C:\GIC\secrets\pg.env"
    if (-not (Test-Path $pgEnv)) { throw "$pgEnv absent : lancez serveur\07-PostgreSQL.ps1." }
    $pg = @{}; Get-Content $pgEnv | ForEach-Object { if ($_ -match "^([^=]+)=(.*)$") { $pg[$matches[1]] = $matches[2] } }
    $secret = -join ((1..60) | ForEach-Object { [char](Get-Random -Minimum 33 -Maximum 126) }) -replace "[`"'\\]", "x"
    @(
        "DJANGO_SETTINGS_MODULE=config.settings.prod",
        "SECRET_KEY=$secret",
        "ALLOWED_HOSTS=$hote,127.0.0.1,localhost",
        "DATABASE_URL=postgres://gic:$($pg['PGPASSWORD'])@localhost:5432/$bdd",
        "GROUPE_DIRECTION=GI-Direction",
        "GROUPE_DIRECTION_LECTURE=GI-Direction-Lecture",
        "GROUPE_OFFRES=GI-Offres",
        "IDENTITE_LECTEUR_GROUPES=identite.groupes_windows.groupes_de",   # ADR 0006 : API Windows du DC
        "PARTAGE_GIC=\\AD-SERVEUR\GIC",
        "STATIC_ROOT=$base\static_collecte",
        "JOURNAUX=$base\journaux",
        "ENVIRONNEMENT=$Env"
    ) | Set-Content $envFile -Encoding ASCII
    & icacls $envFile /inheritance:r /grant:r "BUILTIN\Administrateurs:F" "SYSTEM:F" "GICONSEILS\svc-application:R" | Out-Null
    Write-Host ".env créé : $envFile"
} else { Write-Host ".env conservé : $envFile" }
Copy-Item $envFile "$nouveau\.env" -Force

# 6. Vérifications Django
Push-Location $nouveau
$env:DJANGO_SETTINGS_MODULE = "config.settings.prod"
& $py manage.py check --deploy
if ($LASTEXITCODE -ne 0 -and $Env -eq "prod") { Pop-Location; throw "manage.py check --deploy a signalé un problème : déploiement en production refusé." }

# 4. Arrêt du service, 7. migrations et statiques (sur la base de cet environnement)
Arreter-Service
& $py manage.py migrate --noinput
if ($LASTEXITCODE -ne 0) { Pop-Location; Demarrer-Service; throw "migrate a échoué ; l'ancienne version a été redémarrée." }
& $py manage.py collectstatic --noinput --clear | Select-Object -Last 1
Pop-Location

# 8. Bascule
if (Test-Path $prec) { Remove-Item $prec -Recurse -Force }
if (Test-Path $app) { Rename-Item $app "app_precedent" }
Rename-Item $nouveau "app"
Demarrer-Service

# Contrôle
Start-Sleep 2
try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:$port/api/sante" -UseBasicParsing -TimeoutSec 10
    Write-Host "Santé locale : $($r.StatusCode) $($r.Content)"
} catch { Write-Warning "L'application ne répond pas encore sur 127.0.0.1:$port : $($_.Exception.Message). Voir $base\journaux\." }
Write-Host "`nTerminé. Vérifier depuis un poste : https://$hote/identite/qui-suis-je"
Stop-Transcript | Out-Null
