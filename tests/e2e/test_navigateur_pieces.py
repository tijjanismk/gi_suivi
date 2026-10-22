"""Parcours des pièces administratives dans un vrai navigateur (Chromium, Playwright).

Base d'essai : la base de test de pytest-django, remplie par `administratif.demo` (pièces
fictives, PDF écrits dans un dossier temporaire qui joue le partage). L'identité est celle du
développement (`config.settings.test` : GICONSEILS\\essai, GI-Direction).

    pip install pytest-playwright ; playwright install chromium
    pytest -m navigateur                                  # Chromium invisible
    pytest -m navigateur --headed                         # pour regarder
    set GIC_CAPTURES=C:\\dev\\livraisons\\captures & pytest -m navigateur   # captures d'écran

Sans Playwright ou sans Chromium (intégration continue), ces tests sont ignorés.
"""

from __future__ import annotations

import os
import re
from datetime import date, timedelta
from pathlib import Path

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.navigateur, pytest.mark.django_db(transaction=True)]

sync_api = pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def navigateur():
    # Playwright tourne une boucle asyncio dans ce fil : l'ORM des tests l'accepte ainsi
    os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")
    try:
        pw = sync_api.sync_playwright().start()
        chromium = pw.chromium.launch(headless=os.environ.get("GIC_HEADED") != "1")
    except Exception as e:  # noqa: BLE001 — Chromium absent : on ignore, comme sans Playwright
        pytest.skip(f"Chromium indisponible ({e.__class__.__name__}) : playwright install chromium")
    yield chromium
    chromium.close()
    pw.stop()


@pytest.fixture
def onglet(navigateur):
    contexte = navigateur.new_context(viewport={"width": 1366, "height": 900}, locale="fr-FR")
    p = contexte.new_page()
    erreurs: list[str] = []
    p.on("pageerror", lambda e: erreurs.append(str(e)))
    yield p
    contexte.close()
    assert not erreurs, f"erreurs JavaScript : {erreurs}"


@pytest.fixture
def base_essai(tmp_path, settings):
    """Types de départ (vidés par les tests transactionnels précédents) et pièces fictives."""
    from django.apps import apps

    from administratif import demo
    from administratif.models import TypePiece

    if not TypePiece.objects.exists():
        import importlib

        importlib.import_module("administratif.migrations.0002_types_initiaux").creer(apps, None)
    settings.PARTAGE_GIC = str(tmp_path)
    demo.remplir(tmp_path, date.today())
    return tmp_path


def capturer(page, nom: str) -> None:
    dossier = os.environ.get("GIC_CAPTURES")
    if dossier:
        Path(dossier).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(dossier) / f"{nom}.png"), full_page=True)


def ligne(page, code: str):
    return page.locator(f'#table-pieces tr[data-code="{code}"]')


