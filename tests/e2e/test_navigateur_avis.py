"""Parcours du dossier d'un AMI (AV14, au modèle des vrais dossiers du bureau) dans Chromium : la
carte « Sommaire » de la fiche, sur grand écran et à la largeur d'un téléphone, puis le dossier à
imprimer (en-tête et pied sur le sommaire, les intercalaires et l'organigramme seulement ;
organigramme en A4 paysage) et les intercalaires seuls. Avec GIC_CAPTURES, les captures et le PDF
imprimé par Chromium y sont écrits."""

from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path

import pytest

from tests.e2e.conftest import capturer

pytestmark = [pytest.mark.e2e, pytest.mark.navigateur, pytest.mark.django_db(transaction=True)]

sync_api = pytest.importorskip("playwright.sync_api")

ETUDES = "Expériences spécifiques dans les études"
CONTROLE = "Expériences spécifiques dans le contrôle et la surveillance des travaux"
BAREME = (  # le barème de l'AMI FIER II (Ségou, 2026) : 1 général, 2.x et 3.x spécifiques
    ("1", "Expériences générales en rapport avec la mission"),
    ("2", "Expériences spécifiques"),
    ("2.1", f"{ETUDES} des travaux d'aménagements hydroagricoles"),
    ("2.2", f"{ETUDES} d'infrastructures aquacoles ou animales"),
    ("2.3", f"{ETUDES} d'infrastructures de bâtiments"),
    ("3", CONTROLE),
    ("3.1", f"{CONTROLE} d'aménagements hydroagricoles"),
    ("3.2", f"{CONTROLE} d'infrastructures aquacoles ou animales"),
    ("3.3", f"{CONTROLE} d'infrastructures de bâtiments"),
)
RUBRIQUES = 18  # A et ses 4 lettres, B, C, D, D.1, D.2, 6 D.2.x, E, F


@pytest.fixture
def fier_ii(donnees_de_depart):
    from avis.models import Avis, Critere
    from referentiel.models import Client

    a = Avis.objects.create(
        reference="AMI-FIER-II-SEGOU",
        objet="Recrutement de bureaux d'ingénieurs-conseils pour la réalisation des études "
        "techniques (APS, APD, EIES/NIES, DAO) et le contrôle/surveillance des travaux des "
        "infrastructures agrégatives du Projet FIER II dans la région de Ségou",
        type=Avis.Type.AMI,
        maitre_ouvrage=Client.objects.create(
            nom="Ministère de l'Entrepreneuriat national, de l'Emploi et de la Formation "
            "professionnelle"
        ),
        groupement=True,
        date_limite=date(2026, 11, 15),
    )
    for ordre, (code, libelle) in enumerate(BAREME, start=1):
        Critere.objects.create(
            avis=a, code=code, ordre=ordre, libelle=libelle, mode=Critere.Mode.MANUEL
        )
    return a


def test_sommaire_dossier_et_intercalaires(onglet, live_server, fier_ii):
    page, expect = onglet, sync_api.expect
    page.goto(f"{live_server.url}/avis/{fier_ii.pk}/")
    lignes = page.locator("#sommaire li")
    expect(lignes).to_have_count(RUBRIQUES)
    expect(lignes.first).to_have_text("A. LETTRES")
    expect(page.locator('#sommaire li[data-rubrique="A.2"]')).to_contain_text(
        "ACCORD DE GROUPEMENT"
    )
    expect(page.locator('#sommaire li[data-rubrique="D.2.6"]')).to_contain_text(
        f"{CONTROLE} d'infrastructures de bâtiments"
    )
    expect(page.locator('#sommaire li[data-rubrique="F"]')).to_contain_text("liste des moyens")
    capturer(page, "13-sommaire-ami")

    page.set_viewport_size({"width": 375, "height": 800})
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    capturer(page, "13-sommaire-ami-telephone")
    page.set_viewport_size({"width": 1366, "height": 900})

    page.get_by_role("link", name="Dossier", exact=True).click()
    expect(page).to_have_title(re.compile("^Dossier"))
    expect(page.locator("section.page-intercalaire")).to_have_count(RUBRIQUES)
    expect(page.locator("section .hf-haut")).to_have_count(RUBRIQUES + 2)  # sommaire, organigramme
    expect(page.locator('section.page-intercalaire[data-rubrique="D.2.6"] h2')).to_have_text(
        f"D.2.6. {CONTROLE} d'infrastructures de bâtiments"
    )
    organigramme = page.locator("section.page-organigramme")
    expect(organigramme).to_have_count(1)
    assert organigramme.evaluate("e => getComputedStyle(e).page") == "paysage"
    capturer(page, "14-dossier-ami")
    page.emulate_media(media="print")
    expect(page.locator(".outils")).to_be_hidden()
    dossier = os.environ.get("GIC_CAPTURES")
    if dossier:  # le PDF tel que Chromium l'imprime, portrait et paysage mêlés
        page.pdf(path=str(Path(dossier) / "14-dossier-ami.pdf"), prefer_css_page_size=True)
    page.emulate_media(media="screen")

    page.goto(f"{live_server.url}/avis/{fier_ii.pk}/intercalaires")
    expect(page).to_have_title(re.compile("^Intercalaires"))
    expect(page.locator("section.page")).to_have_count(RUBRIQUES + 1)  # le sommaire en tête
