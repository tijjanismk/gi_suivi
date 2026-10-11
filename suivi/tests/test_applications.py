import pytest
from django.test import override_settings

from suivi.applications import WINDOWS, nom_application, regrouper, table
from suivi.models import Parametre

pytestmark = pytest.mark.django_db


def test_noms_connus_et_inconnus():
    noms = table()
    assert nom_application("WINWORD.EXE", noms) == "Microsoft Word"
    assert nom_application("msedge.exe", noms) == "Microsoft Edge"
    assert nom_application("claude.exe", noms) == "Claude"
    assert nom_application("ShellExperienceHost.exe", noms) == WINDOWS
    assert nom_application("IDMan.exe", noms) == "Internet Download Manager"
    assert nom_application("Inconnu.exe", noms) == "Inconnu"  # inconnu : sans « .exe »
    assert nom_application("session", noms) == "Session Windows"
    assert nom_application("", noms) == ""


def test_regroupement_et_tri():
    lignes = [
        {"application": "SearchHost.exe", "duree_s": 60},
        {"application": "ShellHost.exe", "duree_s": 30},
        {"application": "WINWORD.EXE", "duree_s": 600},
    ]
    r = regrouper(lignes, table())
    assert [x["application"] for x in r] == ["Microsoft Word", WINDOWS]
    assert r[1]["duree_s"] == 90 and r[1]["executables"] == ["SearchHost.exe", "ShellHost.exe"]


def test_noms_completes_par_parametre():
    Parametre.objects.create(cle="noms_applications", valeur={"Covadis.exe": "Covadis"})
    assert nom_application("covadis.exe") == "Covadis"
    assert nom_application("winword.exe") == "Microsoft Word"  # le reste de la table demeure


@override_settings(IDENTITE_SOURCE="iis", IDENTITE_LECTEUR_GROUPES=None)
def test_page_moi_affiche_les_noms(client, faire_lot):
    import json

    from django.utils import timezone

    debut = timezone.localtime().replace(hour=8, minute=0, second=0, microsecond=0)
    for app in ("WINWORD.EXE", "SearchHost.exe", "ShellHost.exe"):
        client.post(
            "/api/segments",
            data=json.dumps(faire_lot(1, debut=debut.replace(tzinfo=None), application=app)),
            content_type="application/json",
            HTTP_USER_AGENT="GiSuivi-Agent/0.2.2",
            REMOTE_USER="GICONSEILS\\a.traore",
        )
        debut = debut.replace(minute=debut.minute + 10)
    html = client.get("/moi", REMOTE_USER="GICONSEILS\\a.traore").content.decode()
    assert "Microsoft Word" in html and WINDOWS in html
    assert ">WINWORD.EXE<" not in html and "SearchHost.exe</td>" not in html
