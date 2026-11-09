"""Sommaire et plan du dossier de réponse à un AMI, en Python pur.

Modèle : la version électronique du dossier SOMAPEP (octobre 2026), reprise pour les deux AMI
PISEN du Niger (novembre 2026) et validée page par page par le porteur :

- A lettres : la lettre de manifestation d'intérêt ; en groupement seulement, l'accord de
  groupement et la procuration ; puis les adresses et contacts du consultant ;
- B pièces administratives du bureau, hors présentation et liste des moyens ;
- C présentation du bureau ;
- D expériences : D.1 l'expérience générale, toutes les références du bureau en une liste,
  même sans critère général ; D.2 les expériences spécifiques, un D.2.x par critère
  spécifique, son libellé tel quel, avec toutes les références qui y répondent, sans s'arrêter
  au nombre demandé (règle du porteur, 09/11/2026, comme dans SOMAPEP) ;
- E organigramme avec les experts clés ; F moyens matériels et logistiques.

Le sommaire imprimé montre les rubriques de premier niveau et celles de D ; chaque rubrique a son
intercalaire. L'application prépare la part du bureau seulement, même en groupement.

`plan` en tire le dossier page par page : ce que l'application rédige (couverture, sommaire,
intercalaires, lettre, adresse, listes, pages de famille, organigramme), ce qu'elle insère depuis
le partage (pièces administratives, pièces des références) et ce qui manque.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal
from enum import StrEnum

PIECES_A_PART = {"PRESENTATION": "présentation du bureau", "MOYENS": "liste des moyens"}
JUSTIFICATIFS = (
    ("garde", "page de garde"),
    ("signature", "page de signature"),
    ("attestation", "attestation"),
)
MOIS = (
    *("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août"),
    *("septembre", "octobre", "novembre", "décembre"),
)
# En-tête de la couverture, dans le style du pays du client ; un pays absent garde son seul nom.
PAYS = {
    "mali": ("RÉPUBLIQUE DU MALI", "Un Peuple – Un But – Une Foi"),
    "niger": ("RÉPUBLIQUE DU NIGER", "Fraternité – Travail – Progrès"),
    "senegal": ("RÉPUBLIQUE DU SÉNÉGAL", "Un Peuple – Un But – Une Foi"),
    "guinee": ("RÉPUBLIQUE DE GUINÉE", "Travail – Justice – Solidarité"),
    "cote d'ivoire": ("RÉPUBLIQUE DE CÔTE D'IVOIRE", "Union – Discipline – Travail"),
    "mauritanie": ("RÉPUBLIQUE ISLAMIQUE DE MAURITANIE", "Honneur – Fraternité – Justice"),
    "tchad": ("RÉPUBLIQUE DU TCHAD", "Unité – Travail – Progrès"),
    "cameroun": ("RÉPUBLIQUE DU CAMEROUN", "Paix – Travail – Patrie"),
    "burkina faso": ("BURKINA FASO", ""),
}
SANS_REFERENCE = "aucune référence ne répond (ou simulation à enregistrer)"
SANS_REGISTRE = "aucune référence au registre"
_GENERALE = re.compile(r"\bexperiences? generales?\b")
_SPECIFIQUE = re.compile(r"\bexperiences? specifiques?\b")


class Experience(StrEnum):
    """Où un critère range ses références dans le dossier."""

    GENERALE = "generale"  # dans la liste de D.1
    SPECIFIQUE = "specifique"  # un D.2.x à lui
    HORS = "hors"  # pas de liste (ancienneté, note sur la méthode…)


class Etat(StrEnum):
    """Ce qu'il faut pour une page du dossier."""

    REDIGEE = "redigee"  # l'application la compose
    A_INSERER = "a_inserer"  # un fichier du partage, à sa place
    PERIMEE = "perimee"  # la version jointe ne vaut plus à la date limite
    MANQUANTE = "manquante"


@dataclass(frozen=True)
class Bureau:
    raison_sociale: str = "GI-Conseils SARL"
    nom_court: str = "GI-Conseils"


BUREAU = Bureau()


@dataclass(frozen=True)
class Piece:
    """Une pièce administrative exigée par l'avis, à la date limite de dépôt."""

    code: str
    etat: str  # en mots, à la date limite de dépôt
    a_regler: bool
    libelle: str = ""  # le type de pièce, tel qu'on le lit
    chemin: str = ""  # la version jointe, relatif au partage ; vide : aucune version


