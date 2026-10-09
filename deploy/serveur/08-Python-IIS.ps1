<#
.SYNOPSIS
  S07 (c) — Installe Python 3.14 pour tous les utilisateurs, configure IIS
  comme frontal d'authentification Windows (Kerberos seul) et proxy inverse
  vers Uvicorn, crée les sites suivi-test et suivi, règle le pare-feu.

.USAGE
    # Télécharger d'abord :
    #  - Python 3.14 Windows installer (64-bit) : https://www.python.org/downloads/windows/
    #  - URL Rewrite 2.1 et Application Request Routing 3.0 (x64) : https://www.iis.net/downloads
    .\08-Python-IIS.ps1 -Python ".\python-3.14.x-amd64.exe" -UrlRewrite ".\rewrite_amd64_fr-FR.msi" -ARR ".\requestRouter_amd64.msi" -Empreinte <empreinte du certificat>
    .\08-Python-IIS.ps1 -Python ... -UrlRewrite ... -ARR ... -AutoSigne     # pas d'autorité interne : certificat auto-signé créé ici
    .\08-Python-IIS.ps1 -SeulementIIS -Empreinte <empreinte>     # Python déjà installé
    .\08-Python-IIS.ps1 -SansHttps                                  # test sans certificat (réseau local, provisoire)

