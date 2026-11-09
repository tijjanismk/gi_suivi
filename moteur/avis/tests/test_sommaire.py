"""Sommaire et plan du dossier d'un AMI, sans base : la version électronique de SOMAPEP en modèle,
reprise pour les AMI PISEN du Niger (novembre 2026)."""

from datetime import date
from decimal import Decimal

from moteur.avis.sommaire import (
    SANS_JUSTIFIEE,
    Bureau,
    Critere,
    Etat,
    Experience,
    Justificatif,
    Ligne,
    Piece,
    Poste,
    Reference,
    classer,
    justifiee,
    ligne,
    pays,
    plan,
    sommaire,
)

EIES = "Au moins trois (3) Études d'Impact Environnemental et Social (EIES) de projets hydrauliques"
PAR = "Au moins trois (3) Plans d'Action de Réinstallation (PAR)"
SAHEL = "Une expérience dans des zones sahéliennes ou semi-arides constitue un atout"
QUATRE = ["fiche", "piece", "piece", "piece"]  # la fiche, la garde, la signature, l'attestation


DOSSIER = "REFERENCES\\02_JUSTIFICATIFS\\"


def reference(code: str, annee: int, *types: str) -> Reference:
    justificatifs = tuple(Justificatif(t, f"{DOSSIER}{code}\\{t.upper()}.pdf") for t in types)
    return Reference(
        code,
        f"Mission {code}",
        client="Welthungerhilfe",
        pays="Mali",
        montant=Decimal("12500000"),
        devise="FCFA",
        source="Banque mondiale",
        annee=annee,
        justificatifs=justificatifs,
    )


R1 = reference("GIC-ENV-ETU-001", 2020, "garde", "signature", "attestation")
R2 = reference("GIC-ENV-ETU-002", 2024, "garde")
R3 = reference("GIC-HYD-ETU-003", 2018, "garde", "signature", "attestation")
GENERALE, MODE = "generale", "par_mission"
PISEN = [  # les critères 2 à 4 sont généraux par leur champ : leurs mots ne le disent pas
    Critere("1", "Être légalement constitué depuis au moins dix (10) ans", mode="anciennete"),
    Critere("2", "Au moins cinq (5) études environnementales", GENERALE, MODE, (R1, R2)),
    Critere("3", "Trois (3) missions de bailleurs internationaux", GENERALE, MODE, (R3, R1)),
    Critere("4", "Au moins deux (2) études d'infrastructures rurales", GENERALE, MODE, ()),
    Critere("5", EIES, mode=MODE, retenues=(R3, R1)),
    Critere("6", PAR, mode=MODE, retenues=()),
    Critere("7", SAHEL, mode=MODE),
]
PIECES = [
    Piece("RCCM", "permanente", False, "Immatriculation au RCCM", "PIECES\\r.pdf"),
    Piece("QUITUS-FISCAL", "périmée 3 j avant le dépôt", True, "Quitus fiscal", "PIECES\\q.pdf"),
    Piece("NIF", "manquante", True, "Carte d'identification fiscale"),
    Piece("MOYENS", "valide · 30 j de marge", False, "Liste des moyens", "PIECES\\m.pdf"),
]


