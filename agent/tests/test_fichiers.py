import pytest
from gisuivi_agent.fichiers import depuis_titre

CAS = [
    ("WINWORD.EXE", "rapport_APD_Bargondaga.docx - Word", ("rapport_APD_Bargondaga.docx", None)),
    ("WINWORD.EXE", "● Lettre de soumission.docx  -  Word", ("Lettre de soumission.docx", None)),
    ("WINWORD.EXE", "Document1 - Word", ("Document1", None)),
    (
        "EXCEL.EXE",
        "Offre financière SOMAPEP.xlsx [Mode de compatibilité] - Excel",
        ("Offre financière SOMAPEP.xlsx", None),
    ),
    ("EXCEL.EXE", "Classeur2 - Excel", ("Classeur2", None)),
    ("POWERPNT.EXE", "Présentation1 - PowerPoint", ("Présentation1", None)),
    (
        "acad.exe",
        r"Autodesk AutoCAD 2024 - [D:\GIC\MISSIONS_EN_COURS\GIC-HYD-ETU-052_x\Plans\digue.dwg]",
        ("digue.dwg", r"D:\GIC\MISSIONS_EN_COURS\GIC-HYD-ETU-052_x\Plans\digue.dwg"),
    ),
    ("acad.exe", "Autodesk AutoCAD 2024 - [Dessin1.dwg]", ("Dessin1.dwg", None)),
    (
        "Acrobat.exe",
        r"TDR_Etude_Ouvrages_de_Recharge_de_nappe_VF.pdf - Adobe Acrobat Reader (64-bit)",
        ("TDR_Etude_Ouvrages_de_Recharge_de_nappe_VF.pdf", None),
    ),
    ("qgis-bin.exe", r"Bargondaga — QGIS", (None, None)),
    (
        "qgis-bin.exe",
        r"\\AD-SERVEUR\GIC\MISSIONS_EN_COURS\A-CODER_Bargondaga\SIG\projet.qgz — QGIS",
        ("projet.qgz", r"\\AD-SERVEUR\GIC\MISSIONS_EN_COURS\A-CODER_Bargondaga\SIG\projet.qgz"),
    ),
    (
        "notepad.exe",
        r"C:\Users\x\Desktop\notes.txt - Bloc-notes",
        ("notes.txt", r"C:\Users\x\Desktop\notes.txt"),
    ),
    ("explorer.exe", "MISSIONS_EN_COURS", (None, None)),
    ("chrome.exe", "Banque mondiale — Appels d'offres - Google Chrome", (None, None)),
    # PDF dans un navigateur : le nom seul (ADR 0003), jamais l'adresse ni le titre de page
    ("msedge.exe", "rapport.pdf - Microsoft Edge", ("rapport.pdf", None)),
    ("chrome.exe", "TDR - Bargondaga.pdf - Google Chrome", ("TDR - Bargondaga.pdf", None)),
    (
        "msedge.exe",
        "TDR_052.pdf et 2 pages de plus - Profil 1 - Microsoft​ Edge",
        ("TDR_052.pdf", None),
    ),
    ("chrome.exe", "127.0.0.1:8000/media/tdr.pdf - Google Chrome", (None, None)),
    ("chrome.exe", "Guide des procédures.pdf.html - Google Chrome", (None, None)),
    ("OUTLOOK.EXE", "Boîte de réception - o.hassane@gi-conseils.ml - Outlook", (None, None)),
    ("WINWORD.EXE", "", (None, None)),
]


@pytest.mark.parametrize("application,titre,attendu", CAS)
def test_depuis_titre(application, titre, attendu):
    assert depuis_titre(application, titre) == attendu
