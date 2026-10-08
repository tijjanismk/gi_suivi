"""Fixtures partagées par les tests Django (docs/tests.md, section 2).

`faire_lot(n, ...)` fabrique un lot réaliste, au format que l'agent envoie à POST /api/segments.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest

PROJET_052 = r"\\AD-SERVEUR\GIC\MISSIONS_EN_COURS\GIC-HYD-ETU-052_Bargondaga"
AVIS_SOMAPEP = r"\\AD-SERVEUR\GIC\AVIS\MALI\2026-10\2026-SOMAPEP-001_recharge-nappe"


@pytest.fixture
def racines(db):
    from suivi.models import Racine

    return [
        Racine.objects.create(chemin=r"\\AD-SERVEUR\GIC\MISSIONS_EN_COURS", profondeur=1),
        Racine.objects.create(chemin=r"\\AD-SERVEUR\GIC\AVIS", profondeur=3),
    ]


@pytest.fixture
def employes(db):
    from suivi.models import Employe

    return [
        Employe.objects.create(
            sid_ad="S-1-5-21-1000-1101", login="giconseils\\a.traore", nom_affiche="Awa Traoré"
        ),
        Employe.objects.create(
            sid_ad="S-1-5-21-1000-1102", login="giconseils\\m.keita", nom_affiche="Moussa Keïta"
        ),
    ]


@pytest.fixture
def postes(db):
    from suivi.models import Poste

    return [
        Poste.objects.create(nom="PC-ETUDES-01", version_agent="0.2.0"),
        Poste.objects.create(nom="PC-ETUDES-02"),
    ]


@pytest.fixture
def dossiers(racines):
    from suivi.models import Dossier

    return [
        Dossier.objects.create(
            code="GIC-HYD-ETU-052",
            nom="Bargondaga",
            chemin_windows=PROJET_052,
            racine=racines[0],
            valide=True,
        ),
        Dossier.objects.create(
            code="2026-SOMAPEP-001",
            nom="Recharge de nappe",
            chemin_windows=AVIS_SOMAPEP,
            racine=racines[1],
        ),
    ]


@pytest.fixture
def faire_lot():
    """faire_lot(3) → {lot_id, poste, version_agent, segments: [...]}.

    Par défaut : 3 segments de 10 min dans le dossier 052.
    """

    def fabrique(
        n: int,
        *,
        debut: datetime = datetime(2026, 10, 7, 8, 0),
        duree_s: int = 600,
        application: str = "WINWORD.EXE",
        chemin: str | None = PROJET_052 + r"\Rapports\rapport.docx",
        poste: str = "PC-ETUDES-01",
        utilisateur: str = "a.traore",  # ce que l'agent lit dans %USERNAME% (sans domaine)
        etat: str = "ACTIF",
    ) -> dict:
        segments = []
        for i in range(n):
            d = debut + timedelta(seconds=i * duree_s)
            segments.append(
                {
                    "debut": d.isoformat(),
                    "fin": (d + timedelta(seconds=duree_s)).isoformat(),
                    "duree_s": duree_s,
                    "etat": etat,
                    "application": application,
                    "fichier": chemin.rsplit("\\", 1)[-1] if chemin else None,
                    "chemin": chemin,
                }
            )
        return {
            "lot_id": str(uuid.uuid4()),
            "poste": poste,
            "utilisateur": utilisateur,
            "version_agent": "0.2.0",
            "segments": segments,
        }

    return fabrique
