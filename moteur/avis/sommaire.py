"""Sommaire et intercalaires de la réponse à un AMI, en Python pur.

Le modèle est le dossier déposé pour FIER II (Ségou, 2026) : rubriques A à F, une ligne par
intercalaire, si bien que le sommaire et les intercalaires viennent de la même liste et ne peuvent
pas diverger. L'application prépare la part du bureau seulement, même en groupement (celle des
autres membres se fait hors d'elle) : pas d'intercalaire par membre, des libellés sans « du
groupement » ; seul l'accord de groupement s'ajoute aux lettres. Les rubriques de E sont les
critères du barème, numérotés comme lui (critère 2.1 → E.2.1). La présentation du bureau et la
liste des moyens, pièces de l'administratif, ont leur rubrique (C et F) et ne comptent pas en B.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

PIECES_A_PART = {"PRESENTATION": "présentation du bureau", "MOYENS": "liste des moyens"}


@dataclass(frozen=True)
class Piece:
    code: str
    etat: str  # en mots, à la date limite de dépôt
    a_regler: bool


@dataclass(frozen=True)
class Critere:
    code: str
    libelle: str
    retenues: int | None = None  # références retenues par le filtre ; None : noté à la main


@dataclass(frozen=True)
class Rubrique:
    code: str  # « A », « A.1 », « E.2.1 »
    libelle: str  # tel qu'imprimé
    niveau: int  # 1 pour A à F
    etat: str = ""  # ce que l'application en sait, en mots ; vide si elle n'en sait rien
    a_regler: bool | None = None  # None : l'état informe sans juger


def _s(n: int) -> str:
    return "s" if n > 1 else ""


def _etat_pieces(pieces: list[Piece]) -> tuple[str, bool | None]:
    if not pieces:
        return "aucune pièce exigée", None
    n, k = len(pieces), sum(p.a_regler for p in pieces)
    if k:
        return f"{k} pièce{_s(k)} sur {n} à régler à la date limite", True
    return f"{n} pièce{_s(n)} valide{_s(n)} à la date limite", False


def _etat_piece(pieces: dict[str, Piece], code: str) -> tuple[str, bool]:
    nom = PIECES_A_PART[code]
    if code not in pieces:
        return f"{nom} non cochée dans les pièces exigées", True
    return f"{nom} : {pieces[code].etat}", pieces[code].a_regler


def _etat_postes(postes: list[bool]) -> tuple[str, bool | None]:
    if not postes:
        return "aucun poste saisi", None
    n, k = len(postes), postes.count(False)
    if k:
        return f"{k} poste{_s(k)} sur {n} sans expert retenu", True
    return f"{n} poste{_s(n)}, un expert retenu pour chacun", False


def _rubrique_e(c: Critere) -> Rubrique:
    code = c.code if c.code.upper().startswith("E.") else f"E.{c.code}"
    libelle = c.libelle.strip().splitlines()[0].upper() if c.libelle.strip() else ""
    r = c.retenues
    etat = "" if r is None else f"{r} référence{_s(r)} retenue{_s(r)}"
    return Rubrique(code, libelle, code.count(".") + 1, etat, True if r == 0 else None)


def sommaire(
    criteres: Iterable[Critere],
    groupement: bool = False,
    pieces: Iterable[Piece] = (),
    postes: Iterable[bool] = (),
) -> list[Rubrique]:
    """Les intercalaires dans l'ordre du dossier. `postes` : pour chaque poste demandé, un expert
    est-il retenu."""
    criteres, pieces, postes = list(criteres), {p.code: p for p in pieces}, list(postes)
    lettres = ["LETTRE DE MANIFESTATION D'INTÉRÊT"]
    if groupement:
        lettres.append("ACCORD DE GROUPEMENT")
    lettres += ["PROCURATION DE SIGNATURE", "ADRESSES ET CONTACTS DES CONSULTANTS"]
    b = [p for code, p in pieces.items() if code not in PIECES_A_PART]
    sans_bareme = ("aucun critère au barème", None) if not criteres else ("", None)
    return [
        Rubrique("A", "LETTRES", 1),
        *(Rubrique(f"A.{i}", t, 2) for i, t in enumerate(lettres, start=1)),
        Rubrique("B", "PIÈCES ADMINISTRATIVES", 1, *_etat_pieces(b)),
        Rubrique("C", "PRÉSENTATION", 1, *_etat_piece(pieces, "PRESENTATION")),
        Rubrique("D", "PERSONNEL CLÉ", 1, *_etat_postes(postes)),
        Rubrique("D.1", "CV DÉTAILLÉS DU PERSONNEL CLÉ", 2),
        Rubrique("E", "EXPÉRIENCES", 1, *sans_bareme),
        *(_rubrique_e(c) for c in criteres),
        Rubrique("F", "MOYENS MATÉRIELS ET LOGISTIQUES", 1, *_etat_piece(pieces, "MOYENS")),
    ]