@dataclass(frozen=True)
class Justificatif:
    type: str  # garde, signature, attestation…
    chemin: str  # relatif au partage


@dataclass(frozen=True)
class Reference:
    """Une référence retenue pour un critère, telle que les listes du bureau la montrent."""

    code: str
    titre: str
    client: str = ""
    pays: str = ""
    montant: Decimal | None = None
    devise: str = ""
    source: str = ""  # le bailleur
    annee: int | None = None
    debut: date | None = None
    fin: date | None = None
    justificatifs: tuple[Justificatif, ...] = ()


@dataclass(frozen=True)
class Critere:
    code: str
    libelle: str
    experience: str = ""  # une `Experience` ; vide : déduite (voir `classer`)
    mode: str = ""  # celui de `moteur.avis.notation.Mode`
    # Les références jointes au dossier : toutes celles qui répondent au critère, sauf celles
    # qu'une personne a exclues. None : sélection jamais enregistrée.
    retenues: tuple[Reference, ...] | None = None


@dataclass(frozen=True)
class Poste:
    poste: str
    expert: str = ""  # vide : aucun expert retenu


@dataclass(frozen=True)
class Rubrique:
    code: str  # « A », « A.1 », « D.2.1 »
    libelle: str  # tel qu'imprimé
    niveau: int  # 1 pour A à F
    etat: str = ""  # ce que l'application en sait, en mots ; vide si elle n'en sait rien
    a_regler: bool | None = None  # None : l'état informe sans juger
    au_sommaire: bool = True  # les lettres ont leur intercalaire, pas leur ligne au sommaire


@dataclass(frozen=True)
class Ligne:
    """Une ligne d'une liste de références : les sept colonnes des listes du bureau."""

    numero: int
    titre: str
    client: str
    pays: str
    montant: str
    source: str
    periode: str


@dataclass(frozen=True)
class Groupe:
    libelle: str  # le critère
    lignes: tuple[Ligne, ...]


@dataclass(frozen=True)
class Page:
    genre: str  # couverture, sommaire, intercalaire, lettre, adresse, liste, famille, fiche…
    rubrique: str = ""  # la rubrique où elle se range ; vide pour la couverture et le sommaire
    titre: str = ""
    etat: Etat = Etat.REDIGEE
    chemin: str = ""  # le fichier à insérer, relatif au partage
    motif: str = ""  # pourquoi elle manque
    reference: str = ""  # le code de la référence, pour sa fiche et ses pièces
    numero: int | None = None  # son numéro dans les listes du dossier
    paysage: bool = False
    entete: bool = False  # en-tête et pied du dossier : sommaire, intercalaires, organigramme
    groupes: tuple[Groupe, ...] = ()  # pour une liste


def _s(n: int) -> str:
    return "s" if n > 1 else ""


def _simple(texte: str) -> str:
    """En minuscules, sans accents ni espaces doubles : pour comparer des mots."""
    sans = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return " ".join(sans.lower().split())


def premiere_ligne(texte: str) -> str:
    return texte.strip().splitlines()[0].strip() if texte.strip() else ""


def pays(nom: str) -> tuple[str, str]:
    """Le nom officiel du pays, en capitales, et sa devise (vide si on ne la connaît pas)."""
    return PAYS.get(_simple(nom), (nom.strip().upper(), ""))


def mois_annee(jour: date) -> str:
    return f"{MOIS[jour.month - 1]} {jour.year}"


# -- les critères dans le dossier ------------------------------------------------------------
def _parent(code: str, codes: Iterable[str]) -> str | None:
    """Le critère dont celui-ci est un sous-critère (2.1 → 2), le plus proche."""
    parents = [c for c in codes if c != code and code.startswith(f"{c}.")]
    return max(parents, key=len, default=None)


def _dit(c: Critere) -> Experience | None:
    """Ce que le critère dit de lui-même : son champ, sinon « expérience(s) générale(s) » ou
    « spécifique(s) » dans son texte."""
    if c.experience in Experience:
        return Experience(c.experience)
    texte = _simple(c.libelle)
    if _SPECIFIQUE.search(texte):
        return Experience.SPECIFIQUE
    if _GENERALE.search(texte):
        return Experience.GENERALE
    return None


