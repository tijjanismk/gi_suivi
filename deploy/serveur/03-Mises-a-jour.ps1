<#
.SYNOPSIS
  P03 — Recherche, télécharge et installe les mises à jour Windows en
  attente, puis programme les suivantes (installation automatique, redémarrage
  le samedi à 03:00). Utilise l'API Windows Update intégrée : aucun module à
  installer, pas d'accès à la galerie PowerShell nécessaire.

.USAGE
    .\03-Mises-a-jour.ps1                 # recherche et installe, demande avant de redémarrer
    .\03-Mises-a-jour.ps1 -Redemarrer     # redémarre automatiquement si nécessaire
    .\03-Mises-a-jour.ps1 -SeulementLister

.PREALABLE
  Sauvegarde P01 du jour. Fenêtre hors heures de bureau : le serveur est le
  seul contrôleur de domaine, son redémarrage coupe les ouvertures de session.
#>
param([switch]$Redemarrer, [switch]$SeulementLister)
$ErrorActionPreference = "Stop"
$journaux = "D:\SAUVEGARDES\journaux"; New-Item -ItemType Directory -Path $journaux -Force | Out-Null
Start-Transcript -Path "$journaux\03-maj_$(Get-Date -Format yyyyMMdd_HHmm).log" | Out-Null

Write-Host "Dernière mise à jour installée : $((Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 1).InstalledOn)"

$session  = New-Object -ComObject Microsoft.Update.Session
$chercheur = $session.CreateUpdateSearcher()
Write-Host "Recherche des mises à jour (peut prendre plusieurs minutes)..."
$resultat = $chercheur.Search("IsInstalled=0 and IsHidden=0 and Type='Software'")
$maj = $resultat.Updates
if ($maj.Count -eq 0) { Write-Host "Aucune mise à jour en attente."; }
else {
    Write-Host "$($maj.Count) mise(s) à jour disponible(s) :"
    foreach ($m in $maj) { "  - {0}  ({1:N0} Mo)" -f $m.Title, ($m.MaxDownloadSize/1MB) }
}
if ($SeulementLister -or $maj.Count -eq 0) { Stop-Transcript | Out-Null; exit 0 }

$coll = New-Object -ComObject Microsoft.Update.UpdateColl
foreach ($m in $maj) { if (-not $m.EulaAccepted) { $m.AcceptEula() }; [void]$coll.Add($m) }

Write-Host "`nTéléchargement..."
$dl = $session.CreateUpdateDownloader(); $dl.Updates = $coll
$rd = $dl.Download()
if ($rd.ResultCode -ne 2) { throw "Téléchargement incomplet (code $($rd.ResultCode))." }

Write-Host "Installation..."
$inst = $session.CreateUpdateInstaller(); $inst.Updates = $coll
$ri = $inst.Install()
Write-Host "Résultat : code $($ri.ResultCode) (2 = succès)  Redémarrage requis : $($ri.RebootRequired)"
for ($i = 0; $i -lt $coll.Count; $i++) { "  {0} -> code {1}" -f $coll.Item($i).Title, $ri.GetUpdateResult($i).ResultCode }

# Programmer les mises à jour suivantes : installation automatique, redémarrage planifié samedi 03:00
# (une GPO de domaine « Configuration des mises à jour automatiques » prendrait le dessus si elle existe)
$au = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU"
New-Item -Path $au -Force | Out-Null
Set-ItemProperty $au -Name NoAutoUpdate -Value 0
Set-ItemProperty $au -Name AUOptions -Value 4           # télécharger et installer automatiquement
Set-ItemProperty $au -Name ScheduledInstallDay -Value 7  # samedi
Set-ItemProperty $au -Name ScheduledInstallTime -Value 3 # 03:00
Set-ItemProperty $au -Name NoAutoRebootWithLoggedOnUsers -Value 0
Write-Host "`nMises à jour automatiques programmées : samedi 03:00."

Stop-Transcript | Out-Null
if ($ri.RebootRequired) {
    if ($Redemarrer) { Write-Host "Redémarrage dans 60 s..."; shutdown /r /t 60 /c "Mises à jour GIC - P03" }
    else { Write-Host "`nREDÉMARRAGE REQUIS. Lancez : shutdown /r /t 60  (hors heures de bureau)" }
}