.CERTIFICAT
  -Empreinte : empreinte SHA1 d'un certificat déjà présent dans
  Cert:\LocalMachine\My couvrant suivi.giconseils.local et suivi-test.giconseils.local
  (autorité interne AD CS, ou auto-signé déployé par GPO).
  -AutoSigne : AD-SERVEUR n'a pas d'autorité de certification (inventaire du 06/10). Le script
  crée (ou réutilise) un certificat auto-signé pour les deux noms, valable 5 ans, et l'exporte
  en C:\GIC\deploy\gic-serveur.cer : ce fichier est à copier dans le kit de l'agent
  (installer-poste.ps1 l'approuve sur chaque poste) — plus tard, une GPO le fera.
  Sans -Empreinte, -AutoSigne ni -SansHttps, le script s'arrête : Kerberos sans HTTPS n'a pas
  de sens en production.
#>
param(
    [string]$Python, [string]$UrlRewrite, [string]$ARR,
    [string]$Empreinte, [switch]$AutoSigne, [switch]$SansHttps, [switch]$SeulementIIS,
    [string]$CompteService = "svc-application"
)
$ErrorActionPreference = "Stop"
$journaux = "D:\SAUVEGARDES\journaux"; New-Item -ItemType Directory -Path $journaux -Force | Out-Null
Start-Transcript -Path "$journaux\08-python-iis_$(Get-Date -Format yyyyMMdd_HHmm).log" | Out-Null
$zone = (Get-ADDomain).DNSRoot; $dom = (Get-ADDomain).NetBIOSName

# 1. Python 3.14 pour tous les utilisateurs, hors profil. S'il a été installé à la main (assistant
#    python.org, « pour tous les utilisateurs »), on le retrouve par le registre et on le garde ;
#    l'installer une seconde fois échouerait (code 1603).
function Python-Fonctionne($exe) {
    # Une installation interrompue laisse un python.exe sans bibliothèque (« Could not find platform
    # independent libraries ») : on ne retient qu'un Python qui démarre vraiment.
    if (-not (Test-Path $exe)) { return $false }
    $base = & $exe -c "import sys, encodings; print(sys.base_prefix)" 2>&1
    if ($LASTEXITCODE -ne 0) { return $false }
    # Installé dans le profil d'un utilisateur (« pour moi seulement ») : le service n'y a pas accès
    if ("$base" -like "C:\Users\*") { Write-Warning "Python installé pour un seul compte ($base) : inutilisable par le service svc-application."; return $false }
    return $true
}
function Trouver-Python314 {
    $candidats = @("C:\Python314\python.exe")
    foreach ($cle in "HKLM:\SOFTWARE\Python\PythonCore\3.14\InstallPath", "HKLM:\SOFTWARE\WOW6432Node\Python\PythonCore\3.14\InstallPath") {
        $p = (Get-ItemProperty $cle -ErrorAction SilentlyContinue).'(default)'
        if ($p) { $candidats += (Join-Path $p "python.exe") }
    }
    foreach ($c in $candidats) {
        if (Test-Path $c) {
            if (Python-Fonctionne $c) { return $c }
            Write-Warning "Python présent mais inutilisable (installation incomplète) : $c"
            if ($c -eq "C:\Python314\python.exe") {
                # reste d'une installation silencieuse échouée (code 1603) : écarté, pas supprimé
                $casse = "C:\Python314_incomplet_$(Get-Date -Format yyyyMMdd_HHmm)"
                Rename-Item "C:\Python314" $casse
                Write-Host "C:\Python314 renommé en $casse."
            }
        }
    }
    return $null
}
New-Item -ItemType Directory -Path C:\GIC\outils -Force | Out-Null
if (-not $SeulementIIS) {
    $pyExe = Trouver-Python314
    if ($pyExe) { Write-Host "Python 3.14 déjà installé : $pyExe" }
    else {
        $perso = (Get-ItemProperty "HKCU:\SOFTWARE\Python\PythonCore\3.14\InstallPath" -ErrorAction SilentlyContinue).'(default)'
        if ($perso) { throw "Python 3.14 est installé pour votre seul compte ($perso) : le service (svc-application) ne pourra pas l'utiliser. Désinstallez-le (Paramètres > Applications installées > Python 3.14 (64-bit) > Désinstaller) puis relancez : le script l'installera pour tous les utilisateurs dans C:\Python314." }
        if (-not $Python -or -not (Test-Path $Python)) { throw "Indiquez -Python <installateur>." }
        Write-Host "Installation de Python 3.14 dans C:\Python314..."
        $p = Start-Process $Python -ArgumentList "/quiet InstallAllUsers=1 TargetDir=C:\Python314 PrependPath=0 Include_test=0 Include_launcher=1 CompileAll=1" -Wait -PassThru
        if ($p.ExitCode -ne 0) { throw "Installateur Python : code $($p.ExitCode) (1603 = déjà installé ailleurs ou installation en conflit ; voir %TEMP%\Python 3.14*.log)." }
        $pyExe = "C:\Python314\python.exe"
    }
    & $pyExe --version
    # Retenu pour installer.ps1 (qui lit ce fichier si C:\Python314 n'existe pas)
    Set-Content -Path C:\GIC\outils\python.txt -Value $pyExe -Encoding ASCII
}

# 2. IIS : fonctionnalités nécessaires (le rôle Web-Server est déjà présent sur ce serveur)
#    Le Gestionnaire IIS ouvert, ou une autre console PowerShell qui a chargé le module IIS, peut
#    bloquer l'écriture de la configuration : on prévient avant de commencer.
if (Get-Process inetmgr -ErrorAction SilentlyContinue) { Write-Warning "Le Gestionnaire des services IIS est ouvert : fermez-le, il peut bloquer l'écriture de la configuration." }
$autres = Get-Process powershell, pwsh -ErrorAction SilentlyContinue | Where-Object { $_.Id -ne $PID }
if ($autres) { Write-Warning "$($autres.Count) autre(s) fenêtre(s) PowerShell ouverte(s) : si l'une d'elles exécute encore un script GIC, fermez-la (deux déploiements en même temps se bloquent l'un l'autre)." }
$feat = "Web-Server","Web-Windows-Auth","Web-Static-Content","Web-Http-Logging","Web-Filtering","Web-Mgmt-Console"
Install-WindowsFeature $feat | Out-Null
Import-Module WebAdministration

# URL Rewrite et ARR (modules Microsoft, installateurs MSI fournis)
function Installer-Msi($chemin, $nom) {
    if (-not $chemin) { Write-Warning "$nom : aucun installateur fourni, étape sautée."; return }
    if (-not (Test-Path $chemin)) { throw "$nom : $chemin introuvable." }
    Write-Host "Installation $nom..."
    $p = Start-Process msiexec.exe -ArgumentList "/i `"$chemin`" /qn /norestart" -Wait -PassThru
    if ($p.ExitCode -notin 0, 3010) { throw "$nom : msiexec code $($p.ExitCode)." }
}
if (-not (Test-Path "$env:ProgramFiles\IIS\Application Request Routing")) {
    Installer-Msi $UrlRewrite "URL Rewrite"
    Installer-Msi $ARR "Application Request Routing"
} else { Write-Host "ARR déjà installé." }
# Le proxy ARR est activé en fin de script, par appcmd (voir § 7) : le module PowerShell d'IIS n'écrit
# pas cette section de façon fiable ici, et appcmd ne doit pas être mêlé à ses écritures.

# 3. Dossiers de l'application
foreach ($env in "test", "prod") {
    foreach ($d in "app", "journaux", "static_collecte") { New-Item -ItemType Directory -Path "C:\GIC\$env\$d" -Force | Out-Null }
}
& icacls C:\GIC /grant:r "$dom\${CompteService}:(OI)(CI)M" "BUILTIN\Administrateurs:(OI)(CI)F" "SYSTEM:(OI)(CI)F" /inheritance:r | Out-Null
& icacls C:\GIC\secrets /inheritance:r /grant:r "BUILTIN\Administrateurs:(OI)(CI)F" "SYSTEM:(OI)(CI)F" "$dom\${CompteService}:(OI)(CI)R" 2>$null | Out-Null

# 4. Pool d'applications sous le compte de service (nécessaire pour Kerberos avec SPN sur ce compte)
$mdpFichier = "C:\GIC\secrets\$CompteService.txt"
if (-not (Test-Path $mdpFichier)) { throw "$mdpFichier absent : lancez 04 d'abord." }
$mdp = (Get-Content $mdpFichier)[1]
if (-not (Test-Path "IIS:\AppPools\GIC")) { New-WebAppPool -Name "GIC" | Out-Null }
Set-ItemProperty "IIS:\AppPools\GIC" -Name managedRuntimeVersion -Value ""     # pas de .NET : simple proxy
Set-ItemProperty "IIS:\AppPools\GIC" -Name processModel -Value @{ userName = "$dom\$CompteService"; password = $mdp; identityType = 3 }

# 4 bis. Certificat auto-signé (pas d'autorité interne) : créé une fois, réutilisé ensuite, exporté pour les postes
if ($AutoSigne -and -not $SansHttps) {
    $noms = @("suivi.$zone", "suivi-test.$zone")
    $existant = Get-ChildItem Cert:\LocalMachine\My | Where-Object { $_.Subject -eq "CN=suivi.$zone" -and $_.NotAfter -gt (Get-Date).AddMonths(6) } | Sort-Object NotAfter -Descending | Select-Object -First 1
    if ($existant) { Write-Host "Certificat auto-signé existant réutilisé (expire le $($existant.NotAfter.ToShortDateString()))."; $certificat = $existant }
    else {
        $certificat = New-SelfSignedCertificate -DnsName $noms -CertStoreLocation Cert:\LocalMachine\My -FriendlyName "GIC - suivi (auto-signé)" `
            -KeyAlgorithm RSA -KeyLength 2048 -HashAlgorithm SHA256 -NotAfter (Get-Date).AddYears(5) -KeyExportPolicy NonExportable
        Write-Host "Certificat auto-signé créé pour $($noms -join ', '), valable jusqu'au $($certificat.NotAfter.ToShortDateString())."
    }
    $Empreinte = $certificat.Thumbprint
    New-Item -ItemType Directory -Path C:\GIC\deploy -Force | Out-Null
    Export-Certificate -Cert $certificat -FilePath C:\GIC\deploy\gic-serveur.cer -Type CERT -Force | Out-Null
    # Le serveur lui-même doit l'approuver (verifier.ps1 appelle https://suivi-test… depuis la console)
    if (-not (Get-ChildItem Cert:\LocalMachine\Root | Where-Object Thumbprint -eq $Empreinte)) { Import-Certificate -FilePath C:\GIC\deploy\gic-serveur.cer -CertStoreLocation Cert:\LocalMachine\Root | Out-Null }
    Write-Host "Empreinte : $Empreinte — fichier à joindre au kit de l'agent : C:\GIC\deploy\gic-serveur.cer"
}