def test_l_ordre_de_somapep_sans_groupement():
    lignes = sommaire(PISEN)
    assert [x.code for x in lignes] == [
        *("A", "A.1", "A.2", "B", "C", "D", "D.1", "D.2"),
        *("D.2.1", "D.2.2", "D.2.3", "E", "F"),
    ]
    assert [x.code for x in lignes if not x.au_sommaire] == ["A.1", "A.2"]  # intercalaires seuls
    libelles = {x.code: x.libelle for x in lignes}
    assert libelles["A.1"] == "LETTRE DE MANIFESTATION D'INTÉRÊT"
    assert libelles["A.2"] == "ADRESSES ET CONTACTS DU CONSULTANT"
    assert libelles["B"] == "PIÈCES ADMINISTRATIVES DE GI-Conseils SARL"
    assert libelles["C"] == "PRESENTATION DU BUREAU GI-Conseils"
    assert libelles["D"] == "EXPÉRIENCES DU BUREAU GI-Conseils SARL"
    assert (libelles["D.1"], libelles["D.2"]) == ("EXPÉRIENCE GÉNÉRALE", "EXPÉRIENCES SPÉCIFIQUES")
    assert [libelles[f"D.2.{i}"] for i in (1, 2, 3)] == [EIES, PAR, SAHEL]  # tels quels
    assert libelles["E"] == "ORGANIGRAMME AVEC L'ENSEMBLE DES EXPERTS CLES"
    assert libelles["F"] == "MOYENS MATERIELS ET LOGISTIQUES"
    assert [lignes[i].niveau for i in (0, 6, 8)] == [1, 2, 3]


def test_en_groupement_l_accord_et_la_procuration():
    lignes = sommaire(PISEN, groupement=True, bureau=Bureau("ACME SA", "ACME"))
    assert [(x.code, x.libelle) for x in lignes[:5]] == [
        ("A", "LETTRES"),
        ("A.1", "LETTRE DE MANIFESTATION D'INTÉRÊT"),
        ("A.2", "ACCORD DE GROUPEMENT"),
        ("A.3", "PROCURATION DE SIGNATURE"),
        ("A.4", "ADRESSES ET CONTACTS DU CONSULTANT"),
    ]
    assert lignes[5].libelle == "PIÈCES ADMINISTRATIVES DE ACME SA"  # la part du bureau
    accord = [p for p in plan(PISEN, groupement=True) if p.rubrique == "A.2"]
    assert [(p.genre, p.etat) for p in accord] == [
        ("intercalaire", Etat.REDIGEE),
        ("piece", Etat.MANQUANTE),
    ]


def test_criteres_generaux_et_specifiques():
    fier_ii = [
        Critere("1", "Expériences générales en rapport avec la mission", mode="manuel"),
        Critere("2", "Expériences spécifiques", mode="manuel"),
        Critere("2.1", "Études des travaux d'aménagements hydroagricoles", mode="manuel"),
        Critere("3", "Note sur la méthodologie", mode="manuel"),
        Critere("4", "Expérience générale du cabinet", "specifique", "manuel"),
        Critere("5", "Missions pour la Direction générale de l'hydraulique", mode=MODE),
        Critere("6", "Ancienneté du cabinet", mode="anciennete"),
    ]
    assert classer(fier_ii) == {
        "1": Experience.GENERALE,  # ses mots
        "2": None,  # un titre de groupe : ses sous-critères ont leur rubrique
        "2.1": Experience.SPECIFIQUE,  # les mots de son parent
        "3": Experience.HORS,  # une note saisie à la main, sans mots
        "4": Experience.SPECIFIQUE,  # le champ l'emporte sur les mots
        "5": Experience.SPECIFIQUE,  # « direction générale » n'est pas une expérience générale
        "6": Experience.HORS,
    }
    d2 = [x.libelle for x in sommaire(fier_ii) if x.code.startswith("D.2.")]
    assert d2 == [fier_ii[2].libelle, fier_ii[4].libelle, fier_ii[5].libelle]


