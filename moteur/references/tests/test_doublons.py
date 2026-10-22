"""ADR 0008, § 4 — détection des doublons de références, sans base."""

from decimal import Decimal

from moteur.references.doublons import (
    Fiche,
    code_le_plus_ancien,
    comparer,
    mots,
    nature_fusionnee,
    normaliser,
    numero_normalise,
    paires_suspectes,
    proximite,
)

SAME = "Étude d'avant-projet détaillé de la réhabilitation du barrage de Samé Ouolof"


def f(ident, code, intitule, **kw):
    return Fiche(ident, code, intitule, **kw)


def test_normalisation():
    assert normaliser("  Réhabilitation   du BARRAGE, de Samé-Ouolof ! ") == (
        "rehabilitation du barrage de same ouolof"
    )
    assert mots("Étude de la digue et du seuil") == {"etude", "digue", "seuil"}
    assert proximite("", "barrage") == 0
    assert proximite("barrage de Sémé", "Barrage de Seme") == 1
    assert proximite("barrage Sémé", "barrage Bara") == Decimal("0.33")
    assert numero_normalise("N° 09/2026/001/MI") == "092026001MI"
    assert numero_normalise("no. 2023-45") == "202345"
    assert numero_normalise("12") == "" and numero_normalise("") == ""


def test_meme_intitule_dans_deux_domaines():
    """Le cas relevé sur l'AMI SOMAPEP : un contrat codé ENV et HYD."""
    a = f(1, "GIC-HYD-ETU-033", SAME, client="Welthungerhilfe", annee=2016)
    b = f(2, "GIC-ENV-ETU-020", SAME, client="WHH", annee=2016)
    p = comparer(a, b)
    assert p is not None and "même intitulé" in p.raisons and p.score == Decimal("0.90")
    assert p.cle == (1, 2)


def test_meme_client_et_meme_montant():
    a = f(
        1,
        "GIC-AEP-ETC-001",
        "Suivi des travaux d'AEP de Kayes",
        client="SOMAGEP",
        montant=Decimal("45000000"),
    )
    b = f(
        3,
        "GIC-AEP-ETC-003",
        "Contrôle et surveillance AEP Kayes",
        client="Somagep",
        montant=Decimal("45000000"),
    )
    p = comparer(a, b)
    assert p.score == Decimal("0.90")
    assert p.raisons == ["même client et même montant (45 000 000)"]
    # même montant mais client différent, ou montant nul : rien
    assert (
        comparer(a, f(4, "X", "Autre chose", client="ANICT", montant=Decimal("45000000"))) is None
    )
    nuls = (
        f(5, "A", "x", client="C", montant=Decimal(0)),
        f(6, "B", "y", client="C", montant=Decimal(0)),
    )
    assert comparer(*nuls) is None


def test_meme_numero_de_contrat():
    a = f(1, "GIC-HYD-ETU-012", "Étude du micro-barrage", numero_contrat="N° 09/2026/001/MI")
    b = f(2, "GIC-HYD-ETC-006", "Contrôle des travaux", numero_contrat="092026001MI")
    p = comparer(a, b)
    assert p.score == 1 and p.raisons[0].startswith("même numéro de contrat")


def test_intitules_proches_mais_annees_eloignees():
    a = f(
        1, "A", "Étude des aménagements de bas-fonds de Kouloudiengue", client="ACTION", annee=2019
    )
    b = f(
        2, "B", "Étude des aménagements de bas-fonds de Kouloudiengue", client="ACTION", annee=2023
    )
    assert comparer(a, b) is None  # même client, quatre ans d'écart : deux missions
    c = f(
        3,
        "C",
        "Étude d'aménagement des bas-fonds de Kouloudiengue phase 2",
        client="ACTION",
        annee=2023,
    )
    p = comparer(b, c)
    assert (
        p is not None
        and "même client" in p.raisons
        and p.raisons[0].startswith("intitulés proches")
    )
    # un client différent baisse le score
    d = f(
        4,
        "D",
        "Étude d'aménagement des bas-fonds de Kouloudiengue phase 2",
        client="FIDA",
        annee=2023,
    )
    assert comparer(b, d).score < p.score


def test_paires_suspectes_triees_et_deja_tranchees_exclues():
    fiches = [
        f(1, "GIC-HYD-ETU-033", SAME, client="WHH", annee=2016),
        f(2, "GIC-ENV-ETU-020", SAME, client="WHH", annee=2016),
        f(3, "GIC-HYD-ETU-032", SAME, client="Welthungerhilfe", annee=2016),
        f(
            4,
            "GIC-AEP-CTR-003",
            "Contrôle des travaux d'AEP de Kayes",
            client="SOMAGEP",
            annee=2020,
        ),
    ]
    paires = paires_suspectes(fiches)
    assert len(paires) == 3 and paires[0].score >= paires[-1].score
    assert {p.cle for p in paires} == {(1, 2), (1, 3), (2, 3)}
    assert {p.cle for p in paires_suspectes(fiches, frozenset({(1, 2)}))} == {(1, 3), (2, 3)}


def test_fusion_nature_et_code_garde():
    assert nature_fusionnee("ETU", "CTR") == "ETC"
    assert nature_fusionnee("CTR", "ETC") == "ETC"
    assert nature_fusionnee("ETU", "ETU") == "ETU"
    assert code_le_plus_ancien("GIC-HYD-ETU-033", "GIC-ENV-ETU-020") == "GIC-ENV-ETU-020"
    assert code_le_plus_ancien("GIC-AEP-ETC-001", "GIC-AEP-ETC-003") == "GIC-AEP-ETC-001"
    assert code_le_plus_ancien("SANS-NUMERO", "GIC-AEP-ETC-003") == "GIC-AEP-ETC-003"
