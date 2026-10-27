"""AV06 — experts du vivier comparés au profil d'un poste des TDR, sans base."""

from moteur.avis.experts import Besoin, Profil, classer, evaluer, rang_niveau
from moteur.avis.filtres import Reference, lire_filtre

CONTROLE = Reference(1, "GIC-AEP-CTR-015", "Contrôle des forages", nature="CTR", annee=2019)
ETUDE = Reference(2, "GIC-AEP-ETU-001", "Études d'adduction d'eau", nature="ETU", annee=2020)
# Le chef de mission de la DP UNICEF : ingénieur, 5 ans au moins, deux contrôles de travaux
CHEF = Besoin(
    "Contrôleur principal",
    niveau_min="bac+5",
    annees_min=5,
    nb_references_min=2,
    specialites=("hydraulique", "hydrogéologie", "génie civil"),
    filtre=lire_filtre({"natures": ["CTR", "ETC"]}),
)


def test_niveaux():
    assert rang_niveau("bac+5") > rang_niveau("bac+3") > rang_niveau("") == rang_niveau("bts")


def test_un_profil_qui_repond_a_tout():
    p = Profil(
        1,
        "DICKO Oumar",
        "Ingénieur génie civil (BTP)",
        "bac+5",
        2008,
        references=(CONTROLE, CONTROLE),
    )
    x = evaluer(CHEF, p, 2026)
    assert x.complet and x.annees == 18 and x.references == 2


def test_ce_qui_manque_est_dit():
    p = Profil(2, "KEITA Ousmane", "Génie civil", "bac+3", 2018, references=(CONTROLE, ETUDE))
    x = evaluer(CHEF, p, 2026)
    assert x.ecarts == ("diplôme bac+3, bac+5 demandé", "1 référence(s) pour 2 demandée(s)")
    qhse = Besoin("Spécialiste QHSE", annees_min=5, specialites=("QHSE", "hygiène sécurité"))
    sans = evaluer(qhse, Profil(3, "X", "Hydrogéologie", disponible=False), 2026)
    assert sans.ecarts == (
        "début de carrière inconnu pour 5 demandé(s)",
        "spécialité non trouvée : QHSE, hygiène sécurité",
        "non disponible",
    )


def test_classement():
    complet = Profil(1, "B", "hydraulique", "bac+5", 2010, references=(CONTROLE, CONTROLE))
    partiel = Profil(2, "A", "hydraulique", "bac+5", 2010, references=(CONTROLE,))
    loin = Profil(3, "C", "comptabilité", "", None)
    noms = [x.profil.nom for x in classer(CHEF, [loin, partiel, complet], 2026)]
    assert noms == ["B", "A", "C"]
