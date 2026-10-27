"""Experts demandés par un avis (ADR 0013, AV06 ; ADR 0012), en Python pur.

Pour un poste des TDR (diplôme au moins, années d'expérience, nombre de références comparables,
spécialités acceptées), chaque expert du vivier est comparé au profil : ce qui manque est dit en
clair (« 8 ans pour 10 demandés »), et les experts qui répondent à tout viennent d'abord. Les
années se comptent depuis le début de carrière (ADR 0012 § 2), jamais saisies ; faute de début de
carrière, depuis le premier diplôme : c'est un plafond (« 8 ans au plus »), signalé comme tel.
Les références de l'expert sont les missions de ses affectations, comptées avec le filtre du poste.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from moteur.avis.filtres import Filtre, Reference, correspond
from moteur.references.doublons import mots

NIVEAUX = ("bac+2", "bac+3", "bac+4", "bac+5", "bac+8")


def rang_niveau(niveau: str) -> int:
    """« bac+5 » → 4 ; vide ou inconnu → 0 (aucun diplôme de ce niveau)."""
    return NIVEAUX.index(niveau) + 1 if niveau in NIVEAUX else 0


@dataclass(frozen=True)
class Profil:
    """Ce que le moteur sait d'un expert du vivier."""

    ident: int
    nom: str
    textes: str = ""  # spécialité, fonction et intitulés des diplômes, où chercher les mots
    niveau: str = ""  # le plus haut de ses diplômes
    debut_carriere: int | None = None
    annee_diplome: int | None = None  # le plus ancien de ses diplômes, si la carrière manque
    disponible: bool = True
    a_verifier: bool = False  # points en suspens sur sa fiche (ADR 0012 § 4)
    references: tuple[Reference, ...] = ()


@dataclass(frozen=True)
class Besoin:
    """Un poste demandé par l'avis."""

    poste: str
    niveau_min: str = ""
    annees_min: int = 0
    nb_references_min: int = 0
    specialites: tuple[str, ...] = ()
    filtre: Filtre = field(default_factory=Filtre)


@dataclass(frozen=True)
class Adequation:
    profil: Profil
    annees: int | None
    references: int  # références de l'expert qui passent le filtre du poste
    ecarts: tuple[str, ...]  # ce qui manque au profil, vide s'il répond à tout
    annees_estimees: bool = False  # comptées depuis le diplôme : début de carrière à saisir

    @property
    def complet(self) -> bool:
        return not self.ecarts


def evaluer(besoin: Besoin, profil: Profil, annee_reference: int) -> Adequation:
    ecarts = []
    if besoin.niveau_min and rang_niveau(profil.niveau) < rang_niveau(besoin.niveau_min):
        a = profil.niveau or "aucun diplôme enregistré"
        ecarts.append(f"diplôme {a}, {besoin.niveau_min} demandé")
    annees, estimees = None, False
    if profil.debut_carriere and profil.debut_carriere <= annee_reference:
        annees = annee_reference - profil.debut_carriere
    elif profil.annee_diplome and profil.annee_diplome <= annee_reference:
        annees, estimees = annee_reference - profil.annee_diplome, True
    if besoin.annees_min and (annees or 0) < besoin.annees_min:
        if annees is None:
            a = "début de carrière inconnu"
        else:
            a = f"{annees} an(s){' au plus, depuis le diplôme' if estimees else ''}"
        ecarts.append(f"{a} pour {besoin.annees_min} demandé(s)")
    nombre = sum(1 for r in profil.references if correspond(besoin.filtre, r))
    if nombre < besoin.nb_references_min:
        ecarts.append(f"{nombre} référence(s) pour {besoin.nb_references_min} demandée(s)")
    if besoin.specialites:
        mots_profil = mots(profil.textes)
        if not any(mots(s) and mots(s) <= mots_profil for s in besoin.specialites):
            ecarts.append("spécialité non trouvée : " + ", ".join(besoin.specialites))
    if not profil.disponible:
        ecarts.append("non disponible")
    return Adequation(profil, annees, nombre, tuple(ecarts), estimees)


def classer(besoin: Besoin, profils: Iterable[Profil], annee_reference: int) -> list[Adequation]:
    """Les experts du vivier pour ce poste : ceux qui répondent à tout d'abord, puis le moins
    d'écarts ; à égalité, le plus de références, le plus d'années, puis le nom."""
    resultats = [evaluer(besoin, p, annee_reference) for p in profils]
    return sorted(
        resultats,
        key=lambda x: (len(x.ecarts), -x.references, -(x.annees or 0), x.profil.nom),
    )
