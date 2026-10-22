"""Parcours des références dans Chromium (ADR 0008) : liste maîtresse fictive importée,
arbitrage des doublons à l'écran, liste filtrée par domaine secondaire, fiche absorbée."""

from __future__ import annotations

import pytest

from tests.e2e.conftest import capturer

pytestmark = [pytest.mark.e2e, pytest.mark.navigateur, pytest.mark.django_db(transaction=True)]

sync_api = pytest.importorskip("playwright.sync_api")

SAME = "Étude d'avant-projet détaillé de la réhabilitation du barrage de Samé Ouolof"
LIGNES = [
    {"code": "GIC-HYD-ETU-033", "intitule_court": SAME, "client": "WHH", "annee": "2016"},
    {"code": "GIC-ENV-ETU-020", "intitule_court": SAME, "client": "WHH", "annee": "2016"},
    {
        "code": "GIC-AEP-CTR-003",
        "intitule_court": "Contrôle des travaux d'AEP de Kayes",
        "client": "SOMAGEP",
        "annee": "2020",
        "montant": "45 000 000",
    },
    {
        "code": "GIC-AEP-ETU-001",
        "intitule_court": "Études d'AEP de Kayes",
        "client": "SOMAGEP",
        "annee": "2019",
        "montant": "45 000 000",
    },
    {"code": "GIC-RTE-CTR-002", "intitule_court": "Contrôle de la piste Kati-Kolokani"},
]


@pytest.fixture
def liste_fictive(donnees_de_depart):
    from references import services

    rapport = services.importer(LIGNES)
    assert not rapport.erreurs


def test_arbitrer_les_doublons(onglet, live_server, liste_fictive):
    page, expect = onglet, sync_api.expect
    page.goto(f"{live_server.url}/references/")
    expect(page.locator("#ref-total")).to_have_text("5 références")
    page.get_by_role("link", name="Doublons à arbitrer").first.click()
    expect(page.locator("#doublons-total")).to_contain_text("2 paires à arbitrer")
    capturer(page, "8-doublons")

    # le cas SOMAPEP : même intitulé dans deux domaines ; on garde le code proposé
    same = page.locator('[data-paire*="GIC-ENV-ETU-020"]')
    expect(same).to_contain_text("même intitulé")
    same.get_by_role("button", name="Même contrat : garder GIC-ENV-ETU-020").click()
    expect(page.get_by_text("GIC-HYD-ETU-033 est absorbée par GIC-ENV-ETU-020")).to_be_visible()

    # étude et contrôle du même marché : on garde l'étude, qui devient ETC
    kayes = page.locator('[data-paire*="GIC-AEP-CTR-003"]')
    expect(kayes).to_contain_text("même client et même montant (45 000 000)")
    kayes.get_by_role("button", name="Même contrat : garder GIC-AEP-ETU-001").click()
    expect(page.get_by_text("Aucune paire suspecte à arbitrer.")).to_be_visible()

    # la liste : HYD est maintenant un domaine secondaire du code gardé
    page.goto(f"{live_server.url}/references/?domaine=HYD")
    ligne = page.locator('#table-references tr[data-code="GIC-ENV-ETU-020"]')
    expect(ligne).to_contain_text("+ HYD")
    expect(page.locator("#ref-total")).to_have_text("1 référence")
    capturer(page, "9-references-hyd")

    page.goto(f"{live_server.url}/references/GIC-AEP-ETU-001/")
    expect(page.locator("#fiche-reference")).to_contain_text("ETC — études et contrôle")
    expect(page.locator("#absorbees")).to_contain_text("GIC-AEP-CTR-003")
    page.get_by_role("link", name="GIC-AEP-CTR-003").click()
    expect(page.locator("#absorbee")).to_contain_text("GIC-AEP-ETU-001")


def test_lecture_seule_sans_decision(onglet, live_server, liste_fictive, settings):
    settings.GROUPES_DEV = ["GI-Direction-Lecture"]
    onglet.goto(f"{live_server.url}/references/doublons/")
    sync_api.expect(onglet.get_by_text("Consultation seule")).to_be_visible()
    sync_api.expect(onglet.get_by_role("button", name="Contrats différents")).to_have_count(0)


def test_justificatifs_et_ouvrages(onglet, live_server, liste_fictive, tmp_path, settings):
    from administratif.demo import pdf

    page, expect = onglet, sync_api.expect
    settings.PARTAGE_GIC = str(tmp_path)
    dossier = tmp_path / "REFERENCES" / "02_JUSTIFICATIFS" / "GIC-ENV-ETU-020"
    dossier.mkdir(parents=True)
    for nom in ("GARDE.pdf", "SIGNATURE.pdf", "ATTESTATION.pdf"):
        (dossier / nom).write_bytes(pdf(f"{nom} Samé Ouolof"))

    page.goto(f"{live_server.url}/references/GIC-ENV-ETU-020/")
    expect(page.locator("#bilan-justificatifs")).to_contain_text("Page de garde : manquante")
    page.get_by_role("link", name="Rattacher et auditer").click()
    for nom in ("ATTESTATION.pdf", "GARDE.pdf", "SIGNATURE.pdf"):
        page.locator(f'#table-fichiers tr[data-fichier="{nom}"]').get_by_role(
            "button", name="Rattacher"
        ).click()
        expect(page.get_by_text(f"« {nom} » rattaché")).to_be_visible()
    for type_ in ("garde", "signature", "attestation"):
        carte = page.locator(f'[data-emplacement="{type_}"]')
        carte.locator('select[name="lisible"]').select_option("oui")
        carte.locator('select[name="coherente"]').select_option("oui")
        carte.get_by_role("button", name="Enregistrer l'audit").click()
        expect(page.locator(f'[data-emplacement="{type_}"] [data-etat="bonne"]')).to_be_visible()
    expect(page.locator("#justificatifs-bilan")).to_contain_text("Référence complète")
    capturer(page, "10-justificatifs")

    page.goto(f"{live_server.url}/references/GIC-ENV-ETU-020/ouvrages")
    page.locator("#ouvrage-micro-barrage").check()
    page.locator("#livrable-apd").check()
    page.locator("#q-superficie-ha").fill("30,5")
    page.locator("#s-superficie-ha").fill("contrat p. 4")
    page.get_by_role("button", name="Enregistrer").click()
    expect(page.locator("#fiche-ouvrages")).to_contain_text("Micro-barrage")
    expect(page.locator("#fiche-ouvrages")).to_contain_text("Superficie aménagée : 30,5 ha")
    capturer(page, "11-fiche-reference")

    page.goto(f"{live_server.url}/references/?pieces=completes&ouvrage=micro-barrage")
    expect(page.locator("#ref-total")).to_have_text("1 référence")
    expect(page.locator('#table-references tr[data-code="GIC-ENV-ETU-020"]')).to_contain_text(
        "3 / 3"
    )
