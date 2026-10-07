from gisuivi_agent.fichiers import choisir_ouvert, depuis_titre

from moteur.suivi.types import Racine

RACINES = [
    Racine(r"\\AD-SERVEUR\GIC\MISSIONS_EN_COURS", 1),
    Racine(r"C:\Users\x\Documents\PROJETS", 1),
]
LECTEURS = {"H:": r"\\AD-SERVEUR\GIC"}
PROJET = r"\\AD-SERVEUR\GIC\MISSIONS_EN_COURS\GIC-HYD-ETU-052_Bargondaga"


def test_fichier_hors_racine_jamais_retenu():
    # confidentialité : un fichier personnel ouvert par le logiciel n'est pas remonté
    assert (
        choisir_ouvert(
            [r"C:\Users\x\Desktop\perso.pdf"], "perso.pdf - Acrobat", "perso.pdf", RACINES
        )
        is None
    )


def test_revit_seul_fichier_de_projet_ouvert():
    ouverts = [
        r"C:\Program Files\Autodesk\Revit 2025\fr-FR\RevitAPI.dll",
        PROJET + r"\BIM\digue.rvt",
        PROJET + r"\BIM\digue.slog",
    ]
    assert (
        choisir_ouvert(ouverts, "Autodesk Revit 2025", None, RACINES) == PROJET + r"\BIM\digue.rvt"
    )


def test_plusieurs_fichiers_le_nom_du_titre_l_emporte():
    ouverts = [PROJET + r"\Plans\digue.dwg", PROJET + r"\Plans\seuil.dwg"]
    assert (
        choisir_ouvert(ouverts, "Autodesk AutoCAD 2024 - [seuil.dwg]", "seuil.dwg", RACINES)
        == PROJET + r"\Plans\seuil.dwg"
    )


def test_plusieurs_fichiers_sans_nom_dans_le_titre_rien():
    ouverts = [PROJET + r"\Plans\digue.dwg", PROJET + r"\Plans\seuil.dwg"]
    assert choisir_ouvert(ouverts, "Autodesk AutoCAD 2024", None, RACINES) is None


def test_brouillon_n_emprunte_pas_un_autre_document_du_processus():
    # Word : COM donne « Document1 » ; Rapport.docx, ouvert dans le même processus, n'est pas lui
    ouverts = [PROJET + r"\Rapports\Rapport.docx"]
    assert choisir_ouvert(ouverts, "Document1 - Word", "Document1", RACINES) is None


def test_fichiers_techniques_ignores():
    ouverts = [
        PROJET + r"\Plans\~$digue.dwg",
        PROJET + r"\Plans\digue.dwl",
        PROJET + r"\Plans\desktop.ini",
        PROJET + r"\Plans\digue.dwg",
    ]
    assert choisir_ouvert(ouverts, "AutoCAD", None, RACINES) == PROJET + r"\Plans\digue.dwg"


def test_lecteur_reseau_ramene_a_la_racine_unc():
    assert (
        choisir_ouvert(
            [r"H:\MISSIONS_EN_COURS\GIC-HYD-ETU-052_Bargondaga\SIG\carte.qgz"],
            "QGIS",
            None,
            RACINES,
            LECTEURS,
        )
        is not None
    )


def test_meme_fichier_vu_deux_fois_compte_pour_un():
    # open_files et ligne de commande donnent le même fichier, écrit différemment
    ouverts = [PROJET + r"\BIM\digue.rvt", PROJET.lower() + r"\bim\digue.rvt"]
    assert choisir_ouvert(ouverts, "Autodesk Revit 2025", None, RACINES) is not None


def test_enumeration_en_arriere_plan_lue_a_l_observation_suivante(monkeypatch):
    import threading

    from gisuivi_agent import fichiers

    feu = threading.Event()

    def lente(pid):
        feu.wait(2)  # simule les 0,3 à 1 s de psutil
        return [PROJET + r"\BIM\digue.rvt"]

    monkeypatch.setattr(fichiers, "_ouverts_du_processus", lente)
    monkeypatch.setattr(fichiers, "_cache_ouverts", {})
    monkeypatch.setattr(fichiers, "_en_cours", set())
    assert (
        fichiers.depuis_processus(42, "Autodesk Revit 2025", None, RACINES, None) is None
    )  # ne bloque pas
    feu.set()
    for _ in range(100):
        if not fichiers._en_cours:
            break
        threading.Event().wait(0.01)
    assert (
        fichiers.depuis_processus(42, "Autodesk Revit 2025", None, RACINES, None)
        == PROJET + r"\BIM\digue.rvt"
    )


def test_titre_revit_donne_le_nom():
    assert depuis_titre(
        "Revit.exe", "Autodesk Revit 2025 - [digue.rvt - Plan d'étage : Niveau 1]"
    ) == ("digue.rvt", None)
