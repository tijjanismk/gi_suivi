import json
from datetime import datetime, timedelta

import pytest
from django.test import override_settings
from django.utils import timezone

from suivi.models import Segment
from suivi.services import activite_du_jour, employe_de

pytestmark = pytest.mark.django_db

IIS = {"IDENTITE_SOURCE": "iis", "IDENTITE_LECTEUR_GROUPES": None}
AWA = {"REMOTE_USER": "GICONSEILS\\a.traore"}
MOUSSA = {"REMOTE_USER": "GICONSEILS\\m.keita"}


def poster(client, lot, **meta):
    return client.post(
        "/api/segments",
        data=json.dumps(lot),
        content_type="application/json",
        HTTP_USER_AGENT="GiSuivi-Agent/0.2.0",
        **meta,
    )


def aujourd_hui(h: int, m: int = 0) -> datetime:
    return datetime.combine(timezone.localdate(), datetime.min.time()).replace(hour=h, minute=m)


@override_settings(**IIS)
def test_chacun_ne_voit_que_ses_segments(client, dossiers, faire_lot):
    poster(client, faire_lot(2, debut=aujourd_hui(8)), **AWA)  # 2 × 10 min, dossier 052
    poster(client, faire_lot(5, debut=aujourd_hui(9), utilisateur="m.keita"), **MOUSSA)
    r = client.get("/api/moi/aujourdhui", **AWA)
    assert r.status_code == 200
    d = r.json()
    assert d["employe"] == "a.traore" and d["total_s"] == 1200 and d["total_hm"] == "0 h 20"
    assert d["arrivee"] == "08:00" and d["depart"] == "08:20" and d["amplitude_s"] == 1200
    assert d["occupation_pct"] == "100.0"
    assert d["par_dossier"] == [{"code": "GIC-HYD-ETU-052", "nom": "Bargondaga", "duree_s": 1200}]
    assert d["par_application"] == [{"application": "WINWORD.EXE", "duree_s": 1200}]
    assert client.get("/api/moi/aujourdhui", **MOUSSA).json()["total_s"] == 3000


@override_settings(**IIS)
def test_a_classer_sans_fichier_et_inactif(client, racines, faire_lot):
    poster(client, faire_lot(1, debut=aujourd_hui(8), chemin=r"C:\Users\awa\Desktop\x.pdf"), **AWA)
    poster(
        client, faire_lot(1, debut=aujourd_hui(8, 10), chemin=None, application="chrome.exe"), **AWA
    )
    poster(client, faire_lot(1, debut=aujourd_hui(8, 20), etat="INACTIF"), **AWA)
    d = client.get("/api/moi/aujourdhui", **AWA).json()
    assert d["total_s"] == 1200 and d["a_classer_s"] == 600 and d["sans_fichier_s"] == 600
    assert d["par_dossier"] == [] and d["depart"] == "08:20"  # l'inactif ne compte pas


@override_settings(**IIS)
def test_hier_n_apparait_pas(client, dossiers, faire_lot):
    poster(client, faire_lot(3, debut=aujourd_hui(8) - timedelta(days=1)), **AWA)
    assert client.get("/api/moi/aujourdhui", **AWA).json()["total_s"] == 0


@override_settings(**IIS)
def test_personne_sans_agent_journee_vide(client):
    d = client.get("/api/moi/aujourdhui", REMOTE_USER="GICONSEILS\\nouveau").json()
    assert d["employe"] is None and d["total_s"] == 0 and d["par_dossier"] == []
    assert client.get("/api/moi/aujourdhui").status_code == 401


@override_settings(**IIS)
def test_racines_telles_que_saisies(client, racines):
    d = client.get("/api/racines", **AWA).json()
    assert [r["chemin"] for r in d["racines"]] == [
        r"\\AD-SERVEUR\GIC\AVIS",
        r"\\AD-SERVEUR\GIC\MISSIONS_EN_COURS",
    ]
    assert d["racines"][0]["profondeur"] == 3 and "GIC-" in d["racines"][0]["motif_code"]
    assert d["correspondance_lecteurs"] == {"H:": r"\\AD-SERVEUR\GIC"}
    assert d["seuil_inactivite_s"] == 300 and d["intervalle_s"] == 5
    racines[1].active = False
    racines[1].save()
    assert len(client.get("/api/racines", **AWA).json()["racines"]) == 1
    assert client.post("/api/racines", **AWA).status_code == 405


@override_settings(**IIS)
def test_page_mon_activite(client, dossiers, faire_lot):
    poster(client, faire_lot(1, debut=aujourd_hui(14)), **AWA)
    r = client.get("/moi", **AWA)
    assert r.status_code == 200
    html = r.content.decode()
    assert "Mon activité du jour" in html and "GIC-HYD-ETU-052" in html and "14:00" in html
    assert "vous seul voyez cette page" in html
    # une autre personne, sans agent : page vide mais accessible
    assert (
        "Rien de mesuré" in client.get("/moi", REMOTE_USER="GICONSEILS\\nouveau").content.decode()
    )


def test_activite_du_jour_sans_employe():
    assert activite_du_jour(None)["total_s"] == 0


@override_settings(**IIS)
def test_employe_de_par_lien_puis_par_login(client, dossiers, faire_lot, django_user_model):
    poster(client, faire_lot(1), **AWA)
    u = django_user_model.objects.get(login_windows="giconseils\\a.traore")
    e = employe_de(u)
    assert e is not None and e.utilisateur == u
    e.utilisateur = None
    e.save()
    assert employe_de(u) == e  # retrouvé par le login
    assert Segment.objects.filter(employe=e).count() == 1
