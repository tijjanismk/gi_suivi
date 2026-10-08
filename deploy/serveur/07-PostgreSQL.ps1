<#
.SYNOPSIS
  S07 (b) — Installe PostgreSQL (18 par défaut ; installateur EDB, mode silencieux),
  données sur D:, écoute locale seulement, puis crée le rôle « gic » et les
  bases « gic » et « gic_test ». Mots de passe générés et rangés dans
  C:\GIC\secrets.

.USAGE
    # Télécharger d'abord l'installateur Windows x86-64 de PostgreSQL 18 depuis
    # https://www.enterprisedb.com/downloads/postgres-postgresql-downloads
    .\07-PostgreSQL.ps1 -Installateur "C:\GIC\installateurs\postgresql-18.x-windows-x64.exe"
    .\07-PostgreSQL.ps1 -Installateur "...postgresql-17.x-windows-x64.exe" -Version 17   # autre version majeure
    .\07-PostgreSQL.ps1 -SeulementBases      # PostgreSQL déjà installé (à la main, assistant EDB) : rôle et bases seulement ;
                                             # le mot de passe « postgres » est demandé une fois s'il n'est pas dans C:\GIC\secrets
    .\07-PostgreSQL.ps1 -SeulementBases -MotDePasseGic gic   # rôle gic déjà créé à la main avec ce mot de passe : on le garde
#>
param(
    [string]$Installateur,
    [int]$Version = 18,                                 # version majeure : service postgresql-x64-<Version>
    [string]$Donnees,                                   # défaut : D:\PostgreSQL\<Version>\data
    [string]$Prefixe,                                   # défaut : C:\Program Files\PostgreSQL\<Version>
    [string]$MotDePasseGic,                             # mot de passe du rôle gic à imposer (sinon généré, ou repris de pg.env)
    [switch]$SeulementBases
)
$ErrorActionPreference = "Stop"
if (-not $Donnees) { $Donnees = "D:\PostgreSQL\$Version\data" }
if (-not $Prefixe) { $Prefixe = "C:\Program Files\PostgreSQL\$Version" }
$serviceNom = "postgresql-x64-$Version"
if ($Installateur -and (Split-Path $Installateur -Leaf) -notmatch "postgresql-$Version\.") {
    Write-Warning "L'installateur ne semble pas être un PostgreSQL $Version : $(Split-Path $Installateur -Leaf). Indiquez -Version si besoin."
}
$journaux = "D:\SAUVEGARDES\journaux"; New-Item -ItemType Directory -Path $journaux -Force | Out-Null
Start-Transcript -Path "$journaux\07-postgresql_$(Get-Date -Format yyyyMMdd_HHmm).log" | Out-Null

function Nouveau-MotDePasse($longueur = 28) {
    $car = ([char[]](48..57) + [char[]](65..90) + [char[]](97..122))
    -join (1..$longueur | ForEach-Object { $car | Get-Random })
}
$secrets = "C:\GIC\secrets"
if (-not (Test-Path $secrets)) {
    New-Item -ItemType Directory -Path $secrets -Force | Out-Null
    & icacls $secrets /inheritance:r /grant:r "BUILTIN\Administrateurs:(OI)(CI)F" "SYSTEM:(OI)(CI)F" | Out-Null
}
$fichierSuper = "$secrets\postgres-superuser.txt"
$fichierApp   = "$secrets\pg.env"

# 1. Installation
if (-not $SeulementBases) {
    if (-not $Installateur -or -not (Test-Path $Installateur)) { throw "Indiquez -Installateur <chemin de l'exe EDB téléchargé>." }
    if (Get-Service $serviceNom -ErrorAction SilentlyContinue) { Write-Host "Service $serviceNom déjà présent : installation sautée." }
    else {
        $mdpSuper = Nouveau-MotDePasse
        Set-Content $fichierSuper -Value "postgres`r`n$mdpSuper" -Encoding ASCII
        & icacls $fichierSuper /inheritance:r /grant:r "BUILTIN\Administrateurs:F" "SYSTEM:F" | Out-Null
        New-Item -ItemType Directory -Path (Split-Path $Donnees) -Force | Out-Null
        Write-Host "Installation silencieuse de PostgreSQL $Version (données : $Donnees)..."
        $args = @("--mode", "unattended", "--unattendedmodeui", "none", "--superpassword", $mdpSuper,
                  "--serverport", "5432", "--datadir", $Donnees, "--prefix", $Prefixe,
                  "--servicename", $serviceNom, "--locale", "French_France", "--disable-components", "stackbuilder")
        $p = Start-Process -FilePath $Installateur -ArgumentList $args -Wait -PassThru
        if ($p.ExitCode -ne 0) { throw "Installateur terminé avec le code $($p.ExitCode)." }
        Write-Host "PostgreSQL $Version installé. Mot de passe superutilisateur dans $fichierSuper."
    }
    # Écoute locale seulement (valeur par défaut, on la force) + journaux
    $conf = Join-Path $Donnees "postgresql.conf"
    (Get-Content $conf) -replace "^#?listen_addresses\s*=.*", "listen_addresses = 'localhost'" |
        ForEach-Object { $_ -replace "^#?log_min_duration_statement\s*=.*", "log_min_duration_statement = 2000" } | Set-Content $conf -Encoding ASCII
    Restart-Service $serviceNom
    # Pare-feu : 5432 bloqué depuis l'extérieur, explicitement
    if (-not (Get-NetFirewallRule -DisplayName "GIC - Bloquer PostgreSQL externe" -ErrorAction SilentlyContinue)) {
        New-NetFirewallRule -DisplayName "GIC - Bloquer PostgreSQL externe" -Direction Inbound -Protocol TCP -LocalPort 5432 -Action Block -Profile Any | Out-Null
    }
}

