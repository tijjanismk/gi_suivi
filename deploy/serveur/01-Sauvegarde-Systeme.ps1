<#
.SYNOPSIS
  P01 — Sauvegarde complète de l'état du système vers le second disque.
  Avec -Planifier : met en place les protections quotidiennes.

.USAGE
    .\01-Sauvegarde-Systeme.ps1                 # sauvegarde complète unique vers D:
    .\01-Sauvegarde-Systeme.ps1 -Planifier      # + système chaque nuit, données D→C, clichés 2x/jour
    .\01-Sauvegarde-Systeme.ps1 -Verifier       # liste les sauvegardes disponibles

.VOLUMES (serveur de 2 x 2 To)
  Système C: ~35 Go -> image complète + différences quotidiennes : 100-150 Go/an, versions anciennes
  supprimées automatiquement quand la place manque. Miroir D->C : taille constante des données
  (~42 Go, ALASSANE exclu). Clichés : plafonnés à 10 % de D:. Total < 400 Go par disque.
  C:\SAUVEGARDES_D est exclu de la sauvegarde système pour ne pas être sauvegardé deux fois.

.LIMITE
  Les deux disques sont dans la même machine : cela protège d'une panne de
  disque ou d'une erreur, pas d'un vol, d'un incendie ni d'un rançongiciel.
  Copier D:\WindowsImageBackup et C:\SAUVEGARDES_D sur un disque externe
  chaque semaine (action A9).
#>
param(
    [string]$Cible = "D:",
    [switch]$Planifier,
    [switch]$Verifier,
    [string[]]$ExclureDeD = @("ALASSANE", "SAUVEGARDES", "WindowsImageBackup")
)
$ErrorActionPreference = "Stop"
$journaux = "D:\SAUVEGARDES\journaux"; New-Item -ItemType Directory -Path $journaux -Force | Out-Null
Start-Transcript -Path "$journaux\01-sauvegarde_$(Get-Date -Format yyyyMMdd_HHmm).log" | Out-Null

if ($Verifier) {
    & wbadmin get versions -backupTarget:$Cible
    Write-Host "`nClichés instantanés sur D: :"; & vssadmin list shadows /for=D: | Select-String "Heure|Creation" | Select-Object -Last 5
    Stop-Transcript | Out-Null; exit 0
}

# 1. Fonctionnalité
if (-not (Get-WindowsFeature Windows-Server-Backup).Installed) {
    Write-Host "Installation de Windows Server Backup..."
    Install-WindowsFeature Windows-Server-Backup | Out-Null
}

# 2. Sauvegarde complète unique (système + état du contrôleur de domaine)
Write-Host "Sauvegarde complète vers $Cible — comptez 20 à 60 minutes."
& wbadmin start backup -backupTarget:$Cible -include:C: -exclude:C:\SAUVEGARDES_D -allCritical -systemState -vssFull -quiet
if ($LASTEXITCODE -ne 0) { throw "wbadmin a échoué (code $LASTEXITCODE). Voir le journal." }
Write-Host "`nSauvegardes disponibles :"
& wbadmin get versions -backupTarget:$Cible | Select-String "sauvegarde|Backup time|Version"

if (-not $Planifier) { Stop-Transcript | Out-Null; exit 0 }

# 3. Protection quotidienne du système : tâche planifiée (la ligne de commande
#    de wbadmin exige un disque dédié pour planifier ; une tâche contourne cela)
$cmdSys = "wbadmin start backup -backupTarget:$Cible -include:C: -exclude:C:\SAUVEGARDES_D -allCritical -systemState -vssFull -quiet"
Register-ScheduledTask -TaskName "GIC - Sauvegarde systeme" -Force `
    -Action (New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c $cmdSys") `
    -Trigger (New-ScheduledTaskTrigger -Daily -At 22:00) `
    -User "SYSTEM" -RunLevel Highest | Out-Null
Write-Host "Tâche « GIC - Sauvegarde systeme » : chaque nuit 22:00."

# 4. Données du bureau D: → C:\SAUVEGARDES_D (miroir), sauf dossiers exclus
New-Item -ItemType Directory -Path C:\SAUVEGARDES_D -Force | Out-Null
$xd = ($ExclureDeD | ForEach-Object { "`"D:\$_`"" }) -join " "
$cmdRobo = "robocopy D:\ C:\SAUVEGARDES_D /MIR /XD $xd `"D:\`$RECYCLE.BIN`" `"D:\System Volume Information`" /R:1 /W:1 /NP /LOG:C:\SAUVEGARDES_D\_journal.txt"
Register-ScheduledTask -TaskName "GIC - Donnees D vers C" -Force `
    -Action (New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c $cmdRobo") `
    -Trigger (New-ScheduledTaskTrigger -Daily -At 23:30) `
    -User "SYSTEM" -RunLevel Highest | Out-Null
Write-Host "Tâche « GIC - Donnees D vers C » : chaque nuit 23:30 (exclus : $($ExclureDeD -join ', '))."

# 5. Clichés instantanés sur D:, 7h30 et 13h30 (Versions précédentes)
& vssadmin add shadowstorage /for=D: /on=D: /maxsize=10% 2>$null | Out-Null
$decl = @((New-ScheduledTaskTrigger -Daily -At 07:30), (New-ScheduledTaskTrigger -Daily -At 13:30))
Register-ScheduledTask -TaskName "GIC - Cliches D" -Force `
    -Action (New-ScheduledTaskAction -Execute "wmic.exe" -Argument "shadowcopy call create Volume=D:\") `
    -Trigger $decl -User "SYSTEM" -RunLevel Highest | Out-Null
& wmic shadowcopy call create Volume=D:\ | Out-Null
Write-Host "Tâche « GIC - Cliches D » : 07:30 et 13:30. Premier cliché créé."

Write-Host "`nÀ FAIRE À LA MAIN : restaurer un fichier de test depuis C:\SAUVEGARDES_D et depuis « Versions précédentes », puis noter le résultat dans docs/exploitation.md."
Stop-Transcript | Out-Null