def classer(criteres: Iterable[Critere]) -> dict[str, Experience | None]:
    """La rubrique de chaque critère. Un critère qui a des sous-critères (2 pour 2.1, 2.2) est un
    titre de groupe (None) : il n'a pas de rubrique à lui. Sinon, dans l'ordre : son champ ; ses
    mots (« expériences spécifiques… ») ; ceux de son parent ; enfin son mode : des points par
    référence font une expérience spécifique, les autres modes restent hors des expériences."""
    criteres = list(criteres)
    par_code = {c.code: c for c in criteres}
    codes = list(par_code)
    rangs: dict[str, Experience | None] = {}
    for c in criteres:
        if any(autre.startswith(f"{c.code}.") for autre in codes):
            rangs[c.code] = None
            continue
        rang, parent = _dit(c), _parent(c.code, codes)
        while rang is None and parent is not None:
            rang, parent = _dit(par_code[parent]), _parent(parent, codes)
        if rang is None:
            rang = Experience.SPECIFIQUE if c.mode == "par_mission" else Experience.HORS
        rangs[c.code] = rang
    return rangs


def _par_rang(criteres: list[Critere]) -> tuple[list[Critere], list[Critere]]:
    rangs = classer(criteres)
    generaux = [c for c in criteres if rangs[c.code] == Experience.GENERALE]
    specifiques = [c for c in criteres if rangs[c.code] == Experience.SPECIFIQUE]
    return generaux, specifiques


# -- le sommaire -----------------------------------------------------------------------------
def _lettres(groupement: bool) -> list[tuple[str, str]]:
    """(genre de la page, libellé de l'intercalaire) des rubriques A.x."""
    lettres = [("lettre", "LETTRE DE MANIFESTATION D'INTÉRÊT")]
    if groupement:
        lettres.append(("accord", "ACCORD DE GROUPEMENT"))
        lettres.append(("procuration", "PROCURATION DE SIGNATURE"))
    lettres.append(("adresse", "ADRESSES ET CONTACTS DU CONSULTANT"))
    return lettres


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


def _etat_postes(postes: list[Poste]) -> tuple[str, bool | None]:
    if not postes:
        return "aucun poste saisi", None
    n, k = len(postes), sum(1 for p in postes if not p.expert)
    if k:
        return f"{k} poste{_s(k)} sur {n} sans expert retenu", True
    return f"{n} poste{_s(n)}, un expert retenu pour chacun", False


def _etat_retenues(c: Critere) -> tuple[str, bool | None]:
    if c.retenues is None:
        return "simulation non enregistrée", True
    n = len({r.code for r in c.retenues})
    if not n:
        return "aucune référence ne répond", True
    return f"{n} référence{_s(n)}", None


def _etat_generale(references: list[Reference]) -> tuple[str, bool | None]:
    n = len({r.code for r in references})
    if not n:
        return SANS_REGISTRE, True
    return f"{n} référence{_s(n)} du bureau", None


def sommaire(
    criteres: Iterable[Critere],
    groupement: bool = False,
    pieces: Iterable[Piece] = (),
    postes: Iterable[Poste] = (),
    bureau: Bureau = BUREAU,
    references: Iterable[Reference] = (),
) -> list[Rubrique]:
    """Les intercalaires dans l'ordre du dossier, avec ce que l'application sait de chacun.
    `references` : toutes les références du bureau, pour D.1."""
    criteres, postes = list(criteres), list(postes)
    pieces = {p.code: p for p in pieces}
    _, specifiques = _par_rang(criteres)
    b = [p for code, p in pieces.items() if code not in PIECES_A_PART]
    rubriques = [Rubrique("A", "LETTRES", 1)]
    for i, (_, libelle) in enumerate(_lettres(groupement), 1):
        rubriques.append(Rubrique(f"A.{i}", libelle, 2, au_sommaire=False))
    sans_bareme = "" if criteres else "aucun critère au barème"
    sans_specifique = "" if specifiques else "aucun critère d'expérience spécifique"
    etat_c, regler_c = _etat_piece(pieces, "PRESENTATION")
    rubriques += [
        Rubrique("B", f"PIÈCES ADMINISTRATIVES DE {bureau.raison_sociale}", 1, *_etat_pieces(b)),
        Rubrique("C", f"PRESENTATION DU BUREAU {bureau.nom_court}", 1, etat_c, regler_c),
        Rubrique("D", f"EXPÉRIENCES DU BUREAU {bureau.raison_sociale}", 1, sans_bareme),
        Rubrique("D.1", "EXPÉRIENCE GÉNÉRALE", 2, *_etat_generale(list(references))),
        Rubrique("D.2", "EXPÉRIENCES SPÉCIFIQUES", 2, sans_specifique),
    ]
    for i, c in enumerate(specifiques, 1):
        etat, a_regler = _etat_retenues(c)
        rubriques.append(Rubrique(f"D.2.{i}", premiere_ligne(c.libelle), 3, etat, a_regler))
    organigramme = "ORGANIGRAMME AVEC L'ENSEMBLE DES EXPERTS CLES"
    moyens = "MOYENS MATERIELS ET LOGISTIQUES"
    rubriques.append(Rubrique("E", organigramme, 1, *_etat_postes(postes)))
    rubriques.append(Rubrique("F", moyens, 1, *_etat_piece(pieces, "MOYENS")))
    return rubriques


