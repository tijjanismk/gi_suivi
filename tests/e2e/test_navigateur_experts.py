"""Parcours du vivier dans Chromium (ADR 0012) : créer un expert, l'affecter à deux références
avec leur preuve, voir l'alerte de chevauchement, retrouver l'expert sur la fiche de la
référence."""

from __future__ import annotations

import pytest

from tests.e2e.conftest import capturer

pytestmark = [pytest.mark.e2e, pytest.mark.navigateur, pytest.mark.django_db(transaction=True)]

sync_api = pytest.importorskip("playwright.sync_api")


@pytest.fixture
def references(donnees_de_depart):
    from references import services

    rapport = services.importer(
        [
            {
                "code": "GIC-HYD-ETU-033",
                "intitule_court": "APD du barrage de Samé Ouolof",
                "annee": "2016",
            },
            {"code": "GIC-AEP-CTR-003", "intitule_court": "Contrôle des travaux d'AEP de Kayes"},
        ]
    )
    assert not rapport.erreurs


def test_creer_affecter_et_controler(onglet, live_server, references):
    page, expect = onglet, sync_api.expect
    page.goto(f"{live_server.url}/experts/")
    page.get_by_role("link", name="Nouvel expert").click()
    page.locator("#expert-nom").fill("TRAORÉ")
    page.locator("#expert-prenoms").fill("Awa")
    page.locator("#expert-specialite").fill("Hydraulique")
    page.locator("#expert-debut_carriere").fill("2011")
    page.get_by_role("button", name="Enregistrer").click()
    expect(page.get_by_text("TRAORÉ Awa enregistré")).to_be_visible()

    for code, poste, du, au, preuve in (
        ("GIC-HYD-ETU-033", "chef de mission", "2016-01-01", "2016-12-31", "contrat annexe 2"),
        ("GIC-AEP-CTR-003", "hydraulicien", "2016-10-01", "2017-03-31", "rapport de démarrage"),
    ):
        page.locator("#affecter summary").click()
        page.locator("#affecter-mission").select_option(
            label=page.locator("#affecter-mission option", has_text=code).inner_text()
        )
        page.locator("#affecter-poste").fill(poste)
        page.locator("#affecter-preuve").fill(preuve)
        page.locator("#affecter-du").fill(du)
        page.locator("#affecter-au").fill(au)
        page.get_by_role("button", name="Affecter").click()
        expect(page.get_by_text(f"affecté à {code} comme {poste}")).to_be_visible()

    expect(page.locator("#alertes")).to_contain_text("à temps plein toutes deux pendant 92 jours")
    expect(page.locator("#table-affectations tbody tr")).to_have_count(2)
    capturer(page, "12-fiche-expert")

    page.goto(f"{live_server.url}/references/GIC-HYD-ETU-033/")
    expect(page.locator("#experts-affectes")).to_contain_text("TRAORÉ Awa · chef de mission")
    page.goto(f"{live_server.url}/experts/?mobilisables=1")
    expect(page.locator("#experts-total")).to_have_text("1 expert")