# 2. Rôle et bases
$psql = Join-Path $Prefixe "bin\psql.exe"
if (-not (Test-Path $psql)) { throw "psql introuvable dans $Prefixe\bin." }
if (-not (Test-Path $fichierSuper)) {
    # PostgreSQL installé à la main (assistant EDB) : le mot de passe « postgres » choisi alors n'est
    # pas connu du script ; on le demande une fois et on le range avec les autres secrets.
    Write-Host "PostgreSQL a été installé sans ce script : saisissez le mot de passe du superutilisateur « postgres » choisi à l'installation."
    $saisi = Read-Host "Mot de passe postgres" -AsSecureString
    $clair = [Runtime.InteropServices.Marshal]::PtrToStringUni([Runtime.InteropServices.Marshal]::SecureStringToGlobalAllocUnicode($saisi))
    if (-not $clair) { throw "Mot de passe vide." }
    Set-Content $fichierSuper -Value "postgres`r`n$clair" -Encoding ASCII
    & icacls $fichierSuper /inheritance:r /grant:r "BUILTIN\Administrateurs:F" "SYSTEM:F" | Out-Null
    Write-Host "Mot de passe rangé dans $fichierSuper (administrateurs seulement)."
}
$env:PGPASSWORD = (Get-Content $fichierSuper)[1]
# Pare-feu : 5432 bloqué depuis l'extérieur, même si l'installation a été faite à la main
if (-not (Get-NetFirewallRule -DisplayName "GIC - Bloquer PostgreSQL externe" -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName "GIC - Bloquer PostgreSQL externe" -Direction Inbound -Protocol TCP -LocalPort 5432 -Action Block -Profile Any | Out-Null
}

if ($MotDePasseGic) {
    # Mot de passe du rôle gic imposé (déjà créé à la main, par exemple) : le rôle est aligné dessus
    # et pg.env réécrit. Ne circule que sur localhost (PostgreSQL n'écoute pas ailleurs, 5432 bloqué).
    $mdpApp = $MotDePasseGic
    @("PGUSER=gic", "PGPASSWORD=$mdpApp", "DATABASE_URL=postgres://gic:$mdpApp@localhost:5432/gic",
      "DATABASE_URL_TEST=postgres://gic:$mdpApp@localhost:5432/gic_test") | Set-Content $fichierApp -Encoding ASCII
    & icacls $fichierApp /inheritance:r /grant:r "BUILTIN\Administrateurs:F" "SYSTEM:F" "GICONSEILS\svc-application:R" 2>$null | Out-Null
    Write-Host "Secret applicatif écrit dans $fichierApp avec le mot de passe fourni (-MotDePasseGic)."
} elseif (Test-Path $fichierApp) {
    $mdpApp = ((Get-Content $fichierApp) | Where-Object { $_ -match "^PGPASSWORD=" }) -replace "^PGPASSWORD=", ""
    Write-Host "Secret applicatif existant réutilisé."
} else {
    $mdpApp = Nouveau-MotDePasse
    @("PGUSER=gic", "PGPASSWORD=$mdpApp", "DATABASE_URL=postgres://gic:$mdpApp@localhost:5432/gic",
      "DATABASE_URL_TEST=postgres://gic:$mdpApp@localhost:5432/gic_test") | Set-Content $fichierApp -Encoding ASCII
    & icacls $fichierApp /inheritance:r /grant:r "BUILTIN\Administrateurs:F" "SYSTEM:F" "GICONSEILS\svc-application:R" 2>$null | Out-Null
    Write-Host "Secret applicatif écrit dans $fichierApp (lisible par svc-application)."
}

$sql = @"
DO `$`$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'gic') THEN
    CREATE ROLE gic LOGIN PASSWORD '$mdpApp';
  ELSE
    ALTER ROLE gic PASSWORD '$mdpApp';
  END IF;
END `$`$;
SELECT 'CREATE DATABASE gic OWNER gic ENCODING ''UTF8'' TEMPLATE template0'
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'gic')\gexec
SELECT 'CREATE DATABASE gic_test OWNER gic ENCODING ''UTF8'' TEMPLATE template0'
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'gic_test')\gexec
"@
$sql | & $psql -U postgres -h localhost -d postgres -v ON_ERROR_STOP=1
# Extensions utiles (plein texte sans accents, trigrammes) dans chaque base
foreach ($b in "gic", "gic_test") {
    "CREATE EXTENSION IF NOT EXISTS unaccent; CREATE EXTENSION IF NOT EXISTS pg_trgm;" | & $psql -U postgres -h localhost -d $b -v ON_ERROR_STOP=1
}
Write-Host "`nVérification (connexion avec le rôle gic, sans saisie) :"
$env:PGPASSWORD = $mdpApp
& $psql -U gic -h localhost -d gic -c "select current_user, version();" 2>&1 | Select-Object -First 3
Remove-Item Env:\PGPASSWORD
Write-Host "`nL'application lit DATABASE_URL dans $fichierApp. Sauvegarde pg_dump : voir deploy/sauvegarde_pg.ps1 (ticket S07)."
Stop-Transcript | Out-Null
