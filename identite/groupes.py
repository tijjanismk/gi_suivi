"""Lecture des groupes AD d'un utilisateur.

En développement, les groupes sont ceux de `GROUPES_DEV`. Sur le serveur, la source est
choisie par `IDENTITE_LECTEUR_GROUPES` (chemin pointé d'une fonction `login -> list[str]`).

Décidé (ADR 0006) : en production, `identite.groupes_windows.groupes_de` (API Windows du
contrôleur de domaine, `pywin32`). Sans source, l'utilisateur n'a aucun groupe, donc aucun droit
direction — l'application échoue fermée, jamais ouverte.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.utils.module_loading import import_string

log = logging.getLogger(__name__)


def lire_groupes(login: str) -> list[str]:
    if settings.IDENTITE_SOURCE == "dev":
        return list(getattr(settings, "GROUPES_DEV", []))
    chemin = getattr(settings, "IDENTITE_LECTEUR_GROUPES", None)
    if not chemin:
        log.warning("Aucune source de groupes AD configurée : %s n'a aucun droit.", login)
        return []
    try:
        return list(import_string(chemin)(login))
    except Exception:  # annuaire injoignable : on garde les groupes précédents (voir services)
        log.exception("Lecture des groupes AD impossible pour %s", login)
        raise
