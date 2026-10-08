"""Groupes AD d'une personne par l'API Windows du serveur (ADR 0006).

Le serveur est le contrôleur de domaine : `win32net` interroge l'annuaire local avec l'identité
du service, sans mot de passe.
Réglage : IDENTITE_LECTEUR_GROUPES = "identite.groupes_windows.groupes_de".
Option IDENTITE_SERVEUR_GROUPES : nom d'un autre serveur à interroger (None = cette machine).
"""

from __future__ import annotations

from django.conf import settings

LG_INCLUDE_INDIRECT = 1  # groupes locaux obtenus aussi par appartenance à un groupe global


def nom_de_compte(login: str) -> str:
    """`GICONSEILS\\jean`, `jean@giconseils.local` ou `jean` → `jean`."""
    return login.rsplit("\\", 1)[-1].split("@", 1)[0].strip()


def groupes_de(login: str) -> list[str]:
    import win32net  # Windows seulement ; la dépendance porte le marqueur sys_platform

    serveur = getattr(settings, "IDENTITE_SERVEUR_GROUPES", None) or None
    compte = nom_de_compte(login)
    if not compte:
        return []
    globaux = {nom for nom, _attributs in win32net.NetUserGetGroups(serveur, compte)}
    locaux = set(win32net.NetUserGetLocalGroups(serveur, compte, LG_INCLUDE_INDIRECT))
    return sorted(globaux | locaux)
