<#
.SYNOPSIS
  Serveur — Installe ou met à jour l'application dans C:\GIC\<Env>\ depuis le dépôt Git
  (C:\GIC\depot, clone privé). Conserve la version précédente. Le serveur n'a aucun outil de
  développement : tout ce qui se construit (CSS, traductions, agent) est construit sur le poste
  du développeur et commité ; ici on ne fait que copier, installer les dépendances (roues
  binaires), migrer et redémarrer.

.USAGE
    .\installer.ps1 -Env test -Ref main          # test : la branche main (flux normal, Git)
    .\installer.ps1 -Env test                    # test : contenu de C:\GIC\depot tel quel (copie posée à la main, pas de GitHub)
    .\installer.ps1 -Env prod -Ref v1.0.0        # production : toujours un tag
    .\installer.ps1 -Env prod -RetourArriere

.GIT
  Le dépôt est privé : au premier clone, Git demande un identifiant GitHub et un jeton
  (fine-grained token, lecture seule du contenu de ce dépôt) ; le gestionnaire d'identifiants de
  Git pour Windows le mémorise pour le compte qui lance ce script. Git pour Windows doit être installé.

.ETAPES
  1. code dans app_nouveau\ (fetch + checkout + copie sans .git)   5. .env créé ou conservé
  2. venv créé ou mis à jour                                        6. manage.py check --deploy (bloquant en prod)
  3. pip install -r deploy\requirements.txt --only-binary=:all:     7. migrate, collectstatic
  4. arrêt du service                                               8. bascule app -> app_precedent, app_nouveau -> app, redémarrage
