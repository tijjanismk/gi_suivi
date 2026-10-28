"""Sommaire et intercalaires d'un AMI, sans base : le dossier FIER II (Ségou, 2026) en modèle."""

from moteur.avis.sommaire import Critere, Piece, sommaire

ETUDES = "Expériences spécifiques dans les études"
CONTROLE = "Expériences spécifiques dans le contrôle et la surveillance des travaux"
FIER_II = [
    Critere("1", "Expériences générales en rapport avec la mission"),
    Critere("2", "Expériences spécifiques"),
    Critere("2.1", f"{ETUDES} des travaux d'aménagements hydroagricoles"),
    Critere("2.2", f"{ETUDES} d'infrastructures aquacoles ou animales"),
    Critere("2.3", f"{ETUDES} d'infrastructures de bâtiments"),
    Critere("3", CONTROLE),
    Critere("3.1", f"{CONTROLE} d'aménagements hydroagricoles"),
    Critere("3.2", f"{CONTROLE} d'infrastructures aquacoles ou animales"),
    Critere("3.3", f"{CONTROLE} d'infrastructures de bâtiments"),
]


def test_le_dossier_fier_ii_une_ligne_par_intercalaire():
    lignes = sommaire(FIER_II, groupement=True)
    assert [x.code for x in lignes] == [
        *("A", "A.1", "A.2", "A.3", "A.4", "B", "C", "D", "D.1"),
        *("E", "E.1", "E.2", "E.2.1", "E.2.2", "E.2.3", "E.3", "E.3.1", "E.3.2", "E.3.3", "F"),
    ]
    par_code = {x.code: x for x in lignes}
    assert par_code["A.2"].libelle == "ACCORD DE GROUPEMENT"
    assert [par_code[c].libelle for c in "BCDE"] == [
        "PIÈCES ADMINISTRATIVES",  # la part du bureau, même en groupement
        "PRÉSENTATION",
        "PERSONNEL CLÉ",
        "EXPÉRIENCES",
    ]
    assert par_code["E.2.1"].libelle.startswith("EXPÉRIENCES SPÉCIFIQUES DANS LES ÉTUDES DES")
    assert (par_code["E"].niveau, par_code["E.2"].niveau, par_code["E.2.1"].niveau) == (1, 2, 3)


def test_sans_groupement_pas_d_accord():
    lignes = sommaire(FIER_II[:1])
    assert [(x.code, x.libelle) for x in lignes[:4]] == [
        ("A", "LETTRES"),
        ("A.1", "LETTRE DE MANIFESTATION D'INTÉRÊT"),
        ("A.2", "PROCURATION DE SIGNATURE"),
        ("A.3", "ADRESSES ET CONTACTS DES CONSULTANTS"),
    ]
    assert [x.code for x in lignes[4:]] == ["B", "C", "D", "D.1", "E", "E.1", "F"]


def test_ce_que_l_application_sait_de_chaque_rubrique():
    pieces = [
        Piece("NIF", "permanente", False),
        Piece("TVA", "périmée 13 j avant le dépôt", True),
        Piece("PRESENTATION", "valide · 30 j de marge", False),
    ]
    criteres = [Critere("1", "Contrôle de forages", retenues=12), Critere("2", "Note", None)]
    lignes = sommaire(criteres, pieces=pieces, postes=[True, False])
    etats = {x.code: (x.etat, x.a_regler) for x in lignes}
    assert etats["B"] == ("1 pièce sur 2 à régler à la date limite", True)  # sans C ni F
    assert etats["C"] == ("présentation du bureau : valide · 30 j de marge", False)
    assert etats["F"] == ("liste des moyens non cochée dans les pièces exigées", True)
    assert etats["D"] == ("1 poste sur 2 sans expert retenu", True)
    assert etats["E.1"] == ("12 références retenues", None)  # informe sans juger
    assert etats["E.2"] == ("", None)  # noté à la main
    assert etats["A"] == ("", None)
    vide = {x.code: x.etat for x in sommaire([], pieces=[Piece("NIF", "permanente", False)])}
    assert vide["B"] == "1 pièce valide à la date limite"
    assert vide["D"] == "aucun poste saisi" and vide["E"] == "aucun critère au barème"
