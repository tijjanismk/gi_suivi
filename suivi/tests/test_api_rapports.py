import pytest
from django.test import override_settings

from suivi.models import Segment
from suivi.rapports import etat_postes

pytestmark = pytest.mark.django_db

IIS = {
    "IDENTITE_SOURCE": "iis",
    "IDENTITE_LECTEUR_GROUPES": "suivi.tests.test_api_rapports.groupes",
}
DIR = {"REMOTE_USER": "GICONSEILS\\directrice"}
VUE = {"REMOTE_USER": "GICONSEILS\\visionneuse"}
AWA = {"REMOTE_USER": "GICONSEILS\\a.traore"}
PERIODE = "?debut=2026-10-05&fin=2026-10-07"


def groupes(login: str) -> list[str]:
    return {
        "giconseils\\directrice": ["GI-Direction"],
        "giconseils\\visionneuse": ["GI-Direction-Lecture"],
    }.get(login, [])


@override_settings(**IIS)
def test_reserve_a_la_direction_et_a_la_consultation(client, jeu_de_segments):
    for url in (
        "/api/rapports/synthese",
        "/api/rapports/dossiers",
        "/api/dossiers",
        "/api/aclasser",
        "/api/postes/etat",
    ):
        assert client.get(url, **AWA).status_code == 403, url
        assert client.get(url, **VUE).status_code == 200, url
        assert client.get(url, **DIR).status_code == 200, url
    assert client.get("/api/rapports/synthese").status_code == 401


@override_settings(**IIS)
def test_synthese(client, jeu_de_segments, employes):
    d = client.get("/api/rapports/synthese" + PERIODE, **DIR).json()
    assert d["periode"] == {"debut": "2026-10-05", "fin": "2026-10-07", "jours": 3}
    assert d["effectif_s"] == 30 * 3600 and d["prevu_s"] == 2 * 3 * 8 * 3600
    assert d["prevu_pct"] == "62.5" and d["employes_actifs"] == 2 and d["a_classer_s"] == 3600
    awa, moussa = d["employes"]
    assert (
        awa["employe"] == "Awa Traoré"
        and awa["effectif_s"] == 18 * 3600
        and awa["prevu_pct"] == "75.0"
    )
    assert awa["jours_travailles"] == 3 and len(awa["journees"]) == 3
    lundi = awa["journees"][0]
    assert (
        lundi["arrivee"] == "08:00"
        and lundi["depart"] == "17:00"
        and lundi["amplitude_s"] == 9 * 3600
    )
    assert lundi["effectif_s"] == 7 * 3600 and lundi["occupation_pct"] == "77.8"
    assert moussa["effectif_s"] == 12 * 3600 and moussa["prevu_pct"] == "50.0"
    assert moussa["journees"][2]["effectif_s"] == 0 and moussa["journees"][2]["arrivee"] is None


@override_settings(**IIS)
def test_synthese_periode_par_defaut_et_invalide(client, jeu_de_segments):
    d = client.get("/api/rapports/synthese", **DIR).json()
    assert d["periode"]["jours"] == 7
    assert (
        client.get("/api/rapports/synthese?debut=2026-10-07&fin=2026-10-05", **DIR).status_code
        == 400
    )
    assert client.get("/api/rapports/synthese?debut=hier", **DIR).status_code == 400
    assert (
        client.get("/api/rapports/synthese?debut=2020-01-01&fin=2026-10-07", **DIR).status_code
        == 400
    )


@override_settings(**IIS)
def test_dossiers(client, jeu_de_segments):
    d = client.get("/api/rapports/dossiers" + PERIODE, **DIR).json()
    d052, dsom = d["dossiers"]
    assert d052["code"] == "GIC-HYD-ETU-052" and d052["duree_s"] == 21 * 3600
    assert {e["employe"]: e["duree_s"] for e in d052["par_employe"]} == {
        "Awa Traoré": 13 * 3600,
        "Moussa Keïta": 8 * 3600,
    }
    assert (
        dsom["code"] == "2026-SOMAPEP-001"
        and dsom["duree_s"] == 7 * 3600
        and dsom["statut"] == "detecte"
    )
    assert d["a_classer_s"] == 3600 and d["brouillon_s"] == 1800 and d["sans_fichier_s"] == 1800


