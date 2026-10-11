# Script de démarrage de l'ordinateur, lancé par la GPO « GI-Suivi - Agent » (sous SYSTEM, avant
# toute ouverture de session). Installe ou met à jour l'agent seulement si le kit publié dans SYSVOL
# diffère de ce qui est installé ; sinon ne fait rien (démarrage normal, rien n'est arrêté).
# Journal : C:\ProgramData\GiSuivi\installation-gpo.log
$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'GiSuivi'          # le kit, à côté de ce script dans SYSVOL
$donnees = Join-Path $env:ProgramData 'GiSuivi'
$local = Join-Path $donnees 'kit'
$journal = Join-Path $donnees 'installation-gpo.log'
New-Item -ItemType Directory -Force $donnees | Out-Null
function Ecrire($texte) { Add-Content -Path $journal -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $texte" -Encoding UTF8 }

try {
    $exeKit = Join-Path $source 'dist\gisuivi-agent\gisuivi-agent.exe'
    if (-not (Test-Path $exeKit)) { Ecrire "Kit introuvable dans $source : rien à faire."; exit 0 }
    $exePoste = Join-Path $env:ProgramFiles 'GI-CONSEILS\GiSuivi\gisuivi-agent.exe'
    $cfgKit = Join-Path $source 'config.json'
    $cfgPoste = Join-Path $donnees 'config.json'
    $cerKit = Join-Path $source 'gic-serveur.cer'

    $memeAgent = (Test-Path $exePoste) -and ((Get-FileHash $exeKit).Hash -eq (Get-FileHash $exePoste).Hash)
    $memeConfig = (-not (Test-Path $cfgKit)) -or ((Test-Path $cfgPoste) -and
        ((Get-Content $cfgKit -Raw -Encoding UTF8).Trim() -eq (Get-Content $cfgPoste -Raw -Encoding UTF8).Trim()))
    $certificatPresent = $true
    if (Test-Path $cerKit) {
        $empreinte = (New-Object Security.Cryptography.X509Certificates.X509Certificate2 $cerKit).Thumbprint
        $certificatPresent = [bool](Get-ChildItem Cert:\LocalMachine\Root | Where-Object Thumbprint -eq $empreinte)
    }
    $service = Get-Service GiSuivi -ErrorAction SilentlyContinue
    if ($memeAgent -and $memeConfig -and $certificatPresent -and $service) {
        if ($service.Status -ne 'Running') { Start-Service GiSuivi; Ecrire "À jour ; service redémarré." }
        exit 0
    }

    Ecrire "Installation ou mise à jour (agent identique : $memeAgent, configuration identique : $memeConfig, certificat présent : $certificatPresent, service présent : $([bool]$service))."
    & robocopy.exe $source $local /MIR /R:2 /W:5 /NFL /NDL /NJH /NJS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "Copie du kit depuis $source en échec (robocopy $LASTEXITCODE)." }
    Get-ChildItem -LiteralPath $local -Recurse | Unblock-File
    $sortie = & powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $local 'installer-poste.ps1') 2>&1
    $sortie | ForEach-Object { Ecrire "  $_" }
    if ($LASTEXITCODE -ne 0) { throw "installer-poste.ps1 a échoué (code $LASTEXITCODE)." }
    Ecrire "Terminé."
} catch {
    Ecrire "ÉCHEC : $($_.Exception.Message)"
    exit 1
}
