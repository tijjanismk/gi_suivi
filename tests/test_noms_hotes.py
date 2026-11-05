"""Noms d'hôte de l'application (ADR 0009) : un seul tableau, `deploy/noms-hotes.ps1`.

Les scripts de déploiement le lisent au lieu d'écrire les noms ; le kit de l'agent, qui voyage
seul sur les postes, en recopie la liste pour la zone Intranet local et envoie au nom principal.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
TABLEAU = RACINE / "deploy" / "noms-hotes.ps1"
SCRIPTS_LECTEURS = [
    "deploy/installer.ps1",
    "deploy/verifier.ps1",
    "deploy/serveur/06-DNS-SPN.ps1",
    "deploy/serveur/08-Python-IIS.ps1",
    "deploy/serveur/Tout-en-un.ps1",
]
KIT_AGENT = ["agent/installer-poste.ps1", "agent/zone-intranet.ps1"]


def lire(chemin: Path) -> str:
    return chemin.read_text(encoding="utf-8-sig")


def sans_commentaires(script: str) -> str:
    """Retire les blocs `<# … #>` et ce qui suit un `#` en début de ligne ou après une espace."""
    script = re.sub(r"<#.*?#>", "", script, flags=re.DOTALL)
    return re.sub(r"(^|\s)#.*$", r"\1", script, flags=re.MULTILINE)


def noms_par_environnement() -> dict[str, list[str]]:
    texte = lire(TABLEAU)
    listes = re.findall(r"^\s*(\w+)\s*=\s*@\(([^)]*)\)", texte, flags=re.MULTILINE)
    return {env: re.findall(r'"([a-z][a-z0-9-]*)"', liste) for env, liste in listes}


def tous_les_noms() -> list[str]:
    return [nom for noms in noms_par_environnement().values() for nom in noms]


def test_tableau_des_noms():
    noms = noms_par_environnement()
    assert set(noms) == {"test", "prod"}
    assert noms["test"][0] == "app"  # adresse donnée aux utilisateurs
    assert "suivi-test" in noms["test"]  # alias de la bascule, retiré à l'étape 8c (ADR 0009)
    assert noms["prod"][0] == "suivi"  # jusqu'à la décision GIC-Prod
    assert len(tous_les_noms()) == len(set(tous_les_noms())), "un nom sert deux environnements"


@pytest.mark.parametrize("chemin", SCRIPTS_LECTEURS)
def test_les_scripts_lisent_le_tableau(chemin):
    assert "noms-hotes.ps1" in sans_commentaires(lire(RACINE / chemin))


def test_aucun_nom_d_hote_ecrit_en_dur_dans_deploy():
    motif = re.compile(
        r"\b(?:" + "|".join(map(re.escape, tous_les_noms())) + r")\.giconseils\.local\b",
        flags=re.IGNORECASE,
    )
    en_dur = {
        str(f.relative_to(RACINE)): motif.findall(sans_commentaires(lire(f)))
        for f in (RACINE / "deploy").rglob("*.ps1")
        if f != TABLEAU
    }
    assert {f: noms for f, noms in en_dur.items() if noms} == {}


@pytest.mark.parametrize("chemin", KIT_AGENT)
def test_le_kit_de_l_agent_met_tous_les_noms_en_zone_intranet(chemin):
    texte = lire(RACINE / chemin)
    assert [nom for nom in tous_les_noms() if f"'{nom}'" not in texte] == []


def test_l_agent_envoie_au_nom_principal_de_test():
    config = json.loads(lire(RACINE / "agent" / "config-pilote.json"))
    assert config["url_api"] == f"https://{noms_par_environnement()['test'][0]}.giconseils.local"


def test_sans_commentaires():
    script = "<# app.giconseils.local #>\n$a = 1   # suivi.giconseils.local\n# x\n$b = 'y'\n"
    assert sans_commentaires(script) == "\n$a = 1   \n\n$b = 'y'\n"
