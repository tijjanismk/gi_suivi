"""Sommaire et intercalaires d'un AMI : la carte de la fiche et les feuilles à imprimer, tirées de
la même liste (modèle : le dossier FIER II, Ségou, 2026), pour la part du bureau."""

from __future__ import annotations

from datetime import date
from html import unescape

import pytest
from django.test import override_settings
from freezegun import freeze_time

from administratif.tests.conftest import AWA, DIR, IIS, VUE
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
    codes = ("A", "A.1", "A.2", "A.3", "A.4", "B", "C", "D", "D.1", "E", "E.1", "E.2", "E.2.1")
    for code in (*codes, "F"):
        assert f'data-rubrique="{code}"' in page
    assert "ACCORD DE GROUPEMENT" in page and "DU GROUPEMENT" not in page  # la part du bureau
    assert "EXPÉRIENCES SPÉCIFIQUES DANS LES ÉTUDES HYDROAGRICOLES<" in page  # première ligne
    assert 'data-rubrique="E.3"' not in page  # critère en brouillon, pas encore validé
    assert "présentation du bureau non cochée dans les pièces exigées" in page
    assert "aucun poste saisi" in page
    assert f'href="/avis/{fier_ii.pk}/intercalaires"' in page


def test_les_intercalaires_une_feuille_par_ligne_du_sommaire(client, fier_ii):
    page = html(client.get(f"/avis/{fier_ii.pk}/intercalaires", **VUE))
    feuilles = page.count('class="feuille intercalaire"')
    assert feuilles == page.count("<li class=") == 14  # 5 A, B, C, 2 D, 4 E, F
    assert "SOMMAIRE DE LA MANIFESTATION D'INTÉRÊT" in page
    assert '<h2 class="cadre">E.2.1. EXPÉRIENCES SPÉCIFIQUES DANS LES ÉTUDES' in page
    assert '<h2 class="cadre">B. PIÈCES ADMINISTRATIVES</h2>' in page
    assert JournalAcces.objects.filter(cible=f"{fier_ii.pk} intercalaires").exists()
    assert client.get(f"/avis/{fier_ii.pk}/intercalaires", **AWA).status_code == 403


def test_entete_et_pied_lus_sur_le_partage(client, fier_ii, settings, tmp_path):
    settings.PARTAGE_GIC = str(tmp_path)
    url = f"/avis/{fier_ii.pk}/intercalaires"
    page = html(client.get(url, **DIR))
    assert 'class="entete-image"' not in page and 'class="pied-image"' not in page
    assert '<p class="objet">Études techniques' in page  # en-tête texte, faute d'image

    dossier = tmp_path / "AVIS" / "MALI" / "2026-10" / "FIER-II"
    dossier.mkdir(parents=True)
    (dossier / "ENTETE.png").write_bytes(b"\x89PNG\r\n\x1a\nen-tete")
    (tmp_path / "ADMINISTRATIF" / "LOGOS").mkdir(parents=True)
    (tmp_path / "ADMINISTRATIF" / "LOGOS" / "PIED.jpg").write_bytes(b"\xff\xd8pied du bureau")
    fier_ii.fichier_avis_chemin = "AVIS\\MALI\\2026-10\\FIER-II\\ami.pdf"
    fier_ii.save()
    page = html(client.get(url, **DIR))
    assert page.count(f'src="{url}/entete"') == page.count('class="feuille ') == 15
    assert page.count(f'src="{url}/pied"') == 15 and '<p class="objet">' not in page
    r = client.get(f"{url}/entete", **VUE)
    assert r.status_code == 200 and r["Content-Type"] == "image/png"
    assert client.get(f"{url}/pied", **DIR)["Content-Type"] == "image/jpeg"  # celui du bureau

    (dossier / "PIED.png").write_bytes(b"\x89PNG\r\n\x1a\npied du groupement")
    assert client.get(f"{url}/pied", **DIR)["Content-Type"] == "image/png"  # celui de l'avis
    assert client.get(f"{url}/autre", **DIR).status_code == 404
    assert client.get(f"{url}/entete", **AWA).status_code == 403


def test_ni_sommaire_ni_intercalaires_hors_ami(client, fier_ii):
    fier_ii.type = Avis.Type.DP
    fier_ii.save()
    assert "Sommaire de la manifestation" not in html(client.get(f"/avis/{fier_ii.pk}/", **DIR))
    assert client.get(f"/avis/{fier_ii.pk}/intercalaires", **DIR).status_code == 404
