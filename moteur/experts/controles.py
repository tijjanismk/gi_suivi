"""Contrôles des affectations d'un expert (ADR 0012, § 2) et années d'expérience.

Une affectation sans date de fin est en cours : elle court jusqu'à la date de référence.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from itertools import combinations


@dataclass(frozen=True)
class Periode:
    ident: int
    libelle: str  # ce que l'alerte affiche : code de la mission et poste
    du: date | None
    au: date | None
    plein_temps: bool = True


@dataclass(frozen=True)
class Alerte:
    idents: tuple[int, ...]
    message: str


def annees_experience(debut_carriere: int | None, aujourd_hui: date) -> int | None:
    """Années pleines depuis le 1er janvier de l'année de début de carrière."""
    if not debut_carriere or debut_carriere > aujourd_hui.year:
        return None
    return aujourd_hui.year - debut_carriere


def _fin(p: Periode, reference: date) -> date:
    return p.au or reference


def alertes(periodes: Iterable[Periode], reference: date) -> list[Alerte]:
    """Dates incohérentes, et chevauchements de deux affectations à temps plein (un expert ne
    peut pas être à plein temps sur deux missions à la fois)."""
    liste = list(periodes)
    resultat: list[Alerte] = []
    for p in liste:
        if p.du and p.au and p.au < p.du:
            resultat.append(Alerte((p.ident,), f"{p.libelle} : la fin précède le début"))
    datees = [p for p in liste if p.du and p.plein_temps and _fin(p, reference) >= p.du]
    for a, b in combinations(sorted(datees, key=lambda p: p.du), 2):
        debut, fin = max(a.du, b.du), min(_fin(a, reference), _fin(b, reference))
        if debut <= fin:
            jours = (fin - debut).days + 1
            resultat.append(
                Alerte(
                    (a.ident, b.ident),
                    f"{a.libelle} et {b.libelle} : à temps plein toutes deux pendant {jours} jour"
                    f"{'s' if jours > 1 else ''} (du {debut:%d/%m/%Y} au {fin:%d/%m/%Y})",
                )
            )
    return resultat
