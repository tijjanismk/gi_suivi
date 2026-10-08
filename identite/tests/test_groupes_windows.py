import sys
import types

import pytest
from django.test import override_settings

from identite.groupes import lire_groupes
from identite.groupes_windows import groupes_de, nom_de_compte


def test_nom_de_compte():
    assert nom_de_compte("GICONSEILS\\Jean.Traore") == "Jean.Traore"
    assert nom_de_compte("jean@giconseils.local") == "jean"
    assert nom_de_compte("  jean ") == "jean"
    assert nom_de_compte("") == ""


@pytest.fixture
def win32net_simule(monkeypatch):
    """Un faux module win32net : les tests tournent sur Linux (CI) comme sur le poste."""
    appels: list[tuple] = []
    module = types.ModuleType("win32net")

    def NetUserGetGroups(serveur, compte):  # noqa: N802 — nom de l'API Windows
        appels.append(("globaux", serveur, compte))
        return [("GI-Direction", 7), ("Utilisa. du domaine", 7)] if compte == "odicko" else []

    def NetUserGetLocalGroups(serveur, compte, drapeaux):  # noqa: N802
        appels.append(("locaux", serveur, compte, drapeaux))
        return ["Utilisateurs"] if compte else []

    module.NetUserGetGroups = NetUserGetGroups
    module.NetUserGetLocalGroups = NetUserGetLocalGroups
    monkeypatch.setitem(sys.modules, "win32net", module)
    return appels


def test_groupes_globaux_et_locaux_reunis(win32net_simule):
    assert groupes_de("GICONSEILS\\odicko") == [
        "GI-Direction",
        "Utilisa. du domaine",
        "Utilisateurs",
    ]
    assert win32net_simule == [("globaux", None, "odicko"), ("locaux", None, "odicko", 1)]


def test_personne_sans_groupe_global(win32net_simule):
    assert groupes_de("stagiaire@giconseils.local") == ["Utilisateurs"]
    assert groupes_de("GICONSEILS\\") == []


@override_settings(IDENTITE_SERVEUR_GROUPES="AD-SERVEUR")
def test_autre_serveur_interroge(win32net_simule):
    groupes_de("odicko")
    assert win32net_simule[0] == ("globaux", "AD-SERVEUR", "odicko")


@override_settings(
    IDENTITE_SOURCE="iis", IDENTITE_LECTEUR_GROUPES="identite.groupes_windows.groupes_de"
)
def test_branche_sur_lire_groupes(win32net_simule):
    assert "GI-Direction" in lire_groupes("giconseils\\odicko")
