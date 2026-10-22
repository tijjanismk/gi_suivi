"""AD01 — échéances des pièces administratives, sans base (ADR 0010, § 5 et 6)."""

from datetime import date

import pytest

from moteur.administratif.echeances import (
    Etat,
    EtatPiece,
    Regle,
    Version,
    ajouter_mois,
    controle,
    date_de_fin,
    etat,
    version_a_la_date,
)


def test_ajouter_mois_fin_de_mois():
    assert ajouter_mois(date(2026, 8, 5), 3) == date(2026, 11, 5)  # quitus de l'ADR
    assert ajouter_mois(date(2026, 11, 30), 3) == date(2027, 2, 28)
    assert ajouter_mois(date(2027, 11, 30), 3) == date(2028, 2, 29)  # année bissextile
    assert ajouter_mois(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert ajouter_mois(date(2026, 12, 15), 12) == date(2027, 12, 15)


def test_date_de_fin_par_regle():
    emission = date(2026, 8, 5)
    assert date_de_fin(Regle.APRES_EMISSION, emission, 3) == date(2026, 11, 5)
    assert date_de_fin("revue_periodique", date(2025, 9, 20), 12) == date(2026, 9, 20)
    assert date_de_fin(Regle.FIN_ANNEE, emission) == date(2026, 12, 31)
    assert date_de_fin(Regle.PERMANENTE, emission) is None
    # date écrite sur le document : elle prime ; sans elle, la durée indicative ; sinon inconnue
    assert date_de_fin(Regle.DATE_DU_DOCUMENT, emission, 3, date(2026, 10, 31)) == date(
        2026, 10, 31
    )
    assert date_de_fin(Regle.DATE_DU_DOCUMENT, emission, 1) == date(2026, 9, 5)
    assert date_de_fin(Regle.DATE_DU_DOCUMENT, emission) is None
    with pytest.raises(ValueError, match="durée"):
        date_de_fin(Regle.APRES_EMISSION, emission)
    with pytest.raises(ValueError):
        date_de_fin("inconnue", emission, 3)


def test_etat_a_une_date():
    quitus = Version(date(2026, 8, 5), date(2026, 11, 5))
    assert etat(quitus, date(2026, 10, 1), 15) == EtatPiece(Etat.VALIDE, 35)
    assert etat(quitus, date(2026, 10, 21), 15) == EtatPiece(Etat.A_RENOUVELER, 15)
    assert etat(quitus, date(2026, 11, 5), 15) == EtatPiece(Etat.A_RENOUVELER, 0)  # dernier jour
    assert etat(quitus, date(2026, 11, 6), 15) == EtatPiece(Etat.EXPIREE, -1)
    assert etat(quitus, date(2026, 11, 5), 0) == EtatPiece(Etat.VALIDE, 0)  # sans rappel
    assert etat(None, date(2026, 10, 1)) == EtatPiece(Etat.MANQUANTE)
    assert etat(quitus, date(2026, 8, 4)) == EtatPiece(Etat.MANQUANTE)  # pas encore émise
    nif = Version(date(2010, 1, 1), None)
    assert etat(nif, date(2026, 10, 22), 15) == EtatPiece(Etat.PERMANENTE)
    assert etat(quitus, date(2026, 10, 21), 15).a_traiter
    assert not etat(nif, date(2026, 10, 22)).a_traiter


def test_version_a_la_date():
    mai = Version(date(2026, 5, 5), date(2026, 8, 5), 1)
    aout = Version(date(2026, 8, 5), date(2026, 11, 5), 2)
    assert version_a_la_date([aout, mai], date(2026, 10, 1)) == aout
    assert version_a_la_date([aout, mai], date(2026, 6, 1)) == mai
    assert version_a_la_date([aout, mai], date(2026, 1, 1)) is None
    assert version_a_la_date([], date(2026, 1, 1)) is None


def test_controle_a_la_date_de_depot():
    """Le quitus valide aujourd'hui est périmé 7 jours avant le dépôt du 12/11 (maquette 4)."""
    versions = {
        "QUITUS-FISCAL": [Version(date(2026, 8, 5), date(2026, 11, 5))],
        "INPS": [Version(date(2026, 9, 12), date(2026, 12, 12))],
        "NIF": [Version(date(2010, 1, 1), None)],
        "RCCM": [],
    }
    lignes = controle(
        ["INPS", "NIF", "QUITUS-FISCAL", "DENOMINATIONS", "RCCM"], versions, date(2026, 11, 12)
    )
    assert [(ligne.code, ligne.etat.etat) for ligne in lignes] == [
        ("QUITUS-FISCAL", Etat.EXPIREE),
        ("DENOMINATIONS", Etat.MANQUANTE),
        ("RCCM", Etat.MANQUANTE),
        ("INPS", Etat.VALIDE),
        ("NIF", Etat.PERMANENTE),
    ]
    assert lignes[0].etat.jours == -7 and lignes[3].etat.jours == 30
    assert lignes[1].version is None
