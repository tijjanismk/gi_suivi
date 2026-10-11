from datetime import datetime

from moteur.suivi.classement import classer_chemin, classer_observation, normaliser_chemin
from moteur.suivi.types import Observation, Racine, RegleException

R_MISSIONS = Racine(r"\\AD-SERVEUR\GIC\MISSIONS_EN_COURS", 1)
R_AVIS = Racine(r"\\AD-SERVEUR\GIC\AVIS", 3)  # AVIS\<pays>\<AAAA-MM>\<avis>
RACINES = [R_MISSIONS, R_AVIS]
LECTEURS = {"H:": r"\\AD-SERVEUR\GIC"}


def test_normalisation_lettre_vers_unc():
    assert (
        normaliser_chemin(r"H:\MISSIONS_EN_COURS\x\f.docx", LECTEURS)
        == r"\\ad-serveur\gic\missions_en_cours\x\f.docx"
    )


def test_normalisation_autres_noms_du_serveur():
    # nom complet (FQDN) : ramené au nom court, sans réglage
    assert (
        normaliser_chemin(r"\\ad-serveur.giconseils.local\ETUDES\Bargondaga\a.docx")
        == r"\\ad-serveur\etudes\bargondaga\a.docx"
    )
    # adresse IP : par la correspondance, comme une lettre de lecteur
    alias = {"\\\\192.168.2.250": r"\\AD-SERVEUR", "E:": r"\\AD-SERVEUR\ETUDES"}
    assert (
        normaliser_chemin(r"\\192.168.2.250\ETUDES\x.docx", alias) == r"\\ad-serveur\etudes\x.docx"
    )
    assert normaliser_chemin(r"\\192.168.2.250", alias) == r"\\ad-serveur"
    assert (
        normaliser_chemin(r"E:\Bargondaga\x.docx", alias)
        == r"\\ad-serveur\etudes\bargondaga\x.docx"
    )
    # sans correspondance, une IP reste telle quelle ; un chemin local n'est pas touché
    assert normaliser_chemin(r"\\192.168.2.250\ETUDES") == r"\\192.168.2.250\etudes"
    assert normaliser_chemin(r"C:\Users\x\Bureau.v2\a.docx") == r"c:\users\x\bureau.v2\a.docx"
    # le classement en profite
    r = Racine(r"\\AD-SERVEUR\ETUDES", 1)
    c = classer_chemin(r"\\ad-serveur.giconseils.local\ETUDES\Bargondaga\a.docx", [r])
    assert c.statut == "dossier" and c.dossier_nom == "bargondaga"


def test_normalisation_accents_et_casse():
    assert (
        normaliser_chemin(r"\\AD-SERVEUR\GIC\Études\Rapport.docx")
        == r"\\ad-serveur\gic\etudes\rapport.docx"
    )


def test_mission_codee():
    c = classer_chemin(
        r"\\AD-SERVEUR\GIC\MISSIONS_EN_COURS\GIC-HYD-ETU-052_Bargondaga\Plans\digue.dwg", RACINES
    )
    assert c.statut == "dossier"
    assert c.code == "GIC-HYD-ETU-052"
    assert c.dossier_nom == "gic-hyd-etu-052_bargondaga"


def test_meme_dossier_par_lettre_et_par_unc():
    a = classer_chemin(r"H:\MISSIONS_EN_COURS\GIC-HYD-ETU-052_Bargondaga\a.docx", RACINES, LECTEURS)
    b = classer_chemin(
        r"\\ad-serveur\gic\missions_en_cours\GIC-HYD-ETU-052_Bargondaga\sous\b.pdf",
        RACINES,
        LECTEURS,
    )
    assert a.dossier_chemin == b.dossier_chemin


def test_avis_profondeur_trois():
    c = classer_chemin(
        r"\\AD-SERVEUR\GIC\AVIS\MALI\2026-10\2026-SOMAPEP-001_recharge-nappe\OFFRE\methodo.docx",
        RACINES,
    )
    assert c.statut == "dossier"
    assert c.code == "2026-SOMAPEP-001"
    assert c.dossier_chemin.endswith(r"\avis\mali\2026-10\2026-somapep-001_recharge-nappe")


def test_fichier_au_niveau_de_la_racine_est_a_classer():
    c = classer_chemin(r"\\AD-SERVEUR\GIC\MISSIONS_EN_COURS\liste.xlsx", RACINES)
    assert c.statut == "a_classer" and c.racine == R_MISSIONS.chemin


def test_hors_racine_est_a_classer():
    c = classer_chemin(r"C:\Users\x\Desktop\brouillon.docx", RACINES)
    assert c.statut == "a_classer" and c.racine is None


def test_code_d_avis_extrait_par_lecteur_reseau():
    c = classer_chemin(
        r"H:\AVIS\MALI\2026-10\2026-SOMAPEP-001_recharge-nappe\TDR.pdf", RACINES, LECTEURS
    )
    assert c.statut == "dossier" and c.code == "2026-SOMAPEP-001" and c.racine == R_AVIS.chemin


def test_dossier_sans_code_est_un_dossier_sans_code():
    c = classer_chemin(r"\\AD-SERVEUR\GIC\MISSIONS_EN_COURS\A-CODER_usine\rapport.docx", RACINES)
    assert c.statut == "dossier" and c.code is None


