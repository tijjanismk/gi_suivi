"""Passage entre l'ORM et le moteur : le moteur ne voit que des dataclasses (CONTEXT.md, r. 1)."""

from __future__ import annotations

from moteur.suivi import types as m
from suivi.models import Parametre, Racine, RegleException

CORRESPONDANCE_LECTEURS = "correspondance_lecteurs"


def racines_moteur() -> list[m.Racine]:
    return [
        m.Racine(r.chemin, r.profondeur, r.motif_code) for r in Racine.objects.filter(active=True)
    ]


def exceptions_moteur() -> list[m.RegleException]:
    return [
        m.RegleException(e.motif, e.type, e.dossier.chemin_windows, e.dossier.code or None)
        for e in RegleException.objects.select_related("dossier")
    ]


def parametre(cle: str, defaut=None):
    p = Parametre.objects.filter(cle=cle).first()
    return p.valeur if p is not None else defaut


def correspondance_lecteurs() -> dict[str, str]:
    return {k.upper(): v for k, v in (parametre(CORRESPONDANCE_LECTEURS, {}) or {}).items()}
