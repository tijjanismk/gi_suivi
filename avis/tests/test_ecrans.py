"""AV03 (ADR 0013) — liste, fiche, saisie d'un avis et de son barème, aperçu, pièces, fichiers."""

from __future__ import annotations

from datetime import date
from html import unescape

import pytest
from django.test import override_settings
from freezegun import freeze_time

from administratif.demo import pdf
from administratif.models import TypePiece
from administratif.tests.conftest import AWA, DIR, IIS, VUE
from avis.formulaires import relatif_au_partage
from avis.models import Avis, Critere, PieceExigee
from references.models import Mission, PieceJustificative
from referentiel.models import Domaine
from suivi.models import JournalAcces

pytestmark = pytest.mark.django_db
CRITERE = {
    "code": "2",
    "ordre": "1",
    "libelle": "Contrôleur principal, dix dernières années, 2 points par référence",
    "mode": "par_mission",
    "points_par_mission": "2",
    "plafond": "25",
    "nb_min_missions": "0",
    "annees_seuil": "0",
    "points_socle": "0",
    "points_par_annee": "0",
    "natures": ["CTR", "ETC"],
    "domaines": ["AEP"],
    "roles": ["seul", "chef_de_file"],
    "annee_min": "2016",
    "mots_cles": "hydraulique, forage",
    "pieces": "pv_bonne_fin",
}


def html(r) -> str:
    return unescape(r.content.decode())


@pytest.fixture(autouse=True)
def le_27_octobre():
    with freeze_time("2026-10-27 10:00"), override_settings(**IIS):
        yield


@pytest.fixture
def unicef():
    return Avis.objects.create(
        reference="LRPS-MLI-2026-9206428",
        objet="Suivi et contrôle des forages équipés d'AES, des latrines et du génie civil",
        type=Avis.Type.DP,
        date_limite=date(2026, 10, 28),
    )


@pytest.fixture
def references():
    aep = Domaine.objects.get(code="AEP")
    m = Mission.objects.create(
        code="GIC-AEP-CTR-015",
        domaine=aep,
        nature="CTR",
        annee=2019,
        intitule="Contrôle des travaux d'hydraulique dans les écoles de Koulikoro et de Menaka",
    )
    PieceJustificative.objects.create(
        mission=m,
        type="attestation",
        nature_exacte="pv_reception",
        chemin="REFERENCES\\02_JUSTIFICATIFS\\GIC-AEP-CTR-015\\ATTESTATION.pdf",
        empreinte="1" * 64,
    )
    Mission.objects.create(
        code="GIC-AEP-ETU-001", domaine=aep, nature="ETU", annee=2020, intitule="Eau à Kayes"
    )
    return m


def test_chemin_ramene_au_partage():
    assert relatif_au_partage(r"\\AD-SERVEUR\GIC\AVIS\MALI\avis.pdf") == r"AVIS\MALI\avis.pdf"
    assert relatif_au_partage(r'"D:\GIC\AVIS\avis.pdf"') == r"AVIS\avis.pdf"
    assert relatif_au_partage("AVIS/MALI/avis.pdf") == r"AVIS\MALI\avis.pdf"


def test_liste_et_droits(client, unicef):
    page = html(client.get("/avis/", **DIR))
    assert "LRPS-MLI-2026-9206428" in page and "demain" in page and "Nouvel avis" in page
    lecture = html(client.get("/avis/", **VUE))
    assert "LRPS-MLI-2026-9206428" in lecture and "Nouvel avis" not in lecture
    assert client.get("/avis/", **AWA).status_code == 403
    assert client.get("/avis/nouveau", **VUE).status_code == 403
    assert "Aucun avis ne correspond" in html(client.get("/avis/?echeance=passes", **DIR))
    assert JournalAcces.objects.filter(action="consulter:avis").exists()


