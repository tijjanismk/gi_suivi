"""Doublons de références (ADR 0008, § 4 ; chantier 2, « chasse aux doublons »).

Un contrat ne doit donner qu'une référence. Le moteur PROPOSE des paires suspectes, il ne
fusionne rien : une personne décide. Les passes du chantier 2 :

(a) même montant et même client ;
(b) intitulés très proches (mots en commun, accents et petits mots ignorés) ;
(c) même numéro de contrat.

Et la règle de fusion : si l'une des fiches est une étude et l'autre un contrôle du même
marché, la nature du code gardé devient ETC.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal
from functools import lru_cache
from itertools import combinations

MOTS_VIDES = frozenset(
    "a au aux avec d de des du en et l la le les pour par sur dans un une ou".split()
)
SEUIL_INTITULE = Decimal("0.60")  # part de mots en commun au-delà de laquelle c'est « proche »
ECART_MAX_ANNEES = 1  # au-delà, deux intitulés proches sont deux missions différentes


@dataclass(frozen=True)
class Fiche:
    """Ce que le moteur a besoin de savoir d'une référence."""

    ident: int
    code: str
    intitule: str
    client: str = ""
    annee: int | None = None
    montant: Decimal | None = None
    numero_contrat: str = ""
    nature: str = ""


@dataclass
class Paire:
    a: Fiche
    b: Fiche
    score: Decimal
    raisons: list[str] = field(default_factory=list)

    @property
    def cle(self) -> tuple[int, int]:
        x, y = sorted((self.a.ident, self.b.ident))
        return (x, y)


@lru_cache(maxsize=8192)
def normaliser(texte: str) -> str:
    """Minuscules, sans accents ni ponctuation, espaces réduits."""
    t = unicodedata.normalize("NFKD", texte or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t).split())


def _singulier(mot: str) -> str:
    """« aménagements » et « aménagement » sont le même mot pour comparer deux intitulés."""
    return mot[:-1] if len(mot) > 3 and mot.endswith(("s", "x")) else mot


@lru_cache(maxsize=8192)
def mots(texte: str) -> frozenset[str]:
    return frozenset(
        _singulier(m) for m in normaliser(texte).split() if m not in MOTS_VIDES and len(m) > 1
    )


def proximite(a: str, b: str) -> Decimal:
    """Part des mots en commun (indice de Jaccard), de 0 à 1, arrondie au centième."""
    ma, mb = mots(a), mots(b)
    if not ma or not mb:
        return Decimal(0)
    return (Decimal(len(ma & mb)) / Decimal(len(ma | mb))).quantize(Decimal("0.01"))


def numero_normalise(numero: str) -> str:
    """« N° 09/2026/001/MI » → « 092026001MI » ; vide s'il est trop court pour comparer."""
    t = re.sub(r"^\s*(n\s*[°o]|no\.?|numero\.?)\s*", "", numero or "", flags=re.IGNORECASE)
    t = re.sub(r"[^0-9A-Za-z]", "", t).upper()
    return t if len(t) >= 4 else ""


def comparer(a: Fiche, b: Fiche) -> Paire | None:
    """La paire si elle est suspecte, avec ses raisons et un score de 0 à 1."""
    raisons: list[str] = []
    score = Decimal(0)
    na, nb = numero_normalise(a.numero_contrat), numero_normalise(b.numero_contrat)
    if na and na == nb:
        raisons.append(f"même numéro de contrat ({a.numero_contrat.strip()})")
        score = Decimal(1)
    meme_client = bool(normaliser(a.client)) and normaliser(a.client) == normaliser(b.client)
    if meme_client and a.montant is not None and a.montant > 0 and a.montant == b.montant:
        raisons.append(
            "même client et même montant (" + f"{a.montant:,.0f}".replace(",", " ") + ")"
        )
        score = max(score, Decimal("0.90"))
    p = proximite(a.intitule, b.intitule)
    annees_proches = (
        a.annee is None or b.annee is None or abs(a.annee - b.annee) <= ECART_MAX_ANNEES
    )
    if p >= SEUIL_INTITULE and annees_proches:
        if normaliser(a.intitule) == normaliser(b.intitule):
            raisons.append("même intitulé")
        else:
            raisons.append(f"intitulés proches ({int(p * 100)} % de mots en commun)")
        if meme_client:
            raisons.append("même client")
        score = max(score, p if meme_client else p * Decimal("0.9"))
    if not raisons:
        return None
    return Paire(a, b, score.quantize(Decimal("0.01")), raisons)


def paires_suspectes(fiches: Iterable[Fiche], deja_tranchees=frozenset()) -> list[Paire]:
    """Toutes les paires suspectes, la plus probable d'abord. `deja_tranchees` : clés
    (ident, ident) que la direction a déjà arbitrées ; elles ne reviennent pas."""
    paires = []
    for a, b in combinations(list(fiches), 2):
        paire = comparer(a, b)
        if paire and paire.cle not in deja_tranchees:
            paires.append(paire)
    return sorted(paires, key=lambda p: (-p.score, p.a.code, p.b.code))


def nature_fusionnee(gardee: str, absorbee: str) -> str:
    """Étude + contrôle du même marché : ETC. Sinon la nature du code gardé."""
    natures = {gardee, absorbee}
    if "ETC" in natures or {"ETU", "CTR"} <= natures:
        return "ETC"
    return gardee


_NUMERO = re.compile(r"-(\d+)$")


def code_le_plus_ancien(a: str, b: str) -> str:
    """Proposition par défaut du code à garder : le plus petit numéro de série (attribué en
    premier) ; à égalité, l'ordre alphabétique. La direction peut choisir l'autre."""

    def cle(code: str) -> tuple[int, str]:
        m = _NUMERO.search(code)
        return (int(m.group(1)) if m else 10**9, code)

    return min(a, b, key=cle)
