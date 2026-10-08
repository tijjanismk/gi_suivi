import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.test import override_settings

from conftest import PROJET_052
from suivi.models import DemandeRecalcul, Dossier, Racine, RegleException, Segment
from suivi.services import recalculer, valider_dossier

pytestmark = pytest.mark.django_db

URL = "/api/segments"
IIS = {"IDENTITE_SOURCE": "iis", "IDENTITE_LECTEUR_GROUPES": None}
AWA = {"REMOTE_USER": "GICONSEILS\\a.traore"}
BUREAU = r"C:\Users\awa\Desktop\TDR_Bargondaga.pdf"


def poster(client, lot):
    return client.post(URL, data=json.dumps(lot), content_type="application/json", **AWA)


def en_attente() -> int:
    return DemandeRecalcul.objects.filter(traitee_le=None).count()


@override_settings(**IIS)
def test_exception_puis_recalcul_rattache_sans_toucher_au_brut(client, dossiers, faire_lot):
    poster(client, faire_lot(1, chemin=BUREAU, application="Acrobat.exe"))
    seg = Segment.objects.get()
    assert seg.statut_classement == "a_classer" and seg.dossier is None
    brut = (seg.debut, seg.fin, seg.duree_s, seg.fichier, seg.chemin, seg.application)

    DemandeRecalcul.objects.all().delete()
    RegleException.objects.create(motif=BUREAU, type="chemin", dossier=dossiers[0])
    assert en_attente() == 1  # signal

    r = recalculer()
    assert r == {"examines": 1, "modifies": 1, "demandes": 1}
    seg.refresh_from_db()
    assert seg.statut_classement == "dossier" and seg.dossier == dossiers[0]
    assert (seg.debut, seg.fin, seg.duree_s, seg.fichier, seg.chemin, seg.application) == brut
    assert en_attente() == 0


@override_settings(**IIS)
def test_exception_supprimee_le_segment_redevient_a_classer(client, dossiers, faire_lot):
    poster(client, faire_lot(1, chemin=BUREAU))
    e = RegleException.objects.create(motif=BUREAU, type="chemin", dossier=dossiers[0])
    recalculer()
    assert Segment.objects.get().statut_classement == "dossier"
    e.delete()
    assert en_attente() == 1
    recalculer()
    assert Segment.objects.get().statut_classement == "a_classer"


@override_settings(**IIS)
def test_racine_ajoutee_apres_coup_rattache_les_anciens_segments(client, faire_lot):
    # aucune racine : le fichier de projet reste à classer
    poster(client, faire_lot(1))
    assert Segment.objects.get().statut_classement == "a_classer" and Dossier.objects.count() == 0
    Racine.objects.create(chemin=r"\\AD-SERVEUR\GIC\MISSIONS_EN_COURS", profondeur=1)
    r = recalculer()
    assert r["modifies"] == 1
    d = Dossier.objects.get()
    assert d.statut == "detecte" and d.code == "GIC-HYD-ETU-052"
    assert Segment.objects.get().dossier == d


@override_settings(**IIS)
def test_brouillons_applications_et_ignores_jamais_reclasses(client, racines, faire_lot):
    brouillon = faire_lot(1, chemin=None)
    brouillon["segments"][0]["fichier"] = "Document1"
    poster(client, brouillon)
    poster(client, faire_lot(1, chemin=None, application="explorer.exe"))
    poster(client, faire_lot(1, chemin=PROJET_052 + r"\~$rapport.docx"))
    avant = sorted(Segment.objects.values_list("statut_classement", flat=True))
    assert avant == ["application", "brouillon", "ignore"]
    assert recalculer()["examines"] == 0
    assert sorted(Segment.objects.values_list("statut_classement", flat=True)) == avant


def test_valider_dossier(dossiers, django_user_model):
    u = django_user_model.objects.create(login_windows="giconseils\\directrice")
    d = dossiers[1]
    assert d.statut == "detecte" and not d.valide
    DemandeRecalcul.objects.all().delete()
    valider_dossier(d, u, nom="Recharge de nappe — SOMAPEP", client="SOMAPEP")
    d.refresh_from_db()
    assert d.valide and d.valide_par == u and d.valide_le is not None
    assert d.statut == "actif" and d.nom == "Recharge de nappe — SOMAPEP" and d.client == "SOMAPEP"
    assert en_attente() == 1 and "validé" in DemandeRecalcul.objects.get().motif


@override_settings(**IIS)
def test_commande_ne_fait_rien_sans_demande_puis_traite(client, dossiers, faire_lot):
    poster(client, faire_lot(1, chemin=BUREAU))
    DemandeRecalcul.objects.all().delete()
    sortie = StringIO()
    call_command("suivi_recalculer", stdout=sortie)
    assert "Rien à recalculer" in sortie.getvalue()

    RegleException.objects.create(
        motif=r"C:\Users\awa\Desktop", type="prefixe", dossier=dossiers[0]
    )
    sortie = StringIO()
    call_command("suivi_recalculer", stdout=sortie)
    assert "1 modifiés" in sortie.getvalue() and en_attente() == 0
    assert Segment.objects.get().dossier == dossiers[0]

    sortie = StringIO()
    call_command("suivi_recalculer", "--force", stdout=sortie)
    assert "0 modifiés" in sortie.getvalue()


@override_settings(**IIS)
def test_action_admin_valider_et_exception_a_effet_immediat(client, dossiers, faire_lot):
    directrice = {"REMOTE_USER": "GICONSEILS\\directrice"}
    with override_settings(IDENTITE_LECTEUR_GROUPES="suivi.tests.test_recalcul.groupes"):
        poster(client, faire_lot(1, chemin=BUREAU))
        detecte = dossiers[1]
        r = client.post(
            "/admin/suivi/dossier/",
            {"action": "valider", "_selected_action": [detecte.pk]},
            follow=True,
            **directrice,
        )
        assert r.status_code == 200
        detecte.refresh_from_db()
        assert detecte.valide and detecte.statut == "actif"

        r = client.post(
            "/admin/suivi/regleexception/add/",
            {"motif": BUREAU, "type": "chemin", "dossier": dossiers[0].pk},
            follow=True,
            **directrice,
        )
        assert r.status_code == 200
        assert Segment.objects.get().dossier == dossiers[0]  # reclassé sans attendre la tâche
        assert RegleException.objects.get().cree_par.login_windows == "giconseils\\directrice"


def groupes(login: str) -> list[str]:
    return ["GI-Direction"]