@override_settings(**IIS)
def test_liste_dossiers(client, jeu_de_segments, dossiers):
    d = client.get("/api/dossiers" + PERIODE, **DIR).json()["dossiers"]
    par_code = {x["code"]: x for x in d}
    assert (
        par_code["GIC-HYD-ETU-052"]["valide"]
        and par_code["GIC-HYD-ETU-052"]["duree_s"] == 21 * 3600
    )
    assert par_code["2026-SOMAPEP-001"]["statut"] == "detecte"
    assert par_code["GIC-HYD-ETU-052"]["derniere_activite"].startswith("2026-10-07T16:30")
    assert par_code["GIC-HYD-ETU-052"]["racine"] == dossiers[0].racine.chemin


@override_settings(**IIS)
def test_activite_employe(client, jeu_de_segments, employes):
    awa = employes[0]
    d = client.get(f"/api/employes/{awa.pk}/activite{PERIODE}&jour=2026-10-06", **DIR).json()
    assert d["employe"]["nom"] == "Awa Traoré" and len(d["journees"]) == 3
    assert d["jour"] == "2026-10-06" and len(d["chronologie"]) == 6  # 2 + 1 + 1 + 2
    premier = d["chronologie"][0]
    assert (
        premier["debut"] == "09:00"
        and premier["statut"] == "a_classer"
        and premier["dossier"] is None
    )
    assert d["chronologie"][-1]["dossier"] == "GIC-HYD-ETU-052"
    fichiers = {f["fichier"]: f for f in d["fichiers"]}
    assert (
        fichiers["rapport.docx"]["duree_s"] == 13 * 3600
        and fichiers["rapport.docx"]["dossier"] == "GIC-HYD-ETU-052"
    )
    assert (
        fichiers["notes.pdf"]["statut"] == "a_classer"
        and fichiers["Document1"]["statut"] == "brouillon"
    )
    # jour par défaut : la fin de la période
    assert (
        client.get(f"/api/employes/{awa.pk}/activite{PERIODE}", **DIR).json()["jour"]
        == "2026-10-07"
    )
    assert client.get("/api/employes/9999/activite", **DIR).status_code == 404
    assert client.get(f"/api/employes/{awa.pk}/activite?jour=x", **DIR).status_code == 400


@override_settings(**IIS)
def test_a_classer(client, jeu_de_segments):
    d = client.get("/api/aclasser" + PERIODE, **DIR).json()
    (g,) = d["groupes"]
    assert g["fichier"] == "notes.pdf" and g["employe"] == "Awa Traoré"
    assert (
        g["duree_s"] == 3600 and g["segments"] == 2 and g["dernier"].startswith("2026-10-06T10:00")
    )
    assert d["brouillons"] == {"duree_s": 1800, "segments": 1}


@override_settings(**IIS)
def test_etat_postes(client, jeu_de_segments):
    d = {p["nom"]: p for p in client.get("/api/postes/etat", **DIR).json()["postes"]}
    assert d["PC-ETUDES-01"]["alerte"] is None and d["PC-ETUDES-01"]["muet_depuis_h_ouvrees"] < 1
    assert (
        d["PC-ETUDES-02"]["alerte"] == "rouge" and d["PC-ETUDES-02"]["muet_depuis_h_ouvrees"] > 24
    )
    assert d["PC-ETUDES-02"]["demarrages_semaine"] == 14


def test_poste_jamais_vu_est_rouge_et_orange_sur_demarrages(postes):
    from datetime import timedelta

    from django.utils import timezone

    pc1, pc2 = postes
    pc1.dernier_envoi = timezone.now() - timedelta(hours=2)
    pc1.demarrages_semaine = 11
    pc1.save()
    etats = {p["nom"]: p for p in etat_postes()}
    assert (
        etats["PC-ETUDES-02"]["alerte"] == "rouge"
        and etats["PC-ETUDES-02"]["dernier_envoi"] is None
    )
    assert etats["PC-ETUDES-01"]["alerte"] == "orange"


def test_week_end_ne_compte_pas_dans_les_heures_ouvrees():
    from datetime import datetime

    from django.utils import timezone

    from suivi.rapports import _heures_ouvrees_depuis

    tz = timezone.get_current_timezone()
    vendredi_17h = datetime(2026, 10, 9, 17, 0, tzinfo=tz)
    lundi_9h = datetime(2026, 10, 12, 9, 0, tzinfo=tz)
    assert (
        _heures_ouvrees_depuis(vendredi_17h, lundi_9h) == 7 + 9
    )  # fin du vendredi + début du lundi


def test_jeu_de_segments_coherent(jeu_de_segments):
    assert len(jeu_de_segments) == 64 and Segment.objects.count() == 64
    assert Segment.objects.filter(etat="ACTIF").count() == 60
