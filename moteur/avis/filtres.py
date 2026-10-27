"""Filtre d'un critère du barème (ADR 0013, § 3), en Python pur.

Le champ `Critere.filtre` est un objet JSON dont toutes les clés sont optionnelles : les
conditions se cumulent (ET) ; dans une liste, une seule valeur suffit (OU). Format complet dans
`docs/schema-donnees.md` ; il n'est interprété qu'ici.

- `lire_filtre` : le JSON vérifié ; une clé inconnue ou un mauvais type lève `FiltreInvalideError`,
  avec un message pour l'écran de saisie.
- `correspond` : la référence répond-elle au filtre ?
- `mots_cles_trouves` : combien de mots-clés du filtre sont dans son intitulé (pour classer).
- `preuve` : prouvée, à auditer ou manquante, d'après les pièces requises par le critère.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from moteur.references.doublons import mots, normaliser

NATURES = frozenset({"ETU", "CTR", "ETC"})
ROLES = frozenset({"seul", "chef_de_file", "membre"})
# Types et natures exactes des justificatifs (ADR 0011, `references.PieceJustificative`)
TYPES_PIECE = frozenset(
    {
        "garde",
        "signature",
        "attestation",
        "deuxieme_page",  # exceptionnelle, quand l'avis la demande (ADR 0015)
        "contrat_complet",
        "avenant",
        "autre",
    }
)
NATURES_PIECE = frozenset(
    {
        "garde_contrat",
        "garde_avenant",
        "bonne_execution",
        "bonne_fin",
        "services_faits",
        "pv_reception",
        "autre",
    }
)
# Une référence complète : une garde, une signature, une attestation (ADR 0011)
PIECES_PAR_DEFAUT = (frozenset({"garde"}), frozenset({"signature"}), frozenset({"attestation"}))

CLES = frozenset(
    {
        "natures",
        "domaines",
        "categories",
        "types_ouvrage",
        "familles_ouvrage",
        "roles",
        "pays",
        "clients",
        "bailleurs",
        "localites",
        "mots_cles",
        "quantites_min",
        "annee_min",
        "annee_max",
        "pieces_requises",
        "pieces_completes_requises",
    }
)


class FiltreInvalideError(ValueError):
    """Le filtre ne se lit pas ; le message dit pourquoi, en français."""


class Preuve(StrEnum):
    PROUVEE = "prouvee"  # pièce auditée, lisible et cohérente
    A_AUDITER = "a_auditer"  # pièce rattachée, pas encore auditée
    MANQUANTE = "manquante"  # pas de pièce, ou une pièce auditée et mauvaise


# Ordre de classement : ce qui compte déjà d'abord
ORDRE_PREUVE = {Preuve.PROUVEE: 0, Preuve.A_AUDITER: 1, Preuve.MANQUANTE: 2}


@dataclass(frozen=True)
class Piece:
    """Un justificatif rattaché à la référence (ADR 0011)."""

    type: str  # garde, signature, attestation…
    nature: str = ""  # nature exacte : bonne_fin, pv_reception…
    auditee: bool = False
    bonne: bool = False  # lisible (oui ou moyen) et cohérente : elle compte


@dataclass(frozen=True)
class Reference:
    """Ce que le moteur a besoin de savoir d'une référence (`references.Mission`)."""

    ident: int
    code: str
    intitule: str  # intitulé et intitulé court, où l'on cherche les mots-clés
    nature: str = ""  # ETU, CTR, ETC
    domaines: frozenset[str] = frozenset()  # principal et secondaires : HYD, AEP…
    role: str = "seul"
    annee: int | None = None
    pays: str = ""
    clients: frozenset[str] = frozenset()  # nom et sigle du client
    bailleurs: frozenset[str] = frozenset()  # nom et sigle du bailleur
    categorie: str = ""
    types_ouvrage: frozenset[str] = frozenset()  # clés du thésaurus
    familles_ouvrage: frozenset[str] = frozenset()  # familles de ses types d'ouvrage
    localites: frozenset[str] = frozenset()  # ses localités et leurs ascendants
    quantites: Mapping[str, Decimal] = field(default_factory=dict)
    pieces: tuple[Piece, ...] = ()
    absorbee: bool = False  # doublon absorbé par un autre code (ADR 0008)