def test_parcours_registre_depot_rescan_types(onglet, live_server, base_essai):
    page = onglet
    expect = sync_api.expect
    aujourd_hui = date.today()

    # --- 1. Le registre : compteurs, états, alertes d'abord -------------------------------
    page.goto(f"{live_server.url}/administratif/")
    expect(page).to_have_title(re.compile("^Pièces administratives"))
    expect(page.locator('[data-compteur="expirees"]')).to_have_text("1")
    expect(page.locator('[data-compteur="a_renouveler"]')).to_have_text("1")
    expect(ligne(page, "MOYENS")).to_contain_text("expirée depuis 35 j")
    expect(ligne(page, "MOYENS")).to_contain_text("À demander")
    expect(ligne(page, "QUITUS-FISCAL")).to_contain_text("expire dans 15 j")
    expect(ligne(page, "NIF")).to_contain_text("permanente")
    expect(ligne(page, "TVA")).to_contain_text("non requise")
    premiers = page.locator("#table-pieces tbody tr").evaluate_all(
        "rs => rs.slice(0, 2).map(r => r.dataset.code)"
    )
    assert set(premiers) == {"MOYENS", "QUITUS-FISCAL"}
    # la pastille du menu compte les deux pièces à traiter
    expect(page.locator("nav, aside").get_by_text("Pièces administratives").first).to_be_visible()
    capturer(page, "1-registre")

    page.get_by_role("link", name=re.compile(r"^À traiter")).click()
    expect(page.locator("#table-pieces tbody tr")).to_have_count(2)

    # --- 2. La fiche du quitus : version en cours, historique, demande en cours -----------
    page.get_by_role("link", name=re.compile("quitus fiscal")).click()
    expect(page.locator("#version-en-cours")).to_contain_text("QF-0815")
    expect(page.locator("#historique")).to_contain_text("remplacée")
    expect(page.locator("#demande-ouverte")).to_be_visible()
    capturer(page, "2-fiche-quitus")

    # --- 3. Dépôt d'un renouvellement : doublons non sélectionnables, échéance proposée ----
    page.get_by_role("link", name="Déposer la nouvelle version").click()
    expect(page.locator('[data-statut="doublon"] input[type=radio]')).to_be_disabled()
    expect(page.locator('[data-statut="deja_enregistre"] input[type=radio]').first).to_be_disabled()
    expect(page.locator('[data-statut="nouveau"] input[type=radio]')).to_be_checked()
    emission = aujourd_hui - timedelta(days=2)
    page.locator("#depot-emission").fill(emission.isoformat())
    page.locator("#depot-numero").fill("QF-E2E")
    page.get_by_role("button", name="Calculer l'échéance").click()
    expect(page.get_by_text("Échéance proposée")).to_be_visible()
    from moteur.administratif.echeances import ajouter_mois

    expect(page.locator("#depot-fin")).to_have_value(ajouter_mois(emission, 3).isoformat())
    capturer(page, "3-depot-propose")
    page.get_by_role("button", name="Enregistrer la nouvelle version").click()
    expect(page.get_by_text(f"Version du {emission:%d/%m/%Y} enregistrée")).to_be_visible()
    expect(page.locator("#version-en-cours")).to_contain_text("QF-E2E")
    expect(page.locator("#demande-ouverte")).to_have_count(0)  # demande close d'elle-même

    # --- 4. Le registre suit : plus rien à renouveler ------------------------------------
    page.get_by_role("link", name="Pièces administratives").first.click()
    expect(page.locator('[data-compteur="a_renouveler"]')).to_have_text("0")
    expect(ligne(page, "QUITUS-FISCAL")).to_contain_text("valide")

    # --- 5. Nouveau scan de l'attestation INPS (séance de rescan) -------------------------
    from administratif import demo

    dossier_inps = base_essai / "ADMINISTRATIF" / "PIECES" / "INPS"
    (dossier_inps / "INPS septembre propre.pdf").write_bytes(demo.pdf("INPS rescanne", pages=2))
    page.goto(f"{live_server.url}/administratif/deposer?type=INPS")
    page.locator("#depot-nouveau-scan").check()
    page.get_by_role("button", name="Enregistrer la nouvelle version").click()
    expect(page.get_by_text("Nouveau scan enregistré")).to_be_visible()
    expect(page.locator("#historique")).to_contain_text("remplacée par un nouveau scan")
    capturer(page, "5-nouveau-scan")

    # --- 6. Types de pièces : une durée corrigée change l'échéance proposée ---------------
    page.goto(f"{live_server.url}/administratif/types/")
    page.locator('#table-types tr[data-code="NON-FAILLITE"]').get_by_role(
        "link", name="Modifier"
    ).click()
    page.locator("#type-duree_mois").fill("6")
    page.get_by_role("button", name="Enregistrer").click()
    expect(page.locator('#table-types tr[data-code="NON-FAILLITE"]')).to_contain_text(
        "6 mois après l'émission"
    )
    capturer(page, "6-types")
    (base_essai / "ADMINISTRATIF" / "PIECES" / "NON-FAILLITE" / "NF octobre.pdf").write_bytes(
        demo.pdf("Non-faillite octobre")
    )
    page.goto(f"{live_server.url}/administratif/deposer?type=NON-FAILLITE")
    page.locator("#depot-emission").fill(aujourd_hui.isoformat())
    page.get_by_role("button", name="Calculer l'échéance").click()
    expect(page.locator("#depot-fin")).to_have_value(ajouter_mois(aujourd_hui, 6).isoformat())


def test_lecture_seule_ne_voit_pas_les_actions(onglet, live_server, base_essai, settings):
    page = onglet
    settings.GROUPES_DEV = ["GI-Direction-Lecture"]
    page.goto(f"{live_server.url}/administratif/")
    sync_api.expect(page).to_have_title(re.compile("^Pièces administratives"))
    sync_api.expect(page.get_by_role("link", name="Déposer une nouvelle version")).to_have_count(0)
    page.goto(f"{live_server.url}/administratif/deposer")
    sync_api.expect(page.get_by_text("GI-Direction").first).to_be_visible()  # page de refus
