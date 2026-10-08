from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from django.test import override_settings
from django.utils import timezone

from suivi.models import JournalAcces, Segment
from suivi.rapports import blocs_journee, journee_personne

pytestmark = pytest.mark.django_db

IIS = {
    "IDENTITE_SOURCE": "iis",
    "IDENTITE_LECTEUR_GROUPES": "suivi.tests.test_vues_journee.groupes",
}
DIR = {"REMOTE_USER": "GICONSEILS\\directrice"}
VUE = {"REMOTE_USER": "GICONSEILS\\visionneuse"}
AWA = {"REMOTE_USER": "GICONSEILS\\a.traore"}


def groupes(login: str) -> list[str]:
    return {
        "giconseils\\directrice": ["GI-Direction"],
        "giconseils\\visionneuse": ["GI-Direction-Lecture"],
    }.get(login, [])


def test_blocs_fusionnent_pauses_et_trous(employes, postes, dossiers):
    tz = timezone.get_current_timezone()
    awa, pc = employes[0], postes[0]
    t = lambda h, m=0: datetime(2026, 10, 5, h, m, tzinfo=tz)  # noqa: E731

    def seg(debut, fin, **champs):
        base = {
            "etat": "ACTIF",
            "application": "WINWORD.EXE",
            "fichier": "a.docx",
            "chemin": "x",
            "statut_classement": "dossier",
            "dossier": dossiers[0],
        }
        base.update(champs)
        return Segment(
            employe=awa,
            poste=pc,
            debut=debut,
            fin=fin,
            duree_s=int((fin - debut).total_seconds()),
            lot_id=uuid4(),
            **base,
        )

    segments = [
        seg(t(8), t(8, 30)),
        seg(t(8, 30), t(9), fichier="b.docx"),  # même dossier : fusionné
        seg(
            t(9),
            t(9, 10),
            etat="INACTIF",
            application="session",
            statut_classement="application",
            dossier=None,
            fichier="",
            chemin="",
        ),
        seg(
            t(9, 10),
            t(9, 20),
            etat="INACTIF",
            application="session",
            statut_classement="application",
            dossier=None,
            fichier="",
            chemin="",
        ),
        seg(t(9, 20), t(10), dossier=dossiers[1]),
        # 12:00 → 13:30 : rien du tout (poste verrouillé) → hors mesure
        seg(
            t(13, 30),
            t(14),
            application="chrome.exe",
            statut_classement="application",
            dossier=None,
            fichier="",
            chemin="",
        ),
    ]
    blocs = blocs_journee(segments)
    assert [(b["type"], b["debut"].hour, b["debut"].minute, b["duree_s"]) for b in blocs] == [
        ("dossier", 8, 0, 3600),
        ("pause", 9, 0, 1200),
        ("dossier", 9, 20, 2400),
        ("hors_mesure", 10, 0, 3 * 3600 + 1800),
        ("sans_fichier", 13, 30, 1800),
    ]
    assert blocs[0]["fichiers"] == ["a.docx", "b.docx"] and blocs[0]["libelle"] == "GIC-HYD-ETU-052"
    assert blocs[1]["libelle"] == "Pause (aucune action)"
    assert (
        blocs[2]["libelle"] == "2026-SOMAPEP-001"
        and blocs[4]["libelle"] == "Sans fichier — chrome.exe"
    )


def test_journee_personne_totaux(jeu_de_segments, employes):
    from datetime import date

    j = journee_personne(employes[0], date(2026, 10, 5))
    assert j["arrivee"].strftime("%H:%M") == "08:00" and j["depart"].strftime("%H:%M") == "17:00"
    assert j["actif_s"] == 7 * 3600 and j["pause_s"] == 2 * 3600 and j["nb_pauses"] == 1
    assert j["hors_mesure_s"] == 0 and j["amplitude_s"] == 9 * 3600
    assert j["dossiers"] == ["2026-SOMAPEP-001", "GIC-HYD-ETU-052"]
    vide = journee_personne(employes[1], date(2026, 10, 7))
    assert vide["arrivee"] is None and vide["blocs"] == [] and vide["actif_s"] == 0


@override_settings(**IIS)
def test_ecran_journee(client, jeu_de_segments, employes):
    assert client.get("/suivi/journee/?jour=2026-10-05", **AWA).status_code == 403
    r = client.get("/suivi/journee/?jour=2026-10-05", **VUE)
    assert r.status_code == 200
    html = r.content.decode()
    assert "lundi 5 octobre 2026" in html and "Awa Traoré" in html and "Moussa Keïta" in html
    assert "08:00 → 17:00" in html and "7 h 00" in html and "2 h 00" in html  # Awa : actif, pauses
    assert "08:00 → 16:00" in html and "8 h 00" in html  # Moussa
    assert "2 / 2" in html  # présents
    assert "Pause (aucune action)" in html and 'style="background: #2563eb"' in html
    assert f"/suivi/journee/{employes[0].pk}/?jour=2026-10-05" in html
    assert "?jour=2026-10-04" in html and "?jour=2026-10-06" in html  # veille et lendemain
    assert JournalAcces.objects.filter(action="consulter:journee", cible="2026-10-05").exists()


@override_settings(**IIS)
def test_detail_journee_personne(client, jeu_de_segments, employes):
    awa = employes[0]
    html = client.get(f"/suivi/journee/{awa.pk}/?jour=2026-10-06", **DIR).content.decode()
    assert "Bloc par bloc" in html and "09:00 → 10:00" in html and "À classer — notes.pdf" in html
    assert "Brouillon — Document1" in html and "Sans fichier — chrome.exe" in html
    assert "11:00 → 12:00" in html and "GIC-HYD-ETU-052" in html
    assert "Hors mesure" in html  # cartes
    assert client.get(f"/suivi/journee/{awa.pk}/?jour=2026-10-07", **VUE).status_code == 200
    assert client.get("/suivi/journee/9999/", **DIR).status_code == 404
    assert (
        "Rien de mesuré ce jour-là"
        in client.get(f"/suivi/journee/{employes[1].pk}/?jour=2026-10-07", **DIR).content.decode()
    )


@override_settings(**IIS)
def test_jour_par_defaut_et_invalide(client, employes):
    aujourd_hui = timezone.localdate()
    html = client.get("/suivi/journee/", **DIR).content.decode()
    assert aujourd_hui.strftime("%Y-%m-%d") in html
    assert client.get("/suivi/journee/?jour=hier", **DIR).status_code == 200
    r = client.get("/", **DIR)
    assert r.status_code == 302 and r["Location"] == "/suivi/journee/"
    # le futur n'a pas de bouton « jour suivant »
    assert "Jour suivant" not in html


@override_settings(**IIS)
def test_trou_hors_mesure_affiche(client, employes, postes, dossiers):
    tz = timezone.get_current_timezone()
    awa, pc = employes[0], postes[0]
    for h in (8, 14):
        d = datetime(2026, 10, 5, h, tzinfo=tz)
        Segment.objects.create(
            employe=awa,
            poste=pc,
            debut=d,
            fin=d + timedelta(hours=1),
            duree_s=3600,
            etat="ACTIF",
            application="WINWORD.EXE",
            fichier="a.docx",
            chemin="x",
            statut_classement="dossier",
            dossier=dossiers[0],
            lot_id=uuid4(),
        )
    html = client.get(f"/suivi/journee/{awa.pk}/?jour=2026-10-05", **DIR).content.decode()
    assert (
        "09:00 → 14:00" in html
        and "5 h 00" in html
        and "poste verrouillé, éteint ou en veille" in html
    )
