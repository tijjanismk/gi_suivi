# Arrêt propre de l'agent : on lui envoie le message de fermeture de session (WM_QUERYENDSESSION) ;
# il écrit ses segments en attente (jusqu'à 5 min) dans le tampon, puis s'arrête.
# Tuer le processus perdrait ces segments : ce n'est que le dernier recours, après 20 s.
# Chargé par installer-poste.ps1 et desinstaller-poste.ps1 (. .\arreter-agent.ps1 ; Stop-AgentProprement).
# Limite : seule la session courante est atteinte ; les agents des autres sessions sont arrêtés de force.

function Stop-AgentProprement {
    if (-not ('GiSuivi.Fenetre' -as [type])) {
        Add-Type -Namespace GiSuivi -Name Fenetre -MemberDefinition @'
[DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern IntPtr FindWindow(string classe, string titre);
[DllImport("user32.dll")] public static extern IntPtr SendMessageTimeout(IntPtr h, uint msg, IntPtr w, IntPtr l, uint flags, uint ms, out IntPtr res);
'@
    }
    # [NullString]::Value : un $null passé tel quel deviendrait "" et ne trouverait aucune fenêtre
    $h = [GiSuivi.Fenetre]::FindWindow('GiSuiviSession', [NullString]::Value)
    if ($h -ne [IntPtr]::Zero) {
        $r = [IntPtr]::Zero
        [void][GiSuivi.Fenetre]::SendMessageTimeout($h, 0x11, [IntPtr]::Zero, [IntPtr]::Zero, 2, 5000, [ref]$r)
        $fin = (Get-Date).AddSeconds(20)
        while ((Get-Process gisuivi-agent -ErrorAction SilentlyContinue) -and (Get-Date) -lt $fin) { Start-Sleep -Milliseconds 500 }
    }
    $restants = Get-Process gisuivi-agent -ErrorAction SilentlyContinue
    if ($restants) {
        $restants | Stop-Process -Force
        Write-Warning ("{0} agent(s) arrete(s) de force (autre session ou sans reponse) : jusqu'a 5 min de segments perdus." -f @($restants).Count)
    } else {
        Write-Host "Agent arrete proprement."
    }
    Start-Sleep -Seconds 1
}
