<#
.SYNOPSIS
  Serveur — Crée ou met à jour les tâches planifiées d'un environnement.
  Toutes tournent sous SYSTEM. AD-SERVEUR est contrôleur de domaine : le droit « ouvrir une
  session en tant que tâche » y est fixé par la stratégie existante « Default Domain Controllers
  Policy », qui ne contient pas svc-application et retire ce droit à chaque rafraîchissement ;
  sous ce compte, les tâches ne démarraient jamais (résultat 267011). La stratégie n'est pas
  modifiée (rien d'existant n'est touché sur le serveur). -CompteService reste possible ailleurs.

.USAGE
    .\taches.ps1 -Env prod
    .\taches.ps1 -Env test -SansSauvegarde      # la sauvegarde PG est commune : une seule fois suffit
    .\taches.ps1 -Env prod -Lister
#>
param(
    [Parameter(Mandatory)][ValidateSet("test", "prod")][string]$Env,
    [switch]$SansSauvegarde, [switch]$Lister,
    [string]$CompteService = ""                  # vide : SYSTEM (voir ci-dessus)
)
$ErrorActionPreference = "Stop"
$base = "C:\GIC\$Env"; $prefixe = "GIC $Env -"
if ($Lister) { Get-ScheduledTask | Where-Object TaskName -like "GIC*" | Select-Object TaskName, State, @{n="Prochaine";e={(Get-ScheduledTaskInfo $_).NextRunTime}} | Format-Table -AutoSize; exit 0 }

$compte = "SYSTEM"; $mdp = $null
if ($CompteService) {
    $mdpFichier = "C:\GIC\secrets\$CompteService.txt"
    $compte = (Get-Content $mdpFichier)[0]; $mdp = (Get-Content $mdpFichier)[1]
}
$py = "$base\venv\Scripts\python.exe"
$reglages = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 2) -StartWhenAvailable -MultipleInstances IgnoreNew -RunOnlyIfNetworkAvailable:$false

function Tache($nom, $commande, $declencheurs, $compteExec = $compte, $mdpExec = $mdp) {
    $action = New-ScheduledTaskAction -Execute $py -Argument "manage.py $commande" -WorkingDirectory "$base\app"
    $p = @{ TaskName = "$prefixe $nom"; Action = $action; Trigger = $declencheurs; Settings = $reglages; Force = $true; RunLevel = "Limited" }
    if ($compteExec -eq "SYSTEM") { Register-ScheduledTask @p -User "SYSTEM" | Out-Null }
    else { Register-ScheduledTask @p -User $compteExec -Password $mdpExec | Out-Null }
    Write-Host "Tâche : $prefixe $nom ($compteExec)"
}

# Tâches métier (sous SYSTEM par défaut, voir l'en-tête)
Tache "purge"         "suivi_purger"        (New-ScheduledTaskTrigger -Daily -At 02:00)
Tache "recalcul"      "suivi_recalculer"    (New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Minutes 10))
Tache "postes muets"  "suivi_postes_muets"  (New-ScheduledTaskTrigger -Once -At (Get-Date).Date.AddHours(7) -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration (New-TimeSpan -Hours 12))
# Le lundi à 00:05 : compteur hebdomadaire de démarrages des agents remis à zéro (alerte orange)
Tache "démarrages hebdo" "suivi_postes_muets --remettre-demarrages" (New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 00:05)

# Sauvegarde PostgreSQL (commune aux deux bases), sous SYSTEM
if (-not $SansSauvegarde) {
    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$base\app\deploy\sauvegarde_pg.ps1`""
    Register-ScheduledTask -TaskName "GIC - Sauvegarde PostgreSQL" -Action $action -Trigger (New-ScheduledTaskTrigger -Daily -At 01:00) -Settings $reglages -User "SYSTEM" -RunLevel Highest -Force | Out-Null
    Write-Host "Tâche : GIC - Sauvegarde PostgreSQL (01:00)"
}

# Contrôle de santé toutes les 5 minutes : écrit un événement Windows en cas d'échec (source « GIC »)
$port = if ($Env -eq "prod") { 8000 } else { 8001 }
$sante = @"
try { `$r = Invoke-WebRequest -Uri 'http://127.0.0.1:$port/api/sante' -UseBasicParsing -TimeoutSec 15; if (`$r.StatusCode -ne 200) { throw "HTTP `$(`$r.StatusCode)" } }
catch { if (-not [System.Diagnostics.EventLog]::SourceExists('GIC')) { New-EventLog -LogName Application -Source 'GIC' }; Write-EventLog -LogName Application -Source 'GIC' -EntryType Error -EventId 1001 -Message "GIC $Env ne répond pas : `$(`$_.Exception.Message)" }
`$libre = (Get-Volume D).SizeRemaining / (Get-Volume D).Size; if (`$libre -lt 0.2) { if (-not [System.Diagnostics.EventLog]::SourceExists('GIC')) { New-EventLog -LogName Application -Source 'GIC' }; Write-EventLog -LogName Application -Source 'GIC' -EntryType Warning -EventId 1002 -Message "Disque D: à `$([math]::Round(`$libre*100)) % libre" }
"@
$fichierSante = "C:\GIC\outils\sante_$Env.ps1"; New-Item -ItemType Directory -Path C:\GIC\outils -Force | Out-Null
$sante | Set-Content $fichierSante -Encoding UTF8
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$fichierSante`""
Register-ScheduledTask -TaskName "$prefixe santé" -Action $action -Trigger (New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Minutes 5)) -Settings $reglages -User "SYSTEM" -RunLevel Highest -Force | Out-Null
Write-Host "Tâche : $prefixe santé (5 min). Les échecs apparaissent dans l'Observateur d'événements, source « GIC », id 1001/1002."
Write-Host "Pour être prévenu par courriel : Observateur d'événements > Application > filtrer source GIC > Joindre une tâche à cet événement."
