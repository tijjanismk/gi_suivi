# Noms d'hôte de l'application, par environnement (ADR 0009). Seul endroit où ils sont écrits :
# installer.ps1, verifier.ps1, serveur\06-DNS-SPN.ps1 et serveur\08-Python-IIS.ps1 lisent ce tableau
# (tests\test_noms_hotes.py le contrôle). Noms courts, sans la zone DNS.
# Le premier nom est le nom principal (adresse donnée aux utilisateurs) ; les suivants restent servis
# comme alias, le temps que tous les postes approuvent le nouveau certificat et que l'agent change d'adresse.
$ZoneGic = "giconseils.local"
$NomsHotes = [ordered]@{
    test = @("app", "suivi-test")
    prod = @("suivi")
}

# Noms complets d'un environnement (app.giconseils.local, …), nom principal en premier
function Hotes-Complets([string]$Environnement, [string]$Zone = $ZoneGic) {
    $NomsHotes[$Environnement] | ForEach-Object { "$_.$Zone" }
}

# Tous les noms courts, tous environnements confondus (DNS, SPN, certificat)
function Tous-Les-Noms {
    $NomsHotes.Values | ForEach-Object { $_ }
}
