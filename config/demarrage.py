"""Choix du module de réglages avant le chargement de Django.

Sur le serveur, `.env` contient `DJANGO_SETTINGS_MODULE=config.settings.prod`. Les tâches
planifiées lancent `manage.py` sans variable d'environnement : sans cette lecture, elles
tourneraient avec les réglages de développement.
"""

from __future__ import annotations

import os
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent


def module_reglages(fichier_env: Path, defaut: str) -> str:
    """Valeur de `DJANGO_SETTINGS_MODULE` lue dans `.env`, sinon `defaut`."""
    try:
        lignes = fichier_env.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return defaut
    for ligne in lignes:
        cle, egal, valeur = ligne.strip().partition("=")
        if egal and cle.strip() == "DJANGO_SETTINGS_MODULE":
            return valeur.strip().strip("\"'") or defaut
    return defaut


def choisir_reglages(defaut: str = "config.settings.dev") -> None:
    """La variable d'environnement prime ; sinon `.env` ; sinon `defaut`."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", module_reglages(RACINE / ".env", defaut))
