"""Codes de référence (règle 2 de CONTEXT.md, ADR 0008 § 2) : GIC-<domaine>-<nature>-<numéro>.

Un code est attribué une fois : le numéro suivant de la série (domaine, nature), en comptant
toutes les fiches, absorbées comprises, pour qu'un numéro déjà donné ne revienne jamais.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

NATURES = ("ETU", "CTR", "ETC")
MOTIF = re.compile(r"^GIC-([A-Z]{3})-(ETU|CTR|ETC)-(\d{3,})$")


def decomposer(code: str) -> tuple[str, str, int] | None:
    """« GIC-HYD-ETU-043 » → (« HYD », « ETU », 43) ; None si le code n'a pas cette forme."""
    m = MOTIF.match((code or "").strip().upper())
    return (m.group(1), m.group(2), int(m.group(3))) if m else None


def prochain_code(domaine: str, nature: str, existants: Iterable[str]) -> str:
    """Le premier numéro libre après le plus grand de la série, sur trois chiffres au moins."""
    domaine, nature = domaine.strip().upper(), nature.strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", domaine) or nature not in NATURES:
        raise ValueError(f"série inconnue : {domaine}-{nature}")
    plus_grand = max(
        (
            n
            for d, nat, n in filter(None, map(decomposer, existants))
            if (d, nat) == (domaine, nature)
        ),
        default=0,
    )
    return f"GIC-{domaine}-{nature}-{plus_grand + 1:03d}"
