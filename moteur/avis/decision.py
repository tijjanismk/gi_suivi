"""Décision « on répond ou pas » d'un avis (ADR 0021 et 0022, ISO 9001 § 8.2.3), en Python pur.

Une décision porte un motif, se prend avant le dépôt et ne répète pas la décision en cours. Le
statut d'un avis ne passe à « on répond » ou « on ne répond pas » que par elle : le formulaire de
l'avis le refuse. Seules la direction et sa délégation décident ; la qualité de l'auteur est
gardée avec la décision. Les messages sont ceux que l'écran affiche.
"""

from __future__ import annotations

GO, NO_GO = "go", "no_go"
DECISIONS = (GO, NO_GO)
# Statuts depuis lesquels on décide : avant le dépôt, ou pour revoir une décision prise.
AVANT_DEPOT = ("recu", "en_analyse", GO, NO_GO)
DIRECTION, DELEGATION = "direction", "delegation"
MOTIF_MAX = 2000


class DecisionInvalideError(ValueError):
    """Une décision refusée ; le message est pour la personne qui décide."""


def controler(decision: str, motif: str, statut: str) -> str:
    """Le motif nettoyé, si la décision peut être prise sur un avis à ce statut ; sinon
    `DecisionInvalideError`."""
    if decision not in DECISIONS:
        raise DecisionInvalideError("Choisissez « on répond » ou « on ne répond pas ».")
    if statut not in AVANT_DEPOT:
        raise DecisionInvalideError(
            "La décision se prend avant le dépôt : cet avis n'est plus reçu ni en analyse."
        )
    if decision == statut:
        raise DecisionInvalideError(
            "C'est déjà la décision en cours : pour la revoir, choisissez l'autre."
        )
    motif = motif.strip()
    if not any(c.isalnum() for c in motif):
        raise DecisionInvalideError("Indiquez pourquoi vous décidez de répondre ou non.")
    if len(motif) > MOTIF_MAX:
        raise DecisionInvalideError(f"Le motif dépasse {MOTIF_MAX} caractères ; résumez-le.")
    return motif


def changement_de_statut(ancien: str | None, nouveau: str) -> str | None:
    """Le refus, en mots, quand un formulaire pose une décision sans passer par elle ; None si
    le changement est permis. `ancien` vaut None pour un avis nouveau."""
    if nouveau in DECISIONS and nouveau != ancien:
        return (
            "« On répond » et « on ne répond pas » se décident depuis la fiche de l'avis, "
            "avec un motif."
        )
    return None


def qualite(direction: bool, delegation: bool) -> str | None:
    """« direction » ou « delegation » selon les groupes de la personne ; None si elle ne peut
    pas décider. La direction l'emporte quand on est dans les deux."""
    if direction:
        return DIRECTION
    if delegation:
        return DELEGATION
    return None
