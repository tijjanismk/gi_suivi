"""Note d'un avis (ADR 0013, § 3), en Python pur.

Les quatre modes de calcul d'un critère (`docs/schema-donnees.md`) :

- `par_mission` : des points par référence retenue, jusqu'au plafond ;
- `anciennete` : le socle si les années d'expérience atteignent le seuil, plus des points par
  année au-delà, plafonnés ; les années vont de la plus ancienne référence retenue à l'année de
  la date limite ;
- `forfait` : le plafond si le filtre retient assez de références, sinon 0 ;
- `manuel` : la note saisie, plafonnée.

Deux notes : la note sûre ne compte que les références prouvées (pièces auditées et bonnes) ; la
note possible compte aussi celles dont les pièces sont à auditer. Verdict au seuil : éligible si
la note sûre l'atteint, non éligible si la note possible ne l'atteint pas, incertain entre les
deux. Les pièces en jeu disent ce que chaque référence pas encore prouvée ajouterait à la note
sûre ; on les traite dans l'ordre des points.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from decimal import ROUND_CEILING, Decimal
from enum import StrEnum

from moteur.avis.filtres import Filtre, Manque, Preuve, Reference
from moteur.avis.selection import Candidate, selectionner

CENTIEME = Decimal("0.01")


class Mode(StrEnum):
    PAR_MISSION = "par_mission"
    ANCIENNETE = "anciennete"
    FORFAIT = "forfait"
    MANUEL = "manuel"


class Verdict(StrEnum):
    ELIGIBLE = "eligible"
    INCERTAIN = "incertain"
    NON_ELIGIBLE = "non_eligible"


@dataclass(frozen=True)
class Critere:
    """Une ligne du barème (`avis.Critere`)."""

    code: str  # E.1, 2.1…
    mode: Mode | str
    plafond: Decimal | None = None  # sans plafond : par mission et ancienneté seulement
    points_par_mission: Decimal = Decimal(0)
    nb_min_missions: int = 0
    annees_seuil: int = 0
    points_socle: Decimal = Decimal(0)
    points_par_annee: Decimal = Decimal(0)
    note_manuelle: Decimal | None = None
    filtre: Filtre = field(default_factory=Filtre)


@dataclass(frozen=True)
class PieceEnJeu:
    """Ce que rapporterait à la note sûre une référence pas encore prouvée."""

    critere: str
    code: str  # code de la référence
    preuve: Preuve
    manques: tuple[Manque, ...]
    points: Decimal


@dataclass
class ResultatCritere:
    critere: Critere
    candidates: list[Candidate] = field(default_factory=list)
    retenues: list[Candidate] = field(default_factory=list)  # celles qui portent les points
    note_sure: Decimal = Decimal(0)
    note_possible: Decimal = Decimal(0)
    en_jeu: list[PieceEnJeu] = field(default_factory=list)
    alertes: list[str] = field(default_factory=list)


@dataclass
class Resultat:
    criteres: list[ResultatCritere]
    note_sure: Decimal
    note_possible: Decimal
    seuil: Decimal | None
    verdict: Verdict | None  # sans seuil, pas de verdict
    en_jeu: list[PieceEnJeu]  # tous critères, les plus gros points d'abord


def _plafonner(points: Decimal, plafond: Decimal | None) -> Decimal:
    return points if plafond is None else min(points, plafond)


def _piece(critere: Critere, candidate: Candidate, points: Decimal) -> PieceEnJeu:
    return PieceEnJeu(
        critere.code, candidate.reference.code, candidate.preuve, candidate.manques, points
    )


def _par_mission(res: ResultatCritere) -> None:
    c = res.critere
    sures = [x for x in res.candidates if x.sure]
    possibles = [x for x in res.candidates if x.possible]

    def note(n: int) -> Decimal:
        return _plafonner(c.points_par_mission * n, c.plafond)

    res.note_sure, res.note_possible = note(len(sures)), note(len(possibles))
    utiles = len(possibles)
    if c.plafond is not None and c.points_par_mission > 0:
        parts = c.plafond / c.points_par_mission
        utiles = int(parts.to_integral_value(rounding=ROUND_CEILING))
    res.retenues = possibles[:utiles]
    # Chaque référence pas encore prouvée, dans l'ordre : ce qu'elle ajouterait à la note sûre
    n = len(sures)
    for x in res.candidates:
        if x.sure:
            continue
        gain = note(n + 1) - note(n)
        if gain <= 0:
            break
        res.en_jeu.append(_piece(c, x, gain))
        n += 1
    if c.points_par_mission <= 0:
        res.alertes.append("points par référence à saisir")
    if len(sures) < c.nb_min_missions:
        res.alertes.append(
            f"{len(sures)} référence(s) prouvée(s) et {len(possibles)} possible(s) "
            f"pour {c.nb_min_missions} demandée(s)"
        )


def _plus_ancienne(candidates: list[Candidate]) -> Candidate | None:
    datees = [x for x in candidates if x.reference.annee is not None]
    return min(datees, key=lambda x: x.reference.annee, default=None)


def _anciennete(res: ResultatCritere, annee_reference: int) -> None:
    c = res.critere

    def note(candidate: Candidate | None) -> Decimal:
        if candidate is None:
            return Decimal(0)
        annees = annee_reference - candidate.reference.annee
        if annees < c.annees_seuil:
            return Decimal(0)
        points = c.points_socle + c.points_par_annee * (annees - c.annees_seuil)
        return _plafonner(points, c.plafond)

    sure = _plus_ancienne([x for x in res.candidates if x.sure])
    possible = _plus_ancienne([x for x in res.candidates if x.possible])
    res.note_sure, res.note_possible = note(sure), note(possible)
    res.retenues = [sure] if sure else []
    if possible is not None and possible is not sure:
        res.retenues.append(possible)
    autre = _plus_ancienne([x for x in res.candidates if not x.sure])
    if autre is not None and note(autre) > res.note_sure:
        res.en_jeu.append(_piece(c, autre, note(autre) - res.note_sure))
    if res.note_sure == 0:
        if sure is None:
            res.alertes.append("aucune référence prouvée et datée")
        else:
            annees = annee_reference - sure.reference.annee
            res.alertes.append(f"{annees} an(s) prouvé(s) pour {c.annees_seuil} demandé(s)")


def _forfait(res: ResultatCritere) -> None:
    c = res.critere
    minimum = max(c.nb_min_missions, 1)
    forfait = c.plafond or Decimal(0)
    sures = [x for x in res.candidates if x.sure]
    possibles = [x for x in res.candidates if x.possible]
    res.note_sure = forfait if len(sures) >= minimum else Decimal(0)
    res.note_possible = forfait if len(possibles) >= minimum else Decimal(0)
    res.retenues = possibles[:minimum]
    if c.plafond is None:
        res.alertes.append("points du forfait à saisir (plafond)")
    if len(sures) < minimum:
        res.alertes.append(f"{len(sures)} référence(s) prouvée(s) pour {minimum} demandée(s)")
        # Le forfait se partage entre les références qui manquent, s'il y en a assez
        manquent = minimum - len(sures)
        a_prouver = [x for x in res.candidates if not x.sure][:manquent]
        if forfait > 0 and len(a_prouver) == manquent:
            part = (forfait / manquent).quantize(CENTIEME)
            res.en_jeu.extend(_piece(c, x, part) for x in a_prouver)


def _manuel(res: ResultatCritere) -> None:
    c = res.critere
    if c.note_manuelle is None:
        res.alertes.append("note à saisir à la main")
        return
    note = _plafonner(c.note_manuelle, c.plafond)
    if note < c.note_manuelle:
        res.alertes.append(f"note saisie au-dessus du plafond, ramenée à {note}")
    res.note_sure = res.note_possible = note


def noter_critere(
    critere: Critere,
    references: Iterable[Reference],
    annee_reference: int,
    choix: Mapping[int, bool] | None = None,
) -> ResultatCritere:
    """Le résultat d'un critère : références éligibles, retenues, deux notes, pièces en jeu.
    `annee_reference` : l'année de la date limite de dépôt (ancienneté)."""
    mode = Mode(critere.mode)
    res = ResultatCritere(critere)
    if mode != Mode.MANUEL:
        res.candidates = selectionner(critere.filtre, references, choix)
    if mode == Mode.PAR_MISSION:
        _par_mission(res)
    elif mode == Mode.ANCIENNETE:
        _anciennete(res, annee_reference)
    elif mode == Mode.FORFAIT:
        _forfait(res)
    else:
        _manuel(res)
    return res


def noter(
    criteres: Iterable[Critere],
    references: Iterable[Reference],
    annee_reference: int,
    seuil: Decimal | None = None,
    choix: Mapping[str, Mapping[int, bool]] | None = None,
) -> Resultat:
    """La note simulée d'un avis et son verdict au seuil. `choix` : par code de critère, les
    références forcées ou exclues par une personne (`selection.selectionner`)."""
    refs = list(references)
    choix = choix or {}
    resultats = [noter_critere(c, refs, annee_reference, choix.get(c.code)) for c in criteres]
    note_sure = sum((r.note_sure for r in resultats), Decimal(0))
    note_possible = sum((r.note_possible for r in resultats), Decimal(0))
    verdict = None
    if seuil is not None:
        if note_sure >= seuil:
            verdict = Verdict.ELIGIBLE
        elif note_possible < seuil:
            verdict = Verdict.NON_ELIGIBLE
        else:
            verdict = Verdict.INCERTAIN
    en_jeu = [p for r in resultats for p in r.en_jeu]
    en_jeu.sort(key=lambda p: (-p.points, p.critere, p.code))
    return Resultat(resultats, note_sure, note_possible, seuil, verdict, en_jeu)