def test_ce_que_l_application_sait_de_chaque_rubrique():
    postes = [Poste("Chef de mission", "TRAORE Awa"), Poste("Spécialiste QHSE")]
    toutes = [R1, R2, R3]
    lignes = sommaire(PISEN, pieces=PIECES, postes=postes, references=toutes)
    etats = {x.code: (x.etat, x.a_regler) for x in lignes}
    assert etats["B"] == ("2 pièces sur 3 à régler à la date limite", True)  # sans C ni F
    assert etats["C"] == ("présentation du bureau non cochée dans les pièces exigées", True)
    assert etats["F"] == ("liste des moyens : valide · 30 j de marge", False)
    d1 = "2 références du bureau ; 1 référence sans ses trois pièces, hors du dossier"  # R2
    assert etats["D.1"] == (d1, None)  # toutes les justifiées, pas celles d'un critère
    assert etats["D.2.1"] == ("2 références", None)
    assert etats["D.2.2"] == ("aucune référence ne répond", True)
    assert etats["D.2.3"] == ("simulation non enregistrée", True)
    assert etats["E"] == ("1 poste sur 2 sans expert retenu", True)
    assert etats["A"] == ("", None)
    vide = {x.code: x.etat for x in sommaire([])}
    assert vide["D"] == "aucun critère au barème"
    assert vide["D.1"] == "aucune référence au registre"
    assert vide["D.2"] == "aucun critère d'expérience spécifique"
    assert (vide["B"], vide["E"]) == ("aucune pièce exigée", "aucun poste saisi")


def test_le_plan_page_par_page():
    postes = [Poste("Chef de mission", "TRAORE Awa")]
    pages = plan(PISEN, pieces=PIECES, postes=postes, references=[R1, R2, R3])
    debut = [(p.genre, p.rubrique) for p in pages[:7]]
    assert debut == [
        ("couverture", ""),
        ("sommaire", ""),
        ("intercalaire", "A"),
        ("intercalaire", "A.1"),
        ("lettre", "A.1"),
        ("intercalaire", "A.2"),
        ("adresse", "A.2"),
    ]
    b = [(p.titre, p.etat, p.chemin) for p in pages if p.rubrique == "B" and p.genre == "piece"]
    assert b == [
        ("Immatriculation au RCCM", Etat.A_INSERER, "PIECES\\r.pdf"),
        ("Quitus fiscal", Etat.PERIMEE, "PIECES\\q.pdf"),  # jointe, mais périmée
        ("Carte d'identification fiscale", Etat.MANQUANTE, ""),
    ]
    c = [(p.genre, p.etat) for p in pages if p.rubrique == "C"]
    assert c == [("intercalaire", Etat.REDIGEE), ("piece", Etat.MANQUANTE)]

    d1 = [p for p in pages if p.rubrique == "D.1"]
    attendu = ["intercalaire", "liste", *QUATRE, *QUATRE]  # sans page de famille, sans R2
    assert [p.genre for p in d1] == attendu
    liste = d1[1]
    assert liste.paysage and not liste.entete
    assert liste.titre == "LISTE DES EXPERIENCES GÉNÉRALES"
    numeros = [(g.libelle, [x.numero for x in g.lignes]) for g in liste.groupes]
    assert numeros == [("", [1, 2])]  # une seule liste, la plus récente d'abord
    premiere = Ligne(
        1,
        "Mission GIC-ENV-ETU-001",
        "Welthungerhilfe",
        "Mali",
        "12 500 000 F CFA",
        "Banque mondiale",
        "2020",
    )
    assert liste.groupes[0].lignes[0] == premiere
    fiches = [(p.numero, p.reference, p.etat) for p in d1 if p.genre == "fiche"]
    assert fiches == [  # chaque référence une fois en D.1 ; aucune fiche encore au registre
        (1, "GIC-ENV-ETU-001", Etat.MANQUANTE),
        (2, "GIC-HYD-ETU-003", Etat.MANQUANTE),
    ]
    r1 = [(p.titre, p.etat) for p in d1 if p.reference == "GIC-ENV-ETU-001"][1:]
    assert r1 == [
        ("Page de garde · GIC-ENV-ETU-001", Etat.A_INSERER),
        ("Page de signature · GIC-ENV-ETU-001", Etat.A_INSERER),
        ("Attestation · GIC-ENV-ETU-001", Etat.A_INSERER),
    ]
    assert d1[3].chemin == f"{DOSSIER}GIC-ENV-ETU-001\\GARDE.pdf"
    assert all(p.reference != "GIC-ENV-ETU-002" for p in pages)  # R2 n'a que sa garde

    d21 = [p for p in pages if p.rubrique == "D.2.1"]
    assert [p.genre for p in d21] == ["intercalaire", "liste", "famille", *QUATRE, *QUATRE]
    assert [p.numero for p in d21 if p.genre == "fiche"] == [1, 2]  # ses propres fiches
    for code in ("D.2.2", "D.2.3"):
        assert [(p.genre, p.etat) for p in pages if p.rubrique == code] == [
            ("intercalaire", Etat.REDIGEE),
            ("vide", Etat.MANQUANTE),
        ]
    e = [p for p in pages if p.rubrique == "E"]
    assert [(p.genre, p.etat) for p in e] == [
        ("intercalaire", Etat.REDIGEE),
        ("organigramme", Etat.REDIGEE),  # jamais manquant
    ]
    assert [(p.genre, p.etat) for p in pages[-2:]] == [
        ("intercalaire", Etat.REDIGEE),
        ("piece", Etat.A_INSERER),
    ]
    assert {p.genre for p in pages if p.entete} == {"sommaire", "intercalaire", "organigramme"}
    assert {p.genre for p in pages if p.paysage} == {"liste", "organigramme"}


