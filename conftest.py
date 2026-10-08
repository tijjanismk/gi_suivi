"""Fixtures partagées par les tests Django (docs/tests.md, section 2).

`faire_lot(n, ...)` fabrique un lot réaliste, au format que l'agent envoie à POST /api/segments.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pytest
from django.utils import timezone

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
def jeu_de_segments(employes, postes, dossiers):
    """Trois jours ouvrés (lundi 5 → mercredi 7 octobre 2026), deux personnes, 64 segments
    de 30 min.

    Awa : lun 8h-12h dossier 052 et 14h-17h SOMAPEP (12h-14h inactif) ; mar 9h-10h à classer
    (Bureau), 10h-10h30 brouillon, 10h30-11h chrome sans fichier, 11h-12h dossier 052 ;
    mer 8h30-16h30 dossier 052. Total actif 18 h (sur 24 h prévues → 75 %).
    Moussa : lun 8h-16h dossier 052 ; mar 8h-12h SOMAPEP. Total 12 h (50 %).
    Dossier 052 : 21 h ; SOMAPEP : 7 h ; à classer 1 h ; brouillon 30 min ; sans fichier 30 min.
    """
    from suivi.models import Segment

    awa, moussa = employes
    pc1, pc2 = postes
    d052, dsom = dossiers
    tz = timezone.get_current_timezone()

    def plage(jour, h_debut, h_fin, employe, poste, **champs):
        debut = datetime(2026, 10, jour, int(h_debut), int((h_debut % 1) * 60), tzinfo=tz)
        fin = datetime(2026, 10, jour, int(h_fin), int((h_fin % 1) * 60), tzinfo=tz)
        base = {
            "etat": "ACTIF",
            "application": "WINWORD.EXE",
            "fichier": "",
            "chemin": "",
            "statut_classement": "dossier",
            "dossier": None,
            "lot_id": uuid.uuid4(),
        }
        base.update(champs)
        res = []
        t = debut
        while t < fin:
            res.append(
                Segment(
                    employe=employe,
                    poste=poste,
                    debut=t,
                    fin=t + timedelta(minutes=30),
                    duree_s=1800,
                    **base,
                )
            )
            t += timedelta(minutes=30)
        return res

    rapport = {
        "fichier": "rapport.docx",
        "chemin": PROJET_052 + r"\Rapports\rapport.docx",
        "dossier": d052,
    }
    methodo = {
        "fichier": "methodo.docx",
        "chemin": AVIS_SOMAPEP + r"\OFFRE\methodo.docx",
        "dossier": dsom,
    }
    segments = (
        plage(5, 8, 12, awa, pc1, **rapport)
        + plage(
            5,
            12,
            14,
            awa,
            pc1,
            etat="INACTIF",
            application="session",
            statut_classement="application",
        )
        + plage(5, 14, 17, awa, pc1, **methodo)
        + plage(
            6,
            9,
            10,
            awa,
            pc1,
            fichier="notes.pdf",
            chemin=r"C:\Users\awa\Desktop\notes.pdf",
            application="Acrobat.exe",
            statut_classement="a_classer",
        )
        + plage(6, 10, 10.5, awa, pc1, fichier="Document1", statut_classement="brouillon")
        + plage(6, 10.5, 11, awa, pc1, application="chrome.exe", statut_classement="application")
        + plage(6, 11, 12, awa, pc1, **rapport)
        + plage(7, 8.5, 16.5, awa, pc1, **rapport)
        + plage(5, 8, 16, moussa, pc2, **rapport)
        + plage(6, 8, 12, moussa, pc2, **methodo)
    )
    Segment.objects.bulk_create(segments)
    pc1.dernier_envoi = timezone.now()
    pc1.save()
    pc2.dernier_envoi = timezone.now() - timedelta(days=3)
    pc2.demarrages_semaine = 14
    pc2.save()
    return segments


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