# 5. Sites
$sites = @{ "suivi-test" = @{ port = 8001; env = "test" }; "suivi" = @{ port = 8000; env = "prod" } }
foreach ($nom in $sites.Keys) {
    $hote = "$nom.$zone"; $racine = "C:\GIC\$($sites[$nom].env)\site"; New-Item -ItemType Directory -Path $racine -Force | Out-Null
    # Création par le lecteur IIS:\ (New-Website / Get-Website -Name sont capricieux : « référence d'objet non définie »)
    $existe = Get-ChildItem IIS:\Sites | Where-Object { $_.Name -eq $nom }
    if (-not $existe) {
        Write-Host "  $nom : création du site (http://$hote -> $racine)"
        $id = ((Get-ChildItem IIS:\Sites | Measure-Object -Property Id -Maximum).Maximum + 1)
        New-Item "IIS:\Sites\$nom" -Id $id -PhysicalPath $racine -Bindings @{ protocol = "http"; bindingInformation = "*:80:$hote" } | Out-Null
    } else { Write-Host "  $nom : site existant" }
    Set-ItemProperty "IIS:\Sites\$nom" -Name applicationPool -Value "GIC"
    if (-not $SansHttps) {
        if (-not $Empreinte) { throw "Indiquez -Empreinte du certificat, -AutoSigne (pas d'autorité interne) ou -SansHttps." }
        $liaisons = (Get-ItemProperty "IIS:\Sites\$nom" -Name bindings).Collection
        if (-not ($liaisons | Where-Object { $_.protocol -eq "https" -and $_.bindingInformation -eq "*:443:$hote" })) {
            Write-Host "  $nom : liaison https *:443:$hote (SNI)"
            New-ItemProperty "IIS:\Sites\$nom" -Name bindings -Value @{ protocol = "https"; bindingInformation = "*:443:$hote"; sslFlags = 1 } | Out-Null
        }
        # Certificat attaché au couple nom d'hôte:443 dans HTTP.sys (netsh : indépendant du module IIS)
        $deja = & netsh http show sslcert hostnameport="${hote}:443" 2>$null | Select-String -Pattern $Empreinte -Quiet
        if (-not $deja) {
            Write-Host "  $nom : certificat $Empreinte attaché à ${hote}:443"
            & netsh http delete sslcert hostnameport="${hote}:443" 2>$null | Out-Null
            $r = & netsh http add sslcert hostnameport="${hote}:443" certhash=$Empreinte appid="{4dc3e181-e14b-4a21-b022-59fc669b0914}" certstorename=MY
            if ($LASTEXITCODE -ne 0) { throw "netsh http add sslcert a échoué : $r" }
        }
    }
    # Authentification : Windows seule, fournisseur Negotiate uniquement (pas de NTLM), anonyme désactivée
    # Les sections d'authentification sont verrouillées au niveau serveur (overrideModeDefault="Deny") :
    # on les écrit dans applicationHost.config, dans un bloc <location path="<site>">, ce qui est toujours
    # permis et ne touche que ce site — les autres sites IIS du serveur gardent leurs réglages.
    $apphost = "MACHINE/WEBROOT/APPHOST"
    Write-Host "  $nom : authentification Windows (Negotiate seul), anonyme désactivée"
    Set-WebConfigurationProperty -PSPath $apphost -Location $nom -Filter "system.webServer/security/authentication/anonymousAuthentication" -Name enabled -Value $false
    Set-WebConfigurationProperty -PSPath $apphost -Location $nom -Filter "system.webServer/security/authentication/windowsAuthentication" -Name enabled -Value $true
    Set-WebConfigurationProperty -PSPath $apphost -Location $nom -Filter "system.webServer/security/authentication/windowsAuthentication" -Name useAppPoolCredentials -Value $true
    # Fournisseurs : Negotiate seul. La liste héritée du serveur contient Negotiate et NTLM ; on retire
    # NTLM pour ce site et on n'ajoute Negotiate que s'il manque (relançable sans doublon).
    $prov = "system.webServer/security/authentication/windowsAuthentication/providers"
    if (Get-WebConfiguration -PSPath $apphost -Location $nom -Filter "$prov/add[@value='NTLM']") {
        Remove-WebConfigurationProperty -PSPath $apphost -Location $nom -Filter $prov -Name "." -AtElement @{ value = "NTLM" }
    }
    if (-not (Get-WebConfiguration -PSPath $apphost -Location $nom -Filter "$prov/add[@value='Negotiate']")) {
        Add-WebConfigurationProperty -PSPath $apphost -Location $nom -Filter $prov -Name "." -Value @{ value = "Negotiate" }
    }
    $restants = (Get-WebConfiguration -PSPath $apphost -Location $nom -Filter "$prov/add" | ForEach-Object { $_.value }) -join ", "
    Write-Host "Site $nom : fournisseurs d'authentification = $restants"

    # web.config : statiques servis par IIS, tout le reste vers Uvicorn avec identité et protocole
    $port = $sites[$nom].port; $statiques = "C:\GIC\$($sites[$nom].env)\static_collecte"
    @"
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
  <system.webServer>
    <rewrite>
      <rules>
        <rule name="Statiques" stopProcessing="true">
          <match url="^static/(.*)" />
          <action type="Rewrite" url="/static/{R:1}" />
        </rule>
        <rule name="Vers Uvicorn" stopProcessing="true">
          <match url="(.*)" />
          <conditions><add input="{REQUEST_URI}" pattern="^/static/" negate="true" /></conditions>
          <serverVariables>
            <set name="HTTP_X_REMOTE_USER" value="{LOGON_USER}" />
            <set name="HTTP_X_FORWARDED_PROTO" value="https" />
            <set name="HTTP_X_FORWARDED_HOST" value="{HTTP_HOST}" />
          </serverVariables>
          <action type="Rewrite" url="http://127.0.0.1:$port/{R:1}" />
        </rule>
      </rules>
    </rewrite>
    <security><requestFiltering><requestLimits maxAllowedContentLength="52428800" /></requestFiltering></security>
  </system.webServer>
</configuration>
"@ | Set-Content "$racine\web.config" -Encoding UTF8
    Write-Host "  $nom : web.config écrit (statiques par IIS, le reste vers 127.0.0.1:$port)"
    if (-not (Test-Path "$racine\static")) {
        Write-Host "  $nom : jonction $racine\static -> $statiques"
        New-Item -ItemType Junction -Path "$racine\static" -Target $statiques | Out-Null
    }
    Write-Host "Site $nom : https://$hote -> 127.0.0.1:$port"
}


