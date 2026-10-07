"""Indicateurs d'une personne sur une période : heures effectives, % prévu, arrivée/départ,
amplitude, occupation. Fonctions pures (règles du blueprint GI-SUIVI, section 7.4).

Entrée : des segments ACTIF (tout objet portant `debut` et `fin` ; ceux dont `etat` vaut
INACTIF sont écartés), en heure locale du bureau. Un segment qui chevauche minuit est coupé :
chaque jour reçoit sa part.

Les durées sont en secondes entières ; les pourcentages en `Decimal` à une décimale, ou None
quand ils n'ont pas de sens (rien de prévu, journée vide) — jamais de division par zéro.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

from .types import Etat

JOURS_OUVRES_PAR_SEMAINE = 5  # lundi à vendredi


@dataclass(frozen=True)
class Journee:
    jour: date
    effectif_s: int  # temps actif
    prevu_s: int  # 0 le week-end et les jours fériés
    arrivee: datetime | None  # début du premier segment actif du jour
    depart: datetime | None  # fin du dernier segment actif du jour
    amplitude_s: int  # départ − arrivée
    occupation_pct: Decimal | None  # effectif / amplitude
    prevu_pct: Decimal | None  # effectif / prévu


@dataclass(frozen=True)
class Synthese:
    debut: date
    fin: date
    effectif_s: int
    prevu_s: int
    prevu_pct: Decimal | None
    jours_travailles: int  # jours avec au moins une seconde active
    journees: tuple[Journee, ...]


def pourcentage(part: float, total: float) -> Decimal | None:
    if total <= 0:
        return None
    return (Decimal(str(part)) * 100 / Decimal(str(total))).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )


def prevu_du_jour(
    jour: date, heures_prevues_semaine: float, jours_feries: frozenset[date] = frozenset()
) -> int:
    """Secondes prévues : la semaine répartie sur les jours ouvrés ; rien le week-end ni férié."""
    if (
        jour.weekday() >= JOURS_OUVRES_PAR_SEMAINE
        or jour in jours_feries
        or heures_prevues_semaine <= 0
    ):
        return 0
    return round(heures_prevues_semaine * 3600 / JOURS_OUVRES_PAR_SEMAINE)


def _parts_par_jour(segments: Iterable) -> dict[date, list[tuple[datetime, datetime]]]:
    """Découpe chaque segment actif aux minuits ; rend les morceaux rangés par jour."""
    parts: dict[date, list[tuple[datetime, datetime]]] = {}
    for s in segments:
        if getattr(s, "etat", Etat.ACTIF) == Etat.INACTIF or s.fin <= s.debut:
            continue
        debut = s.debut
        while debut < s.fin:
            minuit = datetime.combine(
                debut.date() + timedelta(days=1), time.min, tzinfo=debut.tzinfo
            )
            fin = min(s.fin, minuit)
            parts.setdefault(debut.date(), []).append((debut, fin))
            debut = fin
    return parts


def journees(
    segments: Iterable,
    debut: date,
    fin: date,
    heures_prevues_semaine: float,
    jours_feries: frozenset[date] = frozenset(),
) -> list[Journee]:
    """Une `Journee` par jour de `debut` à `fin` inclus, jours vides compris."""
    parts = _parts_par_jour(segments)
    res: list[Journee] = []
    jour = debut
    while jour <= fin:
        morceaux = parts.get(jour, [])
        effectif = round(sum((f - d).total_seconds() for d, f in morceaux))
        prevu = prevu_du_jour(jour, heures_prevues_semaine, jours_feries)
        arrivee = min((d for d, _ in morceaux), default=None)
        depart = max((f for _, f in morceaux), default=None)
        amplitude = round((depart - arrivee).total_seconds()) if arrivee and depart else 0
        res.append(
            Journee(
                jour=jour,
                effectif_s=effectif,
                prevu_s=prevu,
                arrivee=arrivee,
                depart=depart,
                amplitude_s=amplitude,
                occupation_pct=pourcentage(effectif, amplitude),
                prevu_pct=pourcentage(effectif, prevu),
            )
        )
        jour += timedelta(days=1)
    return res


def synthese(
    segments: Iterable,
    debut: date,
    fin: date,
    heures_prevues_semaine: float,
    jours_feries: frozenset[date] = frozenset(),
) -> Synthese:
    js = journees(segments, debut, fin, heures_prevues_semaine, jours_feries)
    effectif = sum(j.effectif_s for j in js)
    prevu = sum(j.prevu_s for j in js)
    return Synthese(
        debut=debut,
        fin=fin,
        effectif_s=effectif,
        prevu_s=prevu,
        prevu_pct=pourcentage(effectif, prevu),
        jours_travailles=sum(1 for j in js if j.effectif_s > 0),
        journees=tuple(js),
    )