def test_creer_un_avis(client):
    donnees = {
        "reference": "09/2026/001/MI/SOMAPEP/DG",
        "objet": "Études d'ouvrages de recharge de la nappe",
        "type": "AMI",
        "statut": "recu",
        "pays": "Mali",
        "date_publication": "2026-10-01",
        "date_limite": "2026-10-30",
        "fichier_avis_chemin": r"\\AD-SERVEUR\GIC\AVIS\MALI\2026-10\SOMAPEP\AMI-SOMAPEP-SA.pdf",
    }
    r = client.post("/avis/nouveau", donnees, **DIR)
    a = Avis.objects.get(reference="09/2026/001/MI/SOMAPEP/DG")
    assert r.status_code == 302 and r.url == f"/avis/{a.pk}/"
    assert a.fichier_avis_chemin == r"AVIS\MALI\2026-10\SOMAPEP\AMI-SOMAPEP-SA.pdf"
    assert a.cree_par.login_windows == "giconseils\\directrice"
    par_defaut = TypePiece.objects.filter(exigee_par_defaut=True, actif=True).count()
    assert a.pieces_exigees.count() == par_defaut
    assert JournalAcces.objects.filter(action="avis:creer").exists()
    faux = {**donnees, "fichier_avis_chemin": r"C:\Users\moi\avis.pdf", "date_limite": "2026-09-30"}
    page = html(client.post("/avis/nouveau", faux, **DIR))
    assert "Un chemin du partage GIC" in page and "La date limite précède la publication" in page


def test_critere_apercu_puis_enregistrement(client, unicef, references):
    url = f"/avis/{unicef.pk}/critere"
    page = html(client.post(url, {**CRITERE, "action": "apercu"}, **DIR))
    assert "1 référence retenue" in page and "GIC-AEP-CTR-015" in page
    assert "0 prouvées, 1 à auditer, 0 sans pièce" in page and not Critere.objects.exists()

    r = client.post(url, {**CRITERE, "action": "enregistrer"}, **DIR)
    assert r.status_code == 302
    c = unicef.criteres.get()
    assert c.filtre == {
        "natures": ["CTR", "ETC"],
        "domaines": ["AEP"],
        "roles": ["seul", "chef_de_file"],
        "annee_min": 2016,
        "mots_cles": ["hydraulique", "forage"],
        "pieces_requises": ["bonne_fin|pv_reception"],
    }
    fiche = html(client.get(f"/avis/{unicef.pk}/", **DIR))
    assert "depuis 2016" in fiche and "mots-clés : hydraulique, forage" in fiche
    assert "1 à auditer" in fiche

    modifier = html(client.get(f"{url}/{c.pk}", **DIR))
    assert '<option value="pv_bonne_fin" selected>' in modifier

    doublon = html(client.post(url, {**CRITERE, "action": "enregistrer"}, **DIR))
    assert "Le critère 2 existe déjà dans cet avis." in doublon
    inverse = {**CRITERE, "code": "3", "annee_min": "2025", "annee_max": "2010"}
    assert "« annee_min » est après « annee_max »" in html(client.post(url, inverse, **DIR))
    assert unicef.criteres.count() == 1

    assert client.post(f"{url}/{c.pk}/retirer", **DIR).status_code == 302
    assert not unicef.criteres.exists()


def test_pieces_exigees(client, unicef):
    codes = list(unicef.pieces_exigees.values_list("type__code", flat=True))
    voulues = [c for c in codes if c != "NIF"] + ["NON-FAILLITE"]
    r = client.post(f"/avis/{unicef.pk}/pieces", {"pieces": voulues}, follow=True, **DIR)
    assert "1 ajoutée(s), 1 retirée(s)" in html(r)
    assert not unicef.pieces_exigees.filter(type__code="NIF").exists()
    ajoutee = unicef.pieces_exigees.get(type__code="NON-FAILLITE")
    assert ajoutee.origine == PieceExigee.Origine.AVIS
    assert client.post(f"/avis/{unicef.pk}/pieces", {"pieces": []}, **VUE).status_code == 403


def test_fichier_de_l_avis(client, unicef, settings, tmp_path):
    settings.PARTAGE_GIC = str(tmp_path)
    (tmp_path / "AVIS").mkdir()
    (tmp_path / "AVIS" / "rfp.pdf").write_bytes(pdf("RFP UNICEF"))
    unicef.fichier_avis_chemin = "AVIS\\rfp.pdf"
    unicef.fichier_tdr_chemin = "AVIS\\tdr.pdf"
    unicef.save()
    fiche = html(client.get(f"/avis/{unicef.pk}/", **DIR))
    assert "ouvrir" in fiche and "introuvable sur le partage" in fiche
    r = client.get(f"/avis/{unicef.pk}/fichier/avis", **VUE)
    assert r.status_code == 200 and r["Content-Type"] == "application/pdf"
    assert client.get(f"/avis/{unicef.pk}/fichier/tdr", **DIR).status_code == 404
    assert client.get(f"/avis/{unicef.pk}/fichier/autre", **DIR).status_code == 404
