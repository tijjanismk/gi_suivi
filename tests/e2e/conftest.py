"""Fixtures des parcours dans un vrai navigateur (marqueur `navigateur`, Playwright + Chromium).

Playwright est importé dans les fixtures seulement : sans lui (intégration continue), les autres
tests de bout en bout tournent quand même et les parcours dans le navigateur sont ignorés.
"""

from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def navigateur():
    sync_api = pytest.importorskip("playwright.sync_api")
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
def donnees_de_depart(db):
    """Les données posées par les migrations (types de pièces, domaines), vidées par les tests
    transactionnels qui ont tourné avant : on les remet si elles manquent."""
    from django.apps import apps

    from administratif.models import TypePiece
    from referentiel.models import Domaine

    if not TypePiece.objects.exists():
        importlib.import_module("administratif.migrations.0002_types_initiaux").creer(apps, None)
    if not Domaine.objects.exists():
        importlib.import_module("referentiel.migrations.0002_domaines").creer(apps, None)


def capturer(page, nom: str) -> None:
    """Capture d'écran pleine page dans le dossier GIC_CAPTURES, s'il est défini."""
    dossier = os.environ.get("GIC_CAPTURES")
    if dossier:
        Path(dossier).mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(Path(dossier) / f"{nom}.png"), full_page=True)
