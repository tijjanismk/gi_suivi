"""Décision « on répond ou pas » (ADR 0021 et 0022), sans base."""

import pytest

from moteur.avis.decision import (
    DELEGATION,
    DIRECTION,
    GO,
    MOTIF_MAX,
    NO_GO,
    DecisionInvalideError,
    changement_de_statut,
    controler,
    qualite,
)


def test_une_decision_motivee_avant_le_depot():
    motif = "  Lots A et B dans notre métier, 26 références de contrôle.\n"
    assert controler(GO, motif, "en_analyse") == motif.strip()
    assert controler(NO_GO, "Chiffre d'affaires exigé hors de portée", "recu")


@pytest.mark.parametrize("motif", ["", "   ", "\n\t", "…", " - "])
def test_une_decision_sans_motif_est_refusee(motif):
    with pytest.raises(DecisionInvalideError, match="Indiquez pourquoi"):
        controler(GO, motif, "en_analyse")


def test_un_motif_trop_long_est_refuse():
    with pytest.raises(DecisionInvalideError, match="résumez"):
        controler(GO, "x" * (MOTIF_MAX + 1), "en_analyse")


def test_une_decision_se_revoit_mais_ne_se_repete_pas():
    assert controler(NO_GO, "TDR lus : le lot A est réservé aux entreprises", GO)
    with pytest.raises(DecisionInvalideError, match="déjà la décision en cours"):
        controler(GO, "On confirme", GO)


@pytest.mark.parametrize("statut", ["depose", "gagne", "perdu", "sans_suite"])
def test_pas_de_decision_apres_le_depot(statut):
    with pytest.raises(DecisionInvalideError, match="avant le dépôt"):
        controler(NO_GO, "Trop tard", statut)


def test_seules_deux_decisions():
    with pytest.raises(DecisionInvalideError, match="Choisissez"):
        controler("depose", "Déposé hier", "en_analyse")


def test_le_formulaire_ne_pose_pas_une_decision():
    assert changement_de_statut("en_analyse", GO)
    assert changement_de_statut(None, NO_GO)  # un avis nouveau non plus
    assert changement_de_statut(GO, NO_GO)
    # garder la décision en cours, ou passer à un autre statut, reste permis
    assert changement_de_statut(GO, GO) is None
    assert changement_de_statut(GO, "depose") is None
    assert changement_de_statut("recu", "en_analyse") is None
    assert changement_de_statut(None, "recu") is None


def test_qualite_de_celui_qui_decide():
    assert qualite(direction=True, delegation=True) == DIRECTION
    assert qualite(direction=False, delegation=True) == DELEGATION
    assert qualite(direction=False, delegation=False) is None
