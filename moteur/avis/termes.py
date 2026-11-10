"""Termes des types d'ouvrages (ADR 0019), en Python pur : la comparaison d'un terme à un texte,
et les équivalents qu'un mot-clé d'avis apporte dans les intitulés des références du bureau.

L'AES malienne s'appelle mini-AEP au Niger, AEPS au Burkina : un critère qui écrit « AEPS »
doit retrouver nos références qui disent « adduction d'eau sommaire ». Le mot-clé désigne un
type d'ouvrage quand il est l'un de ses termes validés, de portée « partout », sans pays ou du
pays de l'avis ; il apporte alors tous les termes de ce type, chacun cherché dans les intitulés
des références de son pays (ADR 0019, § 2). Les termes viennent de la base (`referentiel.Terme`,
libellé et sigle des types) ; seuls les termes validés arrivent ici.

La comparaison ignore la casse, les accents, les apostrophes, les tirets, les pluriels en s ou x
et les petits mots, comme les mots-clés ; un sigle (un terme écrit tout en capitales) ne se
compare qu'en capitales et en entier : `PEA` trouve « 12 PEA », pas « pea » ; `OF` ne trouve
pas « of ». Les liens web sont retirés du texte avant de comparer.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass

from moteur.references.doublons import mots, normaliser

PARTOUT, REFERENCES = "partout", "references"  # portées d'un terme (ADR 0019, § 1)
_LIEN = re.compile(r"(https?://|www\.)\S+", re.IGNORECASE)
_JETON = re.compile(r"[^\W_]+")


@dataclass(frozen=True)
class Terme:
    """Un terme validé d'un type d'ouvrage."""

    texte: str  # tel qu'il s'écrit : « AEPS », « poste d'eau autonome »
    type_ouvrage: str  # clé du thésaurus : « aes »
    pays: str = ""  # vide : tous les pays
    portee: str = PARTOUT  # ou REFERENCES : intitulés des références du bureau seulement


def est_sigle(terme: str) -> bool:
    """Un terme écrit tout en capitales, d'au moins deux lettres : AEPS, PEA, F/PMH."""
    lettres = [c for c in terme if c.isalpha()]
    return len(lettres) >= 2 and all(c.isupper() for c in lettres)


def _sans_accents(texte: str) -> str:
    t = unicodedata.normalize("NFKD", texte)
    return "".join(c for c in t if not unicodedata.combining(c))


def _jetons(texte: str) -> list[str]:
    return _JETON.findall(_sans_accents(texte))


def contient(texte: str, terme: str) -> bool:
    """Le terme est-il dans le texte ? Un sigle : ses capitales, en mots entiers et dans l'ordre ;
    sinon tous ses mots, dans n'importe quel ordre, pluriels et accents ignorés."""
    texte = _LIEN.sub(" ", texte or "")
    if est_sigle(terme):
        cherches, jetons = _jetons(terme), _jetons(texte)
        n = len(cherches)
        return n > 0 and any(jetons[i : i + n] == cherches for i in range(len(jetons) - n + 1))
    voulus = mots(terme)
    return bool(voulus) and voulus <= mots(texte)


def meme_terme(mot_cle: str, terme: str) -> bool:
    """Le mot-clé d'un critère est-il ce terme ? « Mini AEP » est « mini-AEP » ; « postes d'eau
    autonomes » est « poste d'eau autonome » ; « pea » n'est pas le sigle « PEA »."""
    if est_sigle(terme):
        return _jetons(mot_cle) == _jetons(terme)
    voulus = mots(terme)
    return bool(voulus) and mots(mot_cle) == voulus


def du_pays(terme: Terme, pays: str) -> bool:
    """Un terme sans pays vaut partout ; sinon, seulement dans son pays."""
    return not terme.pays or normaliser(terme.pays) == normaliser(pays)


def equivalents(mot_cle: str, lexique: Iterable[Terme], pays_avis: str = "") -> tuple[Terme, ...]:
    """Les termes qu'un mot-clé d'avis apporte : s'il est un terme de portée « partout » d'un ou
    plusieurs types d'ouvrages (sans pays, ou du pays de l'avis), tous les termes de ces types,
    à chercher dans les intitulés des références de leur pays. Rien s'il ne désigne aucun type."""
    lexique = tuple(lexique)
    types = {
        t.type_ouvrage
        for t in lexique
        if t.portee == PARTOUT and du_pays(t, pays_avis) and meme_terme(mot_cle, t.texte)
    }
    vus: set[tuple[str, str]] = set()
    retenus = []
    for t in lexique:
        cle = (t.texte, t.pays)
        if t.type_ouvrage in types and cle not in vus:
            vus.add(cle)
            retenus.append(t)
    return tuple(retenus)
