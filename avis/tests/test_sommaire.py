"""Sommaire, intercalaires et dossier d'un AMI (AV11, AV14) : la carte de la fiche et les pages à
imprimer, tirées du même plan (cas d'essai : le barème FIER II, Ségou, 2026), part du bureau."""

from __future__ import annotations

from datetime import date
from html import unescape

import pytest
from django.test import override_settings
from freezegun import freeze_time

from administratif.tests.conftest import AWA, DIR, IIS, VUE
from avis import outils_mcp as outils
from avis.models import Avis, Critere
from suivi.models import JournalAcces

pytestmark = pytest.mark.django_db


def html(r) -> str:
    return unescape(r.content.decode())


@pytest.fixture(autouse=True)
def le_28_octobre():
    with freeze_time("2026-10-28 10:00"), override_settings(**IIS):
        yield


@pytest.fixture
def fier_ii():
    a = Avis.objects.create(
        reference="AMI-FIER-II-SEGOU",
        objet="Études techniques et contrôle des travaux des infrastructures du projet FIER II",
        type=Avis.Type.AMI,
        groupement=True,
        date_limite=date(2026, 11, 15),
    )
    for ordre, code, libelle in (
        (1, "1", "Expériences générales en rapport avec la mission"),
        (2, "2", "Expériences spécifiques"),
        (3, "2.1", "Expériences spécifiques dans les études hydroagricoles\n2 points par étude"),
    ):
        Critere.objects.create(
            avis=a, code=code, ordre=ordre, libelle=libelle, mode=Critere.Mode.MANUEL
        )
    Critere.objects.create(
        avis=a, code="3", ordre=4, libelle="Contrôles", mode=Critere.Mode.MANUEL, brouillon=True
    )
    return a


def test_la_fiche_d_un_ami_donne_son_sommaire(client, fier_ii):
    page = html(client.get(f"/avis/{fier_ii.pk}/", **DIR))
    assert "Sommaire de la manifestation d'intérêt" in page
    codes = ("A", "A.1", "A.2", "A.3", "A.4", "B", "C", "D", "D.1", "D.2", "D.2.1", "E", "F")
    for code in codes:
        assert f'data-rubrique="{code}"' in page
    assert "ACCORD DE GROUPEMENT" in page and "DU GROUPEMENT" not in page  # la part du bureau
    assert "Expériences spécifiques dans les études hydroagricoles<" in page  # première ligne
    assert 'data-rubrique="D.2.2"' not in page  # critère en brouillon, pas encore validé
    assert "présentation du bureau non cochée dans les pièces exigées" in page
    assert "aucun poste saisi" in page
    assert f'href="/avis/{fier_ii.pk}/dossier"' in page
    assert f'href="/avis/{fier_ii.pk}/intercalaires"' in page


def test_les_intercalaires_une_feuille_par_ligne_du_plan(client, fier_ii):
    page = html(client.get(f"/avis/{fier_ii.pk}/intercalaires", **VUE))
    assert page.count('class="page intercalaire"') == 13  # 5 A, B, C, 4 D, E, F
    assert page.count("<li class=") == 9  # au sommaire, les A.x n'ont pas de ligne
    assert "SOMMAIRE DE LA MANIFESTATION D’INTERET" in page
    titre = "D.2.1. Expériences spécifiques dans les études hydroagricoles"
    assert f'<h2 class="banniere">{titre}</h2>' in page
    assert '<h2 class="banniere">B. PIÈCES ADMINISTRATIVES DE ' in page
    assert 'data-genre="lettre"' not in page  # le sommaire et les intercalaires seulement
    assert JournalAcces.objects.filter(cible=f"{fier_ii.pk} intercalaires").exists()
    assert client.get(f"/avis/{fier_ii.pk}/intercalaires", **AWA).status_code == 403


def test_dossier_entete_pied_et_logo_lu_sur_le_partage(client, fier_ii, settings, tmp_path):
    settings.PARTAGE_GIC = str(tmp_path)
    page = html(client.get(f"/avis/{fier_ii.pk}/intercalaires", **DIR))
    pied = '<footer class="hf-bas">Études techniques et contrôle'
    assert page.count('<header class="hf-haut">') == page.count(pied) == 14  # le sommaire et 13 intercalaires
    url = f"/avis/{fier_ii.pk}/dossier"
    page = html(client.get(url, **DIR))
    assert 'data-genre="lettre"' in page and 'data-genre="organigramme"' in page
    assert 'src="/avis/logo"' not in page and "le nom du bureau est écrit à sa place" in page
    assert client.get("/avis/logo", **VUE).status_code == 404
    assert JournalAcces.objects.filter(cible=f"{fier_ii.pk} dossier").exists()

    (tmp_path / "ADMINISTRATIF" / "LOGOS").mkdir(parents=True)
    (tmp_path / "ADMINISTRATIF" / "LOGOS" / "LOGO.png").write_bytes(b"\x89PNG\r\n\x1a\nlogo")
    assert 'src="/avis/logo"' in html(client.get(url, **DIR))
    r = client.get("/avis/logo", **VUE)
    assert r.status_code == 200 and r["Content-Type"] == "image/png"
    assert client.get("/avis/logo", **AWA).status_code == 403
    assert client.get(url, **AWA).status_code == 403


def test_outil_mcp_plan_du_dossier(fier_ii):
    r = outils.plan_dossier(fier_ii.pk)
    assert r["adresse"] == f"/avis/{fier_ii.pk}/dossier"
    codes = [s["code"] for s in r["sommaire"]]
    assert codes == ["A", "B", "C", "D", "D.1", "D.2", "D.2.1", "E", "F"]
    assert r["pages"][0] == {"page": 1, "genre": "couverture", "etat": "redigee"}
    assert sum(r["compte"].values()) == len(r["pages"])
    fier_ii.type = Avis.Type.DP
    fier_ii.save()
    assert "AMI" in outils.plan_dossier(fier_ii.pk)["erreur"]


def test_ni_sommaire_ni_dossier_hors_ami(client, fier_ii):
    fier_ii.type = Avis.Type.DP
    fier_ii.save()
    assert "Sommaire de la manifestation" not in html(client.get(f"/avis/{fier_ii.pk}/", **DIR))
    assert client.get(f"/avis/{fier_ii.pk}/intercalaires", **DIR).status_code == 404
    assert client.get(f"/avis/{fier_ii.pk}/dossier", **DIR).status_code == 404
