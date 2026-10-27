"""ADR 0013 § 3 — filtre d'un critère et preuve d'une référence, sans base."""

import re
from dataclasses import replace
from decimal import Decimal

import pytest

from moteur.avis.filtres import (
    PIECES_PAR_DEFAUT,
    FiltreInvalideError,
    Manque,
    Piece,
    Preuve,
    Reference,
    correspond,
    lire_filtre,
    mots_cles_trouves,
    preuve,
)

UNICEF_2019 = Reference(
    1,
    "GIC-AEP-CTR-015",
    "Contrôle des travaux d'hydraulique et de Génie civil dans les écoles et les communautés "
    "des régions de Koulikoro et de Menaka (lot 1 et lot 4)",
    nature="CTR",
    domaines=frozenset({"AEP"}),
    annee=2019,
    clients=frozenset({"UNICEF"}),
)
# Le critère des références de la DP UNICEF LRPS-MLI-2026-9206428 (simulation du 27/10/2026) :
# contrôleur principal, dix dernières années, PV de réception ou attestation de bonne fin
FILTRE_UNICEF = {
    "natures": ["CTR", "ETC"],
    "domaines": ["AEP", "HYD"],
    "roles": ["seul", "chef_de_file"],
    "annee_min": 2016,
    "mots_cles": ["forage", "AES", "latrine", "hydraulique", "génie civil"],
    "pieces_requises": ["bonne_fin|pv_reception"],
}


def test_filtre_vide_et_pieces_par_defaut():
    vide = lire_filtre(None)
    assert vide == lire_filtre({}) and vide.pieces_requises == PIECES_PAR_DEFAUT
    assert vide.pieces_completes_requises and correspond(vide, UNICEF_2019)


def test_filtre_invalide_dit_pourquoi():
    for donnees, message in [
        ({"nature": ["CTR"]}, "clé inconnue : nature"),
        ({"natures": "CTR"}, "liste de textes"),
        ({"natures": ["CTRL"]}, "CTRL inconnue"),
        ({"roles": ["principal"]}, "principal inconnu"),
        ({"annee_min": "2016"}, "année"),
        ({"annee_min": 2025, "annee_max": 2010}, "après"),
        ({"mots_cles": ["de la"]}, "aucun mot utile"),
        ({"quantites_min": {"superficie_ha": "trente"}}, "nombre"),
        ({"pieces_requises": []}, "vide"),
        ({"pieces_requises": ["attestation|pv"]}, "pièce inconnue (pv)"),
        ({"pieces_completes_requises": "oui"}, "true ou false"),
        (["CTR"], "objet JSON"),
    ]:
        with pytest.raises(FiltreInvalideError, match=re.escape(message)):
            lire_filtre(donnees)


def test_le_critere_des_references_unicef():
    filtre = lire_filtre(FILTRE_UNICEF)
    assert correspond(filtre, UNICEF_2019)
    assert mots_cles_trouves(filtre, UNICEF_2019) == 2  # « hydraulique », « génie civil »
    assert correspond(filtre, replace(UNICEF_2019, domaines=frozenset({"BAT", "AEP"})))
    ecartees = [
        replace(UNICEF_2019, role="membre"),
        replace(UNICEF_2019, annee=2014),
        replace(UNICEF_2019, annee=None),
        replace(UNICEF_2019, nature="ETU"),
        replace(UNICEF_2019, domaines=frozenset({"BAT"})),
        replace(UNICEF_2019, intitule="Contrôle de la construction de salles de classe"),
    ]
    assert not any(correspond(filtre, r) for r in ecartees)


def test_mots_cles_accents_pluriels_et_expressions():
    r = Reference(2, "GIC-HYD-ETU-033", "Études APD des micro-barrages et retenues de Samé")
    filtre = lire_filtre({"mots_cles": ["barrage", "Retenue", "digue filtrante"]})
    assert mots_cles_trouves(filtre, r) == 2 and correspond(filtre, r)
    assert not correspond(lire_filtre({"mots_cles": ["digue filtrante"]}), r)


def test_thesaurus_quantites_pays_clients_localites():
    r = Reference(
        3,
        "GIC-HYD-ETU-040",
        "Aménagement du bas-fond de Kodougou",
        types_ouvrage=frozenset({"micro-barrage"}),
        familles_ouvrage=frozenset({"Mobilisation des eaux de surface"}),
        quantites={"superficie_ha": Decimal("35")},
        pays="Mali",
        clients=frozenset({"Islamic Relief", "IR"}),
        localites=frozenset({"koulikoro", "kati"}),
    )
    famille = {"types_ouvrage": ["seuil"], "familles_ouvrage": ["mobilisation des eaux de surface"]}
    assert correspond(lire_filtre(famille), r)
    assert not correspond(lire_filtre({"types_ouvrage": ["seuil"]}), r)
    assert correspond(lire_filtre({"quantites_min": {"superficie_ha": 30}, "pays": ["MALI"]}), r)
    assert not correspond(lire_filtre({"quantites_min": {"superficie_ha": 40}}), r)
    assert not correspond(lire_filtre({"quantites_min": {"longueur_km": 1}}), r)
    assert correspond(lire_filtre({"clients": ["ir"], "localites": ["Koulikoro"]}), r)
    assert not correspond(lire_filtre({"pays": ["Burkina Faso"]}), r)


def test_preuve_pieces_par_defaut_et_unicef():
    garde = Piece("garde", "garde_contrat", auditee=True, bonne=True)
    signature = Piece("signature", auditee=True, bonne=True)
    attestation = Piece("attestation", "pv_reception")  # rattachée, pas encore auditée
    r = replace(UNICEF_2019, pieces=(garde, signature, attestation))
    defaut, unicef = lire_filtre({}), lire_filtre(FILTRE_UNICEF)
    assert preuve(defaut, r) == (Preuve.A_AUDITER, (Manque("attestation", Preuve.A_AUDITER),))
    assert preuve(unicef, r)[0] == Preuve.A_AUDITER
    bonne = replace(attestation, auditee=True, bonne=True)
    assert preuve(unicef, replace(r, pieces=(bonne,))) == (Preuve.PROUVEE, ())
    # Auditée mais illisible : elle ne prouve rien ; une bonne exécution n'est pas une bonne fin
    illisible = replace(attestation, auditee=True)
    assert preuve(unicef, replace(r, pieces=(illisible,)))[0] == Preuve.MANQUANTE
    execution = Piece("attestation", "bonne_execution", auditee=True, bonne=True)
    manque = Manque("bonne_fin|pv_reception", Preuve.MANQUANTE)
    assert preuve(unicef, replace(r, pieces=(execution,))) == (Preuve.MANQUANTE, (manque,))
    _, manques = preuve(defaut, replace(r, pieces=()))
    assert [m.exigence for m in manques] == ["garde", "signature", "attestation"]