@dataclass(frozen=True)
class Filtre:
    """Le filtre lu ; les textes libres (pays, clients, familles…) sont normalisés."""

    natures: frozenset[str] = frozenset()
    domaines: frozenset[str] = frozenset()
    categories: frozenset[str] = frozenset()
    types_ouvrage: frozenset[str] = frozenset()
    familles_ouvrage: frozenset[str] = frozenset()
    roles: frozenset[str] = frozenset()
    pays: frozenset[str] = frozenset()
    clients: frozenset[str] = frozenset()
    bailleurs: frozenset[str] = frozenset()
    localites: frozenset[str] = frozenset()
    mots_cles: tuple[frozenset[str], ...] = ()  # un mot-clé = l'ensemble de ses mots
    quantites_min: Mapping[str, Decimal] = field(default_factory=dict)
    annee_min: int | None = None
    annee_max: int | None = None
    pieces_requises: tuple[frozenset[str], ...] = PIECES_PAR_DEFAUT
    pieces_completes_requises: bool = True


@dataclass(frozen=True)
class Manque:
    """Une pièce requise qui ne prouve pas encore la référence."""

    exigence: str  # « attestation », « bonne_fin|pv_reception »…
    etat: Preuve


def _liste(donnees: Mapping, cle: str) -> list[str]:
    valeur = donnees.get(cle)
    if valeur is None:
        return []
    if not isinstance(valeur, list) or not all(isinstance(v, str) and v.strip() for v in valeur):
        raise FiltreInvalideError(f"« {cle} » doit être une liste de textes non vides")
    return [v.strip() for v in valeur]


def _annee(donnees: Mapping, cle: str) -> int | None:
    valeur = donnees.get(cle)
    if valeur is None:
        return None
    if isinstance(valeur, bool) or not isinstance(valeur, int) or not 1900 <= valeur <= 2100:
        raise FiltreInvalideError(f"« {cle} » doit être une année (par exemple 2016)")
    return valeur


def _quantites(donnees: Mapping) -> dict[str, Decimal]:
    valeur = donnees.get("quantites_min")
    if valeur is None:
        return {}
    if not isinstance(valeur, Mapping):
        raise FiltreInvalideError(
            "« quantites_min » doit associer un type de quantité à un minimum"
        )
    quantites = {}
    for cle, minimum in valeur.items():
        nombre = None
        if isinstance(minimum, int | float | str) and not isinstance(minimum, bool):
            try:
                nombre = Decimal(str(minimum))
            except InvalidOperation:
                nombre = None
        if nombre is None or not nombre.is_finite() or nombre < 0:
            raise FiltreInvalideError(
                f"« quantites_min » : le minimum de {cle} doit être un nombre"
            )
        quantites[str(cle)] = nombre
    return quantites


def _pieces_requises(donnees: Mapping) -> tuple[frozenset[str], ...]:
    if "pieces_requises" not in donnees:
        return PIECES_PAR_DEFAUT
    exigences = _liste(donnees, "pieces_requises")
    if not exigences:
        raise FiltreInvalideError(
            "« pieces_requises » ne peut pas être vide : mettre "
            "« pieces_completes_requises » à false si l'avis ne demande pas de justificatif"
        )
    lues = []
    for exigence in exigences:
        variantes = frozenset(v.strip() for v in exigence.split("|") if v.strip())
        inconnues = sorted(variantes - TYPES_PIECE - NATURES_PIECE)
        if not variantes or inconnues:
            raise FiltreInvalideError(
                f"« pieces_requises » : pièce inconnue ({', '.join(inconnues) or exigence})"
            )
        lues.append(variantes)
    return tuple(lues)