def test_racine_la_plus_longue_gagne():
    r = [Racine(r"\\srv\gic", 1), Racine(r"\\srv\gic\MISSIONS_EN_COURS", 1)]
    c = classer_chemin(r"\\srv\gic\MISSIONS_EN_COURS\GIC-AEP-CTR-003_x\f.pdf", r)
    assert c.racine == r"\\srv\gic\MISSIONS_EN_COURS"


def test_brouillon_et_application():
    o = Observation(datetime(2026, 10, 7), "WINWORD.EXE", "Document1", None, 0)
    assert classer_observation(o, RACINES).statut == "brouillon"
    o2 = Observation(datetime(2026, 10, 7), "chrome.exe", None, None, 0)
    assert classer_observation(o2, RACINES).statut == "application"


PROJET_052 = r"\\AD-SERVEUR\GIC\MISSIONS_EN_COURS\GIC-HYD-ETU-052_Bargondaga"
BUREAU = r"C:\Users\x\Desktop"


def test_fichier_technique_ignore():
    assert classer_chemin(PROJET_052 + r"\~$rapport.docx", RACINES).statut == "ignore"
    assert classer_chemin(PROJET_052 + r"\Plans\digue.dwl", RACINES).statut == "ignore"
    o = Observation(datetime(2026, 10, 7), "WINWORD.EXE", "~$rapport.docx", None, 0)
    assert classer_observation(o, RACINES).statut == "ignore"


def test_exception_par_chemin_exact():
    r = RegleException(BUREAU + r"\TDR_Bargondaga.pdf", "chemin", PROJET_052, "GIC-HYD-ETU-052")
    c = classer_chemin(BUREAU + r"\tdr_bargondaga.PDF", RACINES, exceptions=[r])
    assert c.statut == "dossier" and c.code == "GIC-HYD-ETU-052" and c.par_exception
    assert c.dossier_nom == "gic-hyd-etu-052_bargondaga"
    assert classer_chemin(BUREAU + r"\autre.pdf", RACINES, exceptions=[r]).statut == "a_classer"


def test_exception_par_prefixe_de_dossier():
    r = RegleException(r"D:\Archives\Bargondaga", "prefixe", PROJET_052, "GIC-HYD-ETU-052")
    assert classer_chemin(
        r"D:\Archives\Bargondaga\2025\note.docx", RACINES, exceptions=[r]
    ).par_exception
    # « Bargondaga2 » n'est pas sous le dossier « Bargondaga »
    assert (
        classer_chemin(r"D:\Archives\Bargondaga2\note.docx", RACINES, exceptions=[r]).statut
        == "a_classer"
    )


def test_exception_par_mot_cle_sans_accents_ni_casse():
    r = RegleException("Barg ondaga", "mot_cle", PROJET_052)
    r2 = RegleException("Étude Bargondaga", "mot_cle", PROJET_052, "GIC-HYD-ETU-052")
    c = classer_chemin(BUREAU + r"\ETUDE BARGONDAGA v2.docx", RACINES, exceptions=[r, r2])
    assert c.statut == "dossier" and c.code == "GIC-HYD-ETU-052"


def test_exception_la_plus_precise_l_emporte():
    exacte = RegleException(BUREAU + r"\a.pdf", "chemin", r"\\srv\gic\exacte")
    large = RegleException(BUREAU, "prefixe", r"\\srv\gic\large")
    etroite = RegleException(BUREAU + r"\TDR", "prefixe", r"\\srv\gic\etroite")
    mot = RegleException("tdr", "mot_cle", r"\\srv\gic\mot")
    regles = [mot, large, etroite, exacte]
    assert classer_chemin(BUREAU + r"\a.pdf", RACINES, exceptions=regles).dossier_nom == "exacte"
    assert (
        classer_chemin(BUREAU + r"\TDR\b.pdf", RACINES, exceptions=regles).dossier_nom == "etroite"
    )
    assert classer_chemin(BUREAU + r"\c.pdf", RACINES, exceptions=regles).dossier_nom == "large"
    assert classer_chemin(r"E:\tdr\d.pdf", RACINES, exceptions=regles).dossier_nom == "mot"


def test_la_convention_passe_avant_les_exceptions():
    r = RegleException("bargondaga", "mot_cle", r"\\srv\gic\autre")
    c = classer_chemin(PROJET_052 + r"\a.docx", RACINES, exceptions=[r])
    assert c.code == "GIC-HYD-ETU-052" and not c.par_exception


def test_exception_sur_un_fichier_pose_a_la_racine():
    # au niveau de la racine, la convention ne sait pas dire : l'exception tranche,
    # et la racine reste connue
    r = RegleException(r"\\AD-SERVEUR\GIC\MISSIONS_EN_COURS\liste.xlsx", "chemin", PROJET_052)
    c = classer_chemin(r"H:\MISSIONS_EN_COURS\liste.xlsx", RACINES, LECTEURS, exceptions=[r])
    assert c.par_exception and c.racine == R_MISSIONS.chemin


def test_exception_par_observation():
    r = RegleException(BUREAU, "prefixe", PROJET_052)
    o = Observation(datetime(2026, 10, 7), "Acrobat.exe", "x.pdf", BUREAU + r"\x.pdf", 0)
    assert classer_observation(o, RACINES, exceptions=[r]).par_exception


def test_nom_avec_extension_sans_chemin_est_a_classer():
    # PDF lu dans un navigateur : fichier connu, impossible à rattacher, pas un brouillon
    o = Observation(datetime(2026, 10, 7), "chrome.exe", "TDR_052.pdf", None, 0)
    assert classer_observation(o, RACINES).statut == "a_classer"