# 6. Pare-feu : 443 depuis le LAN ; 8000/8001 bloqués hors de la machine (Uvicorn n'écoute que sur 127.0.0.1, ceinture et bretelles)
#    Par netsh : les cmdlets *-NetFirewallRule passent par WMI et se figent sur ce serveur.
Write-Host "Pare-feu : règles GIC..."
function Assurer-Regle($nom, $arguments) {
    $null = & netsh advfirewall firewall show rule name="$nom" 2>&1
    if ($LASTEXITCODE -eq 0) { Write-Host "  règle « $nom » : existante"; return }
    $r = & netsh advfirewall firewall add rule name="$nom" dir=in protocol=TCP $arguments 2>&1
    if ($LASTEXITCODE -ne 0) { throw "netsh pare-feu ($nom) : $r" }
    Write-Host "  règle « $nom » : créée"
}
Assurer-Regle "GIC - HTTPS LAN" @("localport=443", "remoteip=192.168.2.0/24", "action=allow")
Assurer-Regle "GIC - Bloquer Uvicorn externe" @("localport=8000,8001", "action=block")

# 7. Variables serveur que les règles de réécriture ont le droit de poser (sinon IIS les ignore).
#    Liste globale d'applicationHost.config. Écrite par appcmd, en dernier et dans un processus séparé :
#    le module PowerShell d'IIS se fige sur cette section, et appcmd ne doit pas être mêlé à ses écritures.
$appcmd = "$env:windir\system32\inetsrv\appcmd.exe"
# Proxy ARR : sans lui, une règle qui réécrit vers http://127.0.0.1:<port>/ échoue en 500.50
$proxy = & $appcmd list config -section:system.webServer/proxy 2>&1 | Out-String
if ($proxy -match 'enabled="true"') { Write-Host "Proxy ARR : déjà activé" }
else {
    $r = & $appcmd set config -section:system.webServer/proxy /enabled:"True" /preserveHostHeader:"True" /commit:apphost 2>&1
    if ($LASTEXITCODE -ne 0) { throw "appcmd proxy ARR : $r" }
    Write-Host "Proxy ARR : activé"
}
Write-Host "Variables serveur autorisées pour la réécriture (X-Remote-User, X-Forwarded-Proto, X-Forwarded-Host)..."
# Jamais au niveau d'un site : une entrée présente à la fois pour un site et pour le serveur fait
# échouer la lecture de la configuration (« existe déjà », 500.50 / code 183). On nettoie les sites.
foreach ($nom in $sites.Keys) { & $appcmd clear config "$nom" -section:system.webServer/rewrite/allowedServerVariables /commit:apphost 2>&1 | Out-Null }
$actuelles = & $appcmd list config -section:system.webServer/rewrite/allowedServerVariables 2>&1 | Out-String
foreach ($v in "HTTP_X_REMOTE_USER", "HTTP_X_FORWARDED_PROTO", "HTTP_X_FORWARDED_HOST") {
    if ($actuelles -match "name=`"$v`"") { Write-Host "  $v : déjà autorisée"; continue }
    $r = & $appcmd set config -section:system.webServer/rewrite/allowedServerVariables "/+[name='$v']" /commit:apphost 2>&1
    if ($LASTEXITCODE -ne 0) { throw "appcmd allowedServerVariables ($v) : $r" }
    Write-Host "  $v : autorisée"
}

Write-Host "`nTERMINÉ. Prochaine étape (ticket S07) : installer l'application dans C:\GIC\test\app, créer le service NSSM GIC-Test, puis ouvrir https://suivi-test.$zone/identite/qui-suis-je depuis un poste."
Stop-Transcript | Out-Null
