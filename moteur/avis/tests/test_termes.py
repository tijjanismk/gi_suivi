"""Termes des types d'ouvrages (ADR 0019, AV15), sans base : les cas de la simulation du
10/11/2026, où « Mini AEP », « AEPS » ou « PEA » ne trouvaient aucune de nos références AES."""

from moteur.avis.filtres import Reference, correspond, lire_filtre, termes_trouves
from moteur.avis.selection import selectionner
from moteur.avis.termes import (
    REFERENCES,
    Terme,
    contient,
    equivalents,
    est_sigle,
    meme_terme,
)

LEXIQUE = (
    Terme("Adduction d'eau sommaire", "aes"),  # libellé du type
    Terme("AES", "aes"),  # sigle du type
    Terme("adduction d'eau sommaire", "aes"),
    Terme("mini-AEP", "aes", pays="Niger"),
    Terme("AEPS", "aes", pays="Burkina Faso"),
    Terme("poste d'eau autonome", "aes"),
    Terme("PEA", "aes", pays="Burkina Faso"),
    Terme("PPM", "ppm", portee=REFERENCES),  # « plan de passation des marchés » dans les avis
    Terme("périmètre maraîcher", "ppm"),
    Terme("Forage", "forage"),
)
AES_GAO = Reference(
    1,
    "GIC-AEP-CTR-902",
    "Contrôle des travaux de forages, d'un CSCOM et d'adductions d'eau sommaire autour de Gao",
    pays="Mali",
    annee=2025,
)
BAMBA = Reference(
    2, "GIC-AEP-CTR-901", "Contrôle de forages et AES à Bamba, Bourem et Tarkint", pays="Mali"
)
PEA_BURKINA = Reference(3, "GIC-AEP-CTR-950", "Contrôle de 12 PEA à Dédougou", pays="Burkina Faso")
PEA_MALI = Reference(4, "GIC-AEP-CTR-951", "Contrôle de 12 PEA à Kati", pays="Mali")
PISTES = Reference(5, "GIC-RTE-ETU-901", "Études de 67 km de pistes rurales", pays="Mali")


def test_un_sigle_est_ecrit_en_capitales():
    assert est_sigle("AEPS") and est_sigle("PEA") and est_sigle("F/PMH")
    assert not est_sigle("mini-AEP") and not est_sigle("Mini AEP") and not est_sigle("A")


def test_comparaison_tolerante_des_mots():
    texte = "Contrôle des travaux d'adductions d’eau sommaires à Gao"
    assert contient(texte, "adduction d'eau sommaire")  # pluriel, apostrophe typographique
    assert contient("réalisation de mini AEP solaires", "mini-AEP")  # tiret égal à espace
    assert contient("Périmètres maraichers de Kayes", "périmètre maraîcher")  # accents
    assert not contient("adduction d'eau potable", "adduction d'eau sommaire")


def test_un_sigle_ne_se_compare_qu_en_capitales_et_en_entier():
    assert contient("Contrôle de 12 PEA à Dédougou", "PEA")
    assert not contient("Contrôle de la pea", "PEA")
    assert not contient("Construction of a bridge", "OF")
    assert not contient("Travaux de PEAGE", "PEA")
    assert not contient("voir https://exemple.org/PEA/avis.pdf", "PEA")  # liens retirés
    assert contient("forages F/PMH réhabilités", "F/PMH")


def test_un_mot_cle_est_ce_terme():
    assert meme_terme("Mini AEP", "mini-AEP")
    assert meme_terme("postes d'eau autonomes", "poste d'eau autonome")
    assert meme_terme("PEA", "PEA") and not meme_terme("pea", "PEA")
    assert not meme_terme("mini-AEP solaires", "mini-AEP")  # un mot-clé plus long : autre chose


def test_un_terme_du_burkina_mene_a_l_aes():
    trouves = {t.texte for t in equivalents("AEPS", LEXIQUE, "Burkina Faso")}
    assert {"adduction d'eau sommaire", "AES", "mini-AEP", "PEA"} <= trouves
    assert "Forage" not in trouves


def test_un_terme_ne_vaut_que_dans_son_pays():
    assert equivalents("AEPS", LEXIQUE, "Niger") == ()  # AEPS est un terme du Burkina
    assert equivalents("Mini AEP", LEXIQUE, "Niger")
    assert equivalents("Mini AEP", LEXIQUE, "Togo") == ()


def test_un_terme_de_portee_references_ne_lit_pas_les_avis():
    # PPM est un plan de passation des marchés dans les avis : il ne désigne pas le type
    assert equivalents("PPM", LEXIQUE, "Mali") == ()
    assert {t.texte for t in equivalents("périmètres maraîchers", LEXIQUE)} == {
        "PPM",
        "périmètre maraîcher",
    }


def test_le_critere_du_burkina_trouve_nos_aes():
    sans_termes = lire_filtre({"mots_cles": ["AEPS"]})
    assert not correspond(sans_termes, AES_GAO)  # le comportement d'avant AV15

    filtre = lire_filtre({"mots_cles": ["AEPS"]}, LEXIQUE, "Burkina Faso")
    assert correspond(filtre, AES_GAO) and correspond(filtre, BAMBA)
    assert termes_trouves(filtre, AES_GAO) == ("Adduction d'eau sommaire",)
    assert termes_trouves(filtre, BAMBA) == ("AES",)
    assert not correspond(filtre, PISTES)


def test_un_terme_d_un_autre_pays_ne_lit_pas_nos_intitules():
    # PEA est un terme du Burkina : il trouve une référence du Burkina, pas une du Mali
    filtre = lire_filtre({"mots_cles": ["AEPS"]}, LEXIQUE, "Burkina Faso")
    assert correspond(filtre, PEA_BURKINA) and termes_trouves(filtre, PEA_BURKINA) == ("PEA",)
    assert not correspond(filtre, PEA_MALI)


def test_le_mot_cle_lui_meme_passe_avant_ses_equivalents():
    filtre = lire_filtre({"mots_cles": ["adduction d'eau sommaire"]}, LEXIQUE, "Mali")
    assert correspond(filtre, AES_GAO) and termes_trouves(filtre, AES_GAO) == ()
    assert termes_trouves(filtre, BAMBA) == ("AES",)


def test_la_selection_dit_par_quel_terme():
    filtre = lire_filtre(
        {"mots_cles": ["Mini AEP"], "pieces_completes_requises": False}, LEXIQUE, "Niger"
    )
    candidates = selectionner(filtre, [AES_GAO, BAMBA, PISTES])
    assert [c.reference.code for c in candidates] == ["GIC-AEP-CTR-902", "GIC-AEP-CTR-901"]
    assert all(c.mots_cles == 1 for c in candidates)
    assert candidates[0].par_termes == ("Adduction d'eau sommaire",)
