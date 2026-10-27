"""Sélection des références d'un critère (ADR 0013, § 3), en Python pur.

Pour un critère : les références qui répondent à son filtre, avec l'état de leur preuve,
classées : prouvées d'abord, puis à auditer, puis manquantes ; à preuve égale, le plus de
mots-clés trouvés, la plus récente, puis le code. Une référence absorbée (ADR 0008) n'est jamais
retenue : on cite le code gardé.

Les choix d'une personne passent par-dessus le filtre (`choix` : identifiant → vrai pour forcer,
faux pour exclure) : une référence exclue disparaît, une référence forcée entre même si le filtre
ne la retient pas. Sa preuve est exigée comme pour les autres.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from moteur.avis.filtres import (
    ORDRE_PREUVE,
    Filtre,
    Manque,
    Preuve,
    Reference,
    correspond,
    mots_cles_trouves,
    preuve,
)


@dataclass(frozen=True)
class Candidate:
    """Une référence éligible au critère."""

    reference: Reference
    preuve: Preuve
    manques: tuple[Manque, ...] = ()
    mots_cles: int = 0  # mots-clés du filtre trouvés dans l'intitulé
    forcee: bool = False  # retenue par une personne, pas par le filtre
    sure: bool = True  # compte dans la note sûre
    possible: bool = True  # compte dans la note possible


def _rang(c: Candidate) -> tuple:
    return (ORDRE_PREUVE[c.preuve], -c.mots_cles, -(c.reference.annee or 0), c.reference.code)


def selectionner(
    filtre: Filtre,
    references: Iterable[Reference],
    choix: Mapping[int, bool] | None = None,
) -> list[Candidate]:
    """Les références éligibles au critère, classées. Quand le critère ne demande pas de
    justificatif (`pieces_completes_requises` à false), toutes comptent dans les deux notes et
    la preuve n'est qu'indicative."""
    choix = choix or {}
    candidates = []
    for r in references:
        if r.absorbee or choix.get(r.ident) is False:
            continue
        par_filtre = correspond(filtre, r)
        if not par_filtre and choix.get(r.ident) is not True:
            continue
        etat, manques = preuve(filtre, r)
        exigee = filtre.pieces_completes_requises
        candidates.append(
            Candidate(
                reference=r,
                preuve=etat,
                manques=manques,
                mots_cles=mots_cles_trouves(filtre, r),
                forcee=not par_filtre,
                sure=not exigee or etat == Preuve.PROUVEE,
                possible=not exigee or etat != Preuve.MANQUANTE,
            )
        )
    return sorted(candidates, key=_rang)