def test_d1_et_d2_sans_plafond_avec_les_seules_references_justifiees():
    """Règles du porteur (09/11/2026), comme dans SOMAPEP : D.1 donne toutes les références du
    bureau, même sans critère d'expérience générale ; D.2.x toutes celles qui répondent ; en D.1
    comme en D.2, seulement les justifiées (garde, signature et attestation)."""
    assert justifiee(R1) and justifiee(R3) and not justifiee(R2)
    criteres = [Critere("5", EIES, mode=MODE, retenues=(R3, R1, R2))]
    pages = plan(criteres, references=[R3, R1, R2])
    d1 = [(p.numero, p.reference) for p in pages if p.rubrique == "D.1" and p.genre == "fiche"]
    assert d1 == [(1, "GIC-ENV-ETU-001"), (2, "GIC-HYD-ETU-003")]
    d21 = [p.numero for p in pages if p.rubrique == "D.2.1" and p.genre == "fiche"]
    assert d21 == [1, 2]  # chaque référence garde son numéro de D.1
    etat = {x.code: x.etat for x in sommaire(criteres)}["D.2.1"]
    assert etat == "2 références ; 1 référence sans ses trois pièces, hors du dossier"
    seule_r2 = plan([Critere("5", EIES, mode=MODE, retenues=(R2,))], references=[R2])
    vides = [(p.rubrique, p.motif) for p in seule_r2 if p.genre == "vide" and p.rubrique != "B"]
    assert vides == [("D.1", SANS_JUSTIFIEE), ("D.2.1", SANS_JUSTIFIEE)]
    vide = [(p.genre, p.motif) for p in plan([]) if p.rubrique == "D.1"]
    assert vide == [("intercalaire", ""), ("vide", "aucune référence au registre")]


def test_colonnes_des_listes_et_pays():
    r = Reference(
        "GIC-HYD-CTR-010",
        "Contrôle des travaux",
        montant=Decimal("1500.5"),
        devise="EUR",
        debut=date(2019, 3, 1),
        fin=date(2020, 6, 30),
    )
    assert (ligne(r, 4).montant, ligne(r, 4).periode) == ("1 500,50 EUR", "mars 2019 – juin 2020")
    assert ligne(Reference("X", "x", annee=2015), 1).periode == "2015"
    assert pays("Niger") == ("RÉPUBLIQUE DU NIGER", "Fraternité – Travail – Progrès")
    assert pays("Côte d'Ivoire")[0] == "RÉPUBLIQUE DE CÔTE D'IVOIRE"
    assert pays("Ghana") == ("GHANA", "")