# -- le plan, page par page ------------------------------------------------------------------
def _montant(r: Reference) -> str:
    if r.montant is None:
        return ""
    entier, reste = divmod(r.montant, 1)
    texte = f"{int(entier):,}".replace(",", " ")
    if reste:
        texte += f",{int(reste * 100):02d}"
    devise = "F CFA" if r.devise.replace(" ", "").upper() == "FCFA" else r.devise
    return f"{texte} {devise}".strip()


def _periode(r: Reference) -> str:
    if r.debut and r.fin:
        return f"{mois_annee(r.debut)} – {mois_annee(r.fin)}"
    if r.debut:
        return f"depuis {mois_annee(r.debut)}"
    if r.fin:
        return f"jusqu'en {mois_annee(r.fin)}"
    return str(r.annee) if r.annee else ""


def ligne(r: Reference, numero: int) -> Ligne:
    return Ligne(numero, r.titre, r.client, r.pays, _montant(r), r.source, _periode(r))


def numeroter(criteres: Iterable[Critere]) -> dict[str, int]:
    """Le numéro de chaque référence dans les listes et sur sa fiche : critère après critère,
    les plus récentes d'abord ; une référence garde son premier numéro dans tout le dossier."""
    numeros: dict[str, int] = {}
    for c in criteres:
        for r in sorted(c.retenues or (), key=lambda r: -(r.annee or 0)):
            numeros.setdefault(r.code, len(numeros) + 1)
    return numeros


def _retenues(c: Critere, numeros: dict[str, int]) -> list[Reference]:
    """Les références retenues du critère, sans doublon, dans l'ordre de leur numéro."""
    uniques = {r.code: r for r in c.retenues or ()}
    return sorted(uniques.values(), key=lambda r: numeros[r.code])


def _page_piece(rubrique: str, p: Piece) -> Page:
    titre = p.libelle or p.code
    if not p.chemin:
        return Page("piece", rubrique, titre, Etat.MANQUANTE, motif=p.etat or "aucune version")
    if p.a_regler:
        return Page("piece", rubrique, titre, Etat.PERIMEE, p.chemin, motif=p.etat)
    return Page("piece", rubrique, titre, Etat.A_INSERER, p.chemin)


def _page_a_part(rubrique: str, pieces: dict[str, Piece], code: str) -> Page:
    if code in pieces:
        return _page_piece(rubrique, pieces[code])
    nom = PIECES_A_PART[code]
    motif = f"{nom} non cochée dans les pièces exigées"
    return Page("piece", rubrique, nom[0].upper() + nom[1:], Etat.MANQUANTE, motif=motif)


def _pages_reference(rubrique: str, r: Reference, numero: int) -> list[Page]:
    """La fiche, puis la garde, la signature et l'attestation de la référence."""
    fiche = Page(
        "fiche",
        rubrique,
        f"Fiche de la référence n° {numero:02d} · {r.code}",
        Etat.MANQUANTE,
        motif="fiche au format Banque mondiale pas encore au registre",
    )
    pages = [fiche]
    for type_, nom in JUSTIFICATIFS:
        j = next((j for j in r.justificatifs if j.type == type_), None)
        titre = f"{nom[0].upper()}{nom[1:]} · {r.code}"
        if j is None:
            page = Page("piece", rubrique, titre, Etat.MANQUANTE, motif=f"{nom} absente")
        else:
            page = Page("piece", rubrique, titre, Etat.A_INSERER, j.chemin)
        pages.append(page)
    return [replace(p, reference=r.code, numero=numero) for p in pages]


def _references(rubrique: str, c: Critere, numeros: dict[str, int]) -> list[Page]:
    """La page de famille du critère, puis les pages de ses références."""
    retenues = _retenues(c, numeros)
    if not retenues:
        return []
    pages = [Page("famille", rubrique, premiere_ligne(c.libelle).upper())]
    for r in retenues:
        pages += _pages_reference(rubrique, r, numeros[r.code])
    return pages