def lire_filtre(donnees: Mapping | None) -> Filtre:
    """Le filtre JSON d'un critère, vérifié. Vide ou absent : toutes les références, avec les
    trois pièces requises par défaut."""
    if donnees is None:
        return Filtre()
    if not isinstance(donnees, Mapping):
        raise FiltreInvalideError("le filtre doit être un objet JSON")
    inconnues = sorted(set(donnees) - CLES)
    if inconnues:
        raise FiltreInvalideError(f"clé inconnue : {', '.join(inconnues)}")

    natures = frozenset(v.upper() for v in _liste(donnees, "natures"))
    if natures - NATURES:
        raise FiltreInvalideError(f"« natures » : {', '.join(sorted(natures - NATURES))} inconnue")
    roles = frozenset(_liste(donnees, "roles"))
    if roles - ROLES:
        raise FiltreInvalideError(f"« roles » : {', '.join(sorted(roles - ROLES))} inconnu")
    mots_cles = []
    for mot_cle in _liste(donnees, "mots_cles"):
        if not mots(mot_cle):
            raise FiltreInvalideError(f"« mots_cles » : « {mot_cle} » ne contient aucun mot utile")
        mots_cles.append(mots(mot_cle))
    annee_min, annee_max = _annee(donnees, "annee_min"), _annee(donnees, "annee_max")
    if annee_min and annee_max and annee_min > annee_max:
        raise FiltreInvalideError("« annee_min » est après « annee_max »")
    completes = donnees.get("pieces_completes_requises", True)
    if not isinstance(completes, bool):
        raise FiltreInvalideError("« pieces_completes_requises » vaut true ou false")

    return Filtre(
        natures=natures,
        domaines=frozenset(v.upper() for v in _liste(donnees, "domaines")),
        categories=frozenset(_liste(donnees, "categories")),
        types_ouvrage=frozenset(_liste(donnees, "types_ouvrage")),
        familles_ouvrage=frozenset(normaliser(v) for v in _liste(donnees, "familles_ouvrage")),
        roles=roles,
        pays=frozenset(normaliser(v) for v in _liste(donnees, "pays")),
        clients=frozenset(normaliser(v) for v in _liste(donnees, "clients")),
        bailleurs=frozenset(normaliser(v) for v in _liste(donnees, "bailleurs")),
        localites=frozenset(normaliser(v) for v in _liste(donnees, "localites")),
        mots_cles=tuple(mots_cles),
        quantites_min=_quantites(donnees),
        annee_min=annee_min,
        annee_max=annee_max,
        pieces_requises=_pieces_requises(donnees),
        pieces_completes_requises=completes,
    )


def _normalises(textes: frozenset[str]) -> frozenset[str]:
    return frozenset(normaliser(t) for t in textes)


def mots_cles_trouves(filtre: Filtre, reference: Reference) -> int:
    """Nombre de mots-clés présents dans l'intitulé ; un mot-clé de plusieurs mots les demande
    tous (« génie civil »). Casse, accents et pluriels ignorés."""
    mots_intitule = mots(reference.intitule)
    return sum(1 for mot_cle in filtre.mots_cles if mot_cle <= mots_intitule)


def correspond(filtre: Filtre, reference: Reference) -> bool:
    """La référence répond-elle au filtre ? Une année inconnue ne passe pas une borne d'année ;
    types d'ouvrage et familles ne font qu'une condition (l'un des types ou l'une des
    familles), comme la recherche par le thésaurus."""
    f, r = filtre, reference
    if f.natures and r.nature not in f.natures:
        return False
    if f.domaines and not r.domaines & f.domaines:
        return False
    if f.categories and r.categorie not in f.categories:
        return False
    if f.roles and r.role not in f.roles:
        return False
    if f.types_ouvrage or f.familles_ouvrage:
        par_type = bool(r.types_ouvrage & f.types_ouvrage)
        if not par_type and not _normalises(r.familles_ouvrage) & f.familles_ouvrage:
            return False
    if f.pays and normaliser(r.pays) not in f.pays:
        return False
    if f.clients and not _normalises(r.clients) & f.clients:
        return False
    if f.bailleurs and not _normalises(r.bailleurs) & f.bailleurs:
        return False
    if f.localites and not _normalises(r.localites) & f.localites:
        return False
    if f.annee_min is not None and (r.annee is None or r.annee < f.annee_min):
        return False
    if f.annee_max is not None and (r.annee is None or r.annee > f.annee_max):
        return False
    for cle, minimum in f.quantites_min.items():
        valeur = r.quantites.get(cle)
        if valeur is None or valeur < minimum:
            return False
    return not f.mots_cles or mots_cles_trouves(f, r) > 0


def _etat(variantes: frozenset[str], pieces: tuple[Piece, ...]) -> Preuve:
    candidates = [p for p in pieces if p.type in variantes or p.nature in variantes]
    if any(p.bonne for p in candidates):
        return Preuve.PROUVEE
    if any(not p.auditee for p in candidates):
        return Preuve.A_AUDITER
    return Preuve.MANQUANTE


def preuve(filtre: Filtre, reference: Reference) -> tuple[Preuve, tuple[Manque, ...]]:
    """L'état de la preuve de la référence pour ce critère (le pire de ses pièces requises), et
    les pièces qui ne la prouvent pas encore. Une pièce auditée mauvaise ne prouve rien."""
    manques = []
    for variantes in filtre.pieces_requises:
        etat = _etat(variantes, reference.pieces)
        if etat != Preuve.PROUVEE:
            manques.append(Manque("|".join(sorted(variantes)), etat))
    if not manques:
        return Preuve.PROUVEE, ()
    pire = max((m.etat for m in manques), key=ORDRE_PREUVE.__getitem__)
    return pire, tuple(manques)
