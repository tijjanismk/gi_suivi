"""Lettres de lecteur réseau traduites en chemin UNC par l'agent (résolveur simulé)."""

from gisuivi_agent.fichiers import choisir_ouvert, vers_unc

from moteur.suivi.types import Racine

RESEAU = {"E:": r"\\AD-SERVEUR\ETUDES", "Z:": "\\\\AD-SERVEUR\\AMI\\"}


def resoudre(lettre):
    return RESEAU.get(lettre)


def test_lettre_reseau_traduite():
    assert vers_unc(r"E:\Bargondaga\rapport.docx", resoudre) == (
        r"\\AD-SERVEUR\ETUDES\Bargondaga\rapport.docx"
    )
    assert (
        vers_unc("z:/AMI-2026/Mali/avis.pdf", resoudre)
        == r"\\AD-SERVEUR\AMI/AMI-2026/Mali/avis.pdf"
    )


def test_autres_chemins_inchanges():
    assert vers_unc(r"C:\Users\awa\Bureau\notes.pdf", resoudre) == r"C:\Users\awa\Bureau\notes.pdf"
    assert vers_unc(r"\\AD-SERVEUR\ETUDES\x.docx", resoudre) == r"\\AD-SERVEUR\ETUDES\x.docx"
    assert vers_unc(None, resoudre) is None and vers_unc("", resoudre) == ""
    assert vers_unc("E:", resoudre) == "E:" and vers_unc("Document1", resoudre) == "Document1"


def test_hors_windows_rien_n_est_traduit():
    # sur la machine de tests (Linux ou poste sans lecteur E:), le résolveur réel ne trouve rien
    assert vers_unc(r"Q:\x\y.docx") == r"Q:\x\y.docx"


def test_fichier_ouvert_par_lettre_retenu_apres_traduction():
    racines = [Racine(r"\\AD-SERVEUR\ETUDES", 1)]
    ouverts = [vers_unc(r"E:\Bargondaga\plan.dwg", resoudre), r"C:\Windows\Fonts\arial.ttf"]
    assert choisir_ouvert(ouverts, "plan.dwg - AutoCAD", None, racines) == (
        r"\\AD-SERVEUR\ETUDES\Bargondaga\plan.dwg"
    )