def _groupe(c: Critere, numeros: dict[str, int]) -> Groupe:
    lignes = tuple(ligne(r, numeros[r.code]) for r in _retenues(c, numeros))
    return Groupe(premiere_ligne(c.libelle), lignes)


def _liste(rubrique: str, titre: str, groupes: list[Groupe]) -> Page:
    return Page("liste", rubrique, titre, paysage=True, groupes=tuple(groupes))


def _manque(rubrique: str, titre: str, motif: str) -> Page:
    return Page("vide", rubrique, titre, Etat.MANQUANTE, motif=motif)


def _toutes(references: list[Reference]) -> Critere:
    """D.1 vu comme un critère qui retient toutes les références du bureau, sans libellé."""
    return Critere("D.1", "", Experience.GENERALE, retenues=tuple(references))


def _experience_generale(references: list[Reference], numeros: dict[str, int]) -> list[Page]:
    """Toutes les références du bureau en une seule liste, puis la fiche et les pièces de
    chacune, sans page de famille : l'intercalaire D.1 la précède."""
    if not references:
        return [_manque("D.1", "Expérience générale", SANS_REGISTRE)]
    tout = _toutes(references)
    pages = [_liste("D.1", "LISTE DES EXPERIENCES GÉNÉRALES", [_groupe(tout, numeros)])]
    for r in _retenues(tout, numeros):
        pages += _pages_reference("D.1", r, numeros[r.code])
    return pages


def _experience_specifique(code: str, c: Critere, numeros: dict[str, int]) -> list[Page]:
    """Comme dans SOMAPEP, chaque rubrique spécifique reprend ses propres fiches."""
    if not c.retenues:
        return [_manque(code, premiere_ligne(c.libelle), SANS_REFERENCE)]
    liste = _liste(code, "LISTE DES EXPERIENCES SPECIFIQUES", [_groupe(c, numeros)])
    return [liste, *_references(code, c, numeros)]


def _contenu_lettres(groupement: bool) -> dict[str, list[Page]]:
    contenus = {}
    for i, (genre, libelle) in enumerate(_lettres(groupement), 1):
        code, titre = f"A.{i}", libelle.capitalize()
        if genre in ("lettre", "adresse"):
            contenus[code] = [Page(genre, code, titre)]
        else:  # l'accord et la procuration : signés hors de l'application
            motif = "à joindre, signée par les membres du groupement"
            contenus[code] = [Page("piece", code, titre, Etat.MANQUANTE, motif=motif)]
    return contenus


def plan(
    criteres: Iterable[Critere],
    groupement: bool = False,
    pieces: Iterable[Piece] = (),
    postes: Iterable[Poste] = (),
    bureau: Bureau = BUREAU,
    references: Iterable[Reference] = (),
) -> list[Page]:
    """Le dossier page par page : couverture, sommaire, puis chaque intercalaire suivi de ses
    pages. `pieces` dans l'ordre où le dossier les joint ; `references` : toutes les références
    du bureau, pour D.1. Aucune fiche de référence n'est encore au registre : elles sont toutes
    « manquantes » jusqu'à ce qu'elles y entrent."""
    criteres, pieces, postes = list(criteres), list(pieces), list(postes)
    references = list(references)
    rubriques = sommaire(criteres, groupement, pieces, postes, bureau, references)
    _, specifiques = _par_rang(criteres)
    numeros = numeroter([_toutes(references), *specifiques])
    par_code = {p.code: p for p in pieces}
    administratives = [_page_piece("B", p) for p in pieces if p.code not in PIECES_A_PART]
    if not administratives:
        administratives = [_manque("B", "Pièces administratives", "aucune pièce exigée")]
    organigramme = Page("organigramme", "E", "Organigramme", paysage=True, entete=True)
    contenus = {
        **_contenu_lettres(groupement),
        "B": administratives,
        "C": [_page_a_part("C", par_code, "PRESENTATION")],
        "D.1": _experience_generale(references, numeros),
        "E": [organigramme],
        "F": [_page_a_part("F", par_code, "MOYENS")],
    }
    for i, c in enumerate(specifiques, 1):
        contenus[f"D.2.{i}"] = _experience_specifique(f"D.2.{i}", c, numeros)
    pages = [Page("couverture"), Page("sommaire", entete=True)]
    for r in rubriques:
        pages.append(Page("intercalaire", r.code, r.libelle, entete=True))
        pages += contenus.get(r.code, [])
    return pages
