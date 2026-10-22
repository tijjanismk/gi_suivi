from __future__ import annotations

from datetime import date

import pytest

IIS = {
    "IDENTITE_SOURCE": "iis",
    "IDENTITE_LECTEUR_GROUPES": "administratif.tests.conftest.groupes",
}
DIR = {"REMOTE_USER": "GICONSEILS\\directrice"}
VUE = {"REMOTE_USER": "GICONSEILS\\visionneuse"}
AWA = {"REMOTE_USER": "GICONSEILS\\a.traore"}
AUJOURDHUI = date(2026, 10, 22)


def groupes(login: str) -> list[str]:
    return {
        "giconseils\\directrice": ["GI-Direction"],
        "giconseils\\visionneuse": ["GI-Direction-Lecture"],
    }.get(login, [])


@pytest.fixture
def partage(tmp_path, settings):
    """Un dossier local qui joue le partage GIC."""
    settings.PARTAGE_GIC = str(tmp_path)
    return tmp_path


@pytest.fixture
def jeu(partage, db):
    """Le jeu fictif de `administratif.demo`, daté du 22/10/2026."""
    from administratif import demo

    return demo.remplir(partage, AUJOURDHUI)