#>
param(
    [Parameter(Mandatory)][ValidateSet("test", "prod")][string]$Env,
    [string]$Ref,                                   # branche ou tag Git (main, v1.0.0)
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

if ($Env -eq "prod" -and $Ref -notmatch '^v\d+\.\d+\.\d+$') { throw "En production, -Ref doit être un tag vX.Y.Z (docs/git.md)." }
function Python-Fonctionne($exe) {
    # Refuse un python.exe orphelin (installation interrompue : « Could not find platform independent
    # libraries ») et un Python installé dans le profil d'un utilisateur (C:\Users\…) : le service
    # tourne sous svc-application, qui n'y a pas accès.
    if (-not $exe -or -not (Test-Path $exe)) { return $false }
    $base = & $exe -c "import sys, encodings; print(sys.base_prefix)" 2>&1
    if ($LASTEXITCODE -ne 0) { return $false }
    if ("$base" -like "C:\Users\*") { Write-Warning "Python installé pour un seul compte ($base) : inutilisable par le service."; return $false }
    return $true
}
if (-not (Python-Fonctionne $Python)) {
    # Python installé ailleurs qu'en C:\Python314 (à la main) : 08-Python-IIS.ps1 a noté son chemin
    $candidats = @()
    $note = "C:\GIC\outils\python.txt"
    if (Test-Path $note) { $candidats += (Get-Content $note -First 1) }
    $p = (Get-ItemProperty "HKLM:\SOFTWARE\Python\PythonCore\3.14\InstallPath" -ErrorAction SilentlyContinue).'(default)'
    if ($p) { $candidats += (Join-Path $p "python.exe") }
    $Python = $candidats | Where-Object { Python-Fonctionne $_ } | Select-Object -First 1
}
if (-not $Python) { throw "Aucun Python 3.14 fonctionnel (serveur\08-Python-IIS.ps1 l'installe pour tous les utilisateurs)." }
Write-Host "Python : $Python"
# Un venv créé à partir d'un Python cassé est inutilisable : on le refait si son python ne démarre pas
if ((Test-Path "$venv\Scripts\python.exe") -and -not (Python-Fonctionne "$venv\Scripts\python.exe")) {
    Write-Warning "Environnement virtuel $venv inutilisable : recréé."
    Remove-Item $venv -Recurse -Force
}
$git = Get-Command git -ErrorAction SilentlyContinue

# 1. Le code dans app_nouveau\
#    - avec -Ref : le dépôt Git est mis à jour (clone au premier passage), la référence extraite ;
#    - sans -Ref (test seulement) : le contenu de $Depot est pris tel quel — pour un dépôt posé à la
#      main (copie du poste) ou quand GitHub n'est pas joignable. La version est alors « copie locale ».
if (Test-Path $nouveau) { Remove-Item $nouveau -Recurse -Force }
if ($Ref) {
    if (-not $git) { throw "Git pour Windows absent : https://git-scm.com/download/win (puis rouvrir la console) — ou lancez sans -Ref pour installer le contenu de $Depot tel quel." }
    if (-not (Test-Path "$Depot\.git")) {
        if (Test-Path "$Depot\manage.py") { throw "$Depot contient le projet mais n'est pas un clone Git. Soit lancez sans -Ref (contenu pris tel quel), soit renommez ce dossier et laissez ce script cloner." }
        Write-Host "Premier clone de $Url dans $Depot (identifiant GitHub + jeton en lecture seule demandés une fois)..."
        git clone --quiet $Url $Depot
        if ($LASTEXITCODE -ne 0) { throw "git clone a échoué (jeton refusé ? réseau ?)." }
    }
    git -C $Depot fetch --all --tags --prune --quiet
    if ($LASTEXITCODE -ne 0) { throw "git fetch a échoué (jeton ? réseau ?). Sans GitHub : lancez sans -Ref pour installer le contenu actuel de $Depot." }
    git -C $Depot checkout --detach --quiet "origin/$Ref" 2>$null
    if ($LASTEXITCODE -ne 0) { git -C $Depot checkout --detach --quiet $Ref; if ($LASTEXITCODE -ne 0) { throw "Référence Git introuvable : $Ref" } }
    $commit = git -C $Depot rev-parse --short HEAD
    $version = @{ ref = $Ref; commit = $commit; date = (Get-Date -Format s); source = "git" }
} else {
    if (-not (Test-Path "$Depot\manage.py")) { throw "$Depot ne contient pas le projet (manage.py absent). Indiquez -Ref main pour cloner depuis GitHub, ou copiez le projet dans $Depot." }
    $commit = "inconnu"
    if ($git -and (Test-Path "$Depot\.git")) { $commit = (git -C $Depot rev-parse --short HEAD 2>$null); if (-not $commit) { $commit = "inconnu" } }
    Write-Warning "Sans -Ref : installation du contenu actuel de $Depot tel quel (copie locale, commit $commit). Le flux normal reste Git (-Ref main)."
    $version = @{ ref = "copie locale"; commit = $commit; date = (Get-Date -Format s); source = "copie" }
}
# Copie sans ce qui n'a rien à faire sur le serveur : dépôt Git, environnements virtuels du poste,
# caches, constructions de l'agent, .env du développeur (le .env du serveur est posé à l'étape 5)
New-Item -ItemType Directory -Path $nouveau -Force | Out-Null
& robocopy.exe $Depot $nouveau /MIR /NFL /NDL /NJH /NJS /NP `
    /XD .git .venv venv __pycache__ .pytest_cache .ruff_cache htmlcov node_modules dist build "agent\dist" "agent\build" "agent\.venv" `
    /XF .env "*.pyc" "*.log" "*.db" "*.zip" | Out-Null
if ($LASTEXITCODE -ge 8) { throw "Copie du dépôt en échec (robocopy $LASTEXITCODE)." }
$version | ConvertTo-Json | Set-Content "$nouveau\VERSION.json" -Encoding UTF8
Write-Host "Version à installer : $($version.ref) ($($version.commit), source $($version.source))"
foreach ($construit in "interface\static\css\gic.css", "locale\fr\LC_MESSAGES\django.mo") {
    if (-not (Test-Path "$nouveau\$construit")) { throw "$construit absent du dépôt : il se construit sur le poste du développeur et se commite (pas d'outil de développement ici)." }
}

# 2-3. venv et dépendances d'exécution, roues binaires seulement (aucune compilation sur le serveur).
# deploy\requirements.txt est généré sur le poste par scripts\dev\exporter_dependances.py.
if (-not (Test-Path "$venv\Scripts\python.exe")) { & $Python -m venv $venv }
$py = "$venv\Scripts\python.exe"
& $py -m pip install --upgrade pip --quiet
& $py -m pip install --only-binary=:all: -r "$nouveau\deploy\requirements.txt" --quiet
if ($LASTEXITCODE -ne 0) { throw "pip install a échoué (réseau vers pypi.org ? roue binaire manquante ?)." }

# 5. .env : créé au premier déploiement, conservé ensuite
if (-not (Test-Path $envFile)) {
    $pgEnv = "C:\GIC\secrets\pg.env"
    if (-not (Test-Path $pgEnv)) { throw "$pgEnv absent : lancez serveur\07-PostgreSQL.ps1." }
    $pg = @{}; Get-Content $pgEnv | ForEach-Object { if ($_ -match "^([^=]+)=(.*)$") { $pg[$matches[1]] = $matches[2] } }
    # lettres et chiffres seulement : pas de « # », « = » ni guillemet qui gêneraient la lecture du .env
    $alphabet = ([char[]](48..57) + [char[]](65..90) + [char[]](97..122))
    $secret = -join (1..60 | ForEach-Object { $alphabet | Get-Random })
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
        "DOSSIER_JOURNAUX=$base\journaux",
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
