# Libère un port local : arrête tout processus qui l'écoute encore, avec ses processus enfants.
# Sous Windows, venv\Scripts\python.exe n'est qu'un lanceur qui démarre le vrai interpréteur
# (C:\Python314\python.exe) : arrêter le service tue le lanceur, l'interpréteur peut survivre, garder
# le port et continuer de servir l'ancienne version. netstat + taskkill /T : pas de WMI (qui se fige
# sur ce serveur). Chargé par service.ps1 et installer.ps1 : . (Join-Path $PSScriptRoot 'liberer-port.ps1')

function Get-PidsEcoutant([int]$Port) {
    & netstat -ano | Select-String ":$Port\s" | Select-String "LISTENING|ECOUTE|ÉCOUTE" |
        ForEach-Object { ($_.ToString().Trim() -split '\s+')[-1] } |
        Where-Object { $_ -match '^\d+$' -and [int]$_ -gt 4 } | Sort-Object -Unique
}

function Liberer-Port([int]$Port) {
    for ($essai = 1; $essai -le 10; $essai++) {
        $pids = @(Get-PidsEcoutant $Port)
        if (-not $pids.Count) { return }
        foreach ($p in $pids) {
            Write-Warning "Processus $p écoute encore sur $Port : arrêté avec ses enfants."
            & taskkill /F /T /PID $p 2>&1 | Out-Null
        }
        Start-Sleep -Seconds 1
    }
    if (@(Get-PidsEcoutant $Port).Count) { throw "Le port $Port reste occupé après 10 essais (netstat -ano | findstr :$Port)." }
}
