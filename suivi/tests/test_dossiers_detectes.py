import json

import pytest
from django.test import override_settings

from suivi.models import Dossier, Segment
from suivi.tableau_de_bord import contexte

pytestmark = pytest.mark.django_db

URL = "/api/segments"
IIS = {"IDENTITE_SOURCE": "iis", "IDENTITE_LECTEUR_GROUPES": None}
AWA = {"REMOTE_USER": "GICONSEILS\\a.traore"}
KAYES = r"\\AD-SERVEUR\GIC\MISSIONS_EN_COURS\GIC-AEP-CTR-003_Kayes"


def poster(client, lot):
    return client.post(
        URL,
        data=json.dumps(lot),
        content_type="application/json",
        HTTP_USER_AGENT="GiSuivi-Agent/0.2.0",
        **AWA,
    )


@override_settings(**IIS)
def test_dossier_conforme_inconnu_cree_detecte_et_segment_rattache(client, racines, faire_lot):
    assert poster(client, faire_lot(2, chemin=KAYES + r"\Plans\reseau.dwg")).status_code == 200
    d = Dossier.objects.get()
    assert d.statut == "detecte" and not d.valide
    assert d.code == "GIC-AEP-CTR-003" and d.nom == "gic-aep-ctr-003_kayes"
    assert d.racine == racines[0]
    assert d.chemin_windows == r"\\ad-serveur\gic\missions_en_cours\gic-aep-ctr-003_kayes"
    assert all(s.dossier == d and s.statut_classement == "dossier" for s in Segment.objects.all())


@override_settings(**IIS)
def test_deuxieme_lot_meme_dossier_pas_de_doublon(client, racines, faire_lot):
    poster(client, faire_lot(1, chemin=KAYES + r"\a.docx"))
    poster(client, faire_lot(1, chemin=r"H:\MISSIONS_EN_COURS\GIC-AEP-CTR-003_Kayes\b.xlsx"))
    assert Dossier.objects.count() == 1
    assert Segment.objects.filter(dossier__isnull=False).count() == 2


@override_settings(**IIS)
def test_dossier_sans_code_detecte_quand_meme(client, racines, faire_lot):
    chemin = r"\\AD-SERVEUR\GIC\MISSIONS_EN_COURS\A-CODER_usine\rapport.docx"
    poster(client, faire_lot(1, chemin=chemin))
    d = Dossier.objects.get()
    assert d.code == "" and d.nom == "a-coder_usine" and d.statut == "detecte"


@override_settings(**IIS)
def test_hors_racine_ne_cree_rien(client, racines, faire_lot):
    poster(client, faire_lot(1, chemin=r"C:\Users\awa\Desktop\notes.pdf"))
    poster(client, faire_lot(1, chemin=r"\\AD-SERVEUR\GIC\MISSIONS_EN_COURS\liste.xlsx"))
    assert Dossier.objects.count() == 0
    assert Segment.objects.filter(statut_classement="a_classer").count() == 2


@override_settings(**IIS)
def test_dossier_deja_valide_reste_tel_quel(client, dossiers, faire_lot):
    poster(client, faire_lot(1))
    d = Dossier.objects.get(code="GIC-HYD-ETU-052")
    assert d.valide and d.nom == "Bargondaga" and Dossier.objects.count() == 2


@override_settings(**IIS)
def test_racine_inactive_ignoree(client, racines, faire_lot):
    racines[0].active = False
    racines[0].save()
    poster(client, faire_lot(1, chemin=KAYES + r"\a.docx"))
    assert Dossier.objects.count() == 0


@override_settings(**IIS)
def test_tableau_de_bord_compte_les_dossiers_a_valider(client, racines, faire_lot, rf):
    poster(client, faire_lot(1, chemin=KAYES + r"\a.docx"))
    assert contexte(rf.get("/admin/"), {})["dossiers_a_valider"] == 1
