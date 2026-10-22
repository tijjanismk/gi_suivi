"""Échéances des pièces administratives (ADR 0010, § 5), en Python pur.

- `date_de_fin` : la fin de validité proposée au dépôt d'une version (confirmée ou corrigée par
  la personne qui dépose : certains documents portent leur propre date).
- `etat` : l'état d'une version à une date (valide, à renouveler, expirée, manquante, permanente).
- `version_a_la_date` : la version qu'on joindrait à une date (la plus récente déjà émise).
- `controle` : pour un avis, l'état de chaque pièce exigée **à la date limite de dépôt**, jamais
  à la date du jour (§ 6).
"""

from __future__ import annotations

import calendar
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class Regle(StrEnum):
    APRES_EMISSION = "apres_emission"  # N mois après la date d'émission (non-faillite…)
    FIN_ANNEE = "fin_annee"  # 31/12 de l'année d'émission (patente)
    DATE_DU_DOCUMENT = "date_du_document"  # « valable du … au … » écrit sur la pièce
    REVUE_PERIODIQUE = "revue_periodique"  # document interne revu tous les N mois
    PERMANENTE = "permanente"  # NIF, statuts : pas d'échéance


class Etat(StrEnum):
    VALIDE = "valide"
    A_RENOUVELER = "a_renouveler"
    EXPIREE = "expiree"
    MANQUANTE = "manquante"
    PERMANENTE = "permanente"


# Ordre de gravité, pour trier « ce qui demande une action » en premier
GRAVITE = {
    Etat.EXPIREE: 0,
    Etat.MANQUANTE: 1,
    Etat.A_RENOUVELER: 2,
    Etat.VALIDE: 3,
    Etat.PERMANENTE: 4,
}


def ajouter_mois(jour: date, mois: int) -> date:
    """`jour` + `mois` mois civils ; le quantième ramené au dernier jour du mois s'il n'existe
    pas (30/11 + 3 mois = 28 ou 29/02)."""
    total = jour.year * 12 + (jour.month - 1) + mois
    annee, index = divmod(total, 12)
    dernier = calendar.monthrange(annee, index + 1)[1]
    return date(annee, index + 1, min(jour.day, dernier))


def date_de_fin(
    regle: Regle | str,
    date_emission: date,
    duree_mois: int | None = None,
    date_document: date | None = None,
) -> date | None:
    """Fin de validité proposée ; None = permanente, ou inconnue tant que la date écrite sur le
    document n'est pas saisie (règle « date du document » sans durée indicative).

    ValueError si la règle demande une durée qui manque."""
    regle = Regle(regle)
    if regle == Regle.PERMANENTE:
        return None
    if regle == Regle.FIN_ANNEE:
        return date(date_emission.year, 12, 31)
    if regle == Regle.DATE_DU_DOCUMENT:
        if date_document is not None:
            return date_document
        return ajouter_mois(date_emission, duree_mois) if duree_mois else None
    if not duree_mois:
        raise ValueError(f"la règle « {regle} » demande une durée en mois")
    return ajouter_mois(date_emission, duree_mois)


@dataclass(frozen=True)
class Version:
    """Ce que le moteur a besoin de savoir d'une version enregistrée."""

    date_emission: date
    valide_jusqu_au: date | None  # None = permanente
    ident: int | None = None  # clé de la ligne en base, rendue telle quelle


@dataclass(frozen=True)
class EtatPiece:
    etat: Etat
    jours: int | None = None  # jours restants (positif) ou de retard (négatif) ; None sans échéance

    @property
    def a_traiter(self) -> bool:
        return self.etat in (Etat.EXPIREE, Etat.MANQUANTE, Etat.A_RENOUVELER)


def etat(version: Version | None, date_reference: date, rappel_jours: int = 0) -> EtatPiece:
    """État d'une version à `date_reference`. Une pièce « valide jusqu'au 05/11 » l'est encore
    le 05/11 ; elle est expirée le 06/11. Une version émise après `date_reference` n'existait pas
    encore à cette date : la pièce est manquante."""
    if version is None or version.date_emission > date_reference:
        return EtatPiece(Etat.MANQUANTE)
    if version.valide_jusqu_au is None:
        return EtatPiece(Etat.PERMANENTE)
    reste = (version.valide_jusqu_au - date_reference).days
    if reste < 0:
        return EtatPiece(Etat.EXPIREE, reste)
    if rappel_jours and reste <= rappel_jours:
        return EtatPiece(Etat.A_RENOUVELER, reste)
    return EtatPiece(Etat.VALIDE, reste)


def version_a_la_date(versions: Iterable[Version], date_reference: date) -> Version | None:
    """La version qu'on aurait jointe à `date_reference` : la plus récemment émise parmi celles
    déjà émises à cette date (les versions retirées sont écartées par l'appelant)."""
    emises = [v for v in versions if v.date_emission <= date_reference]
    return max(emises, key=lambda v: v.date_emission, default=None)


@dataclass(frozen=True)
class LigneControle:
    code: str
    version: Version | None
    etat: EtatPiece


def controle(
    codes_exiges: Iterable[str],
    versions: Mapping[str, Iterable[Version]],
    date_limite: date,
) -> list[LigneControle]:
    """Pour un avis : chaque pièce exigée, avec la version qu'on joindrait et son état **à la
    date limite de dépôt** (pas de « à renouveler » à cette date : elle est valide ou non).
    Triées par gravité, puis dans l'ordre reçu."""
    lignes = []
    for code in codes_exiges:
        v = version_a_la_date(versions.get(code, ()), date_limite)
        lignes.append(LigneControle(code, v, etat(v, date_limite, rappel_jours=0)))
    ordre = {ligne.code: i for i, ligne in enumerate(lignes)}
    return sorted(lignes, key=lambda x: (GRAVITE[x.etat.etat], ordre[x.code]))
