"""Noms lisibles des logiciels : « Microsoft Word » plutôt que WINWORD.EXE.

L'agent transmet le nom de l'exécutable (c'est ce qui est stocké, et ce que l'API renvoie) ;
les écrans affichent le nom du logiciel. Les petits programmes de Windows (menu Démarrer,
recherche, sélecteurs…) sont regroupés sous un seul libellé. Pour ajouter ou corriger un nom
sans redéployer : paramètre `noms_applications` dans l'administration, par exemple
{"covadis.exe": "Covadis"}.
"""

from __future__ import annotations

from collections.abc import Iterable

WINDOWS = "Windows (bureau, menus, recherche)"

NOMS: dict[str, str] = {
    # Bureautique
    "winword.exe": "Microsoft Word",
    "excel.exe": "Microsoft Excel",
    "powerpnt.exe": "Microsoft PowerPoint",
    "outlook.exe": "Microsoft Outlook",
    "olk.exe": "Microsoft Outlook",
    "msaccess.exe": "Microsoft Access",
    "onenote.exe": "Microsoft OneNote",
    "mspub.exe": "Microsoft Publisher",
    "winproj.exe": "Microsoft Project",
    "visio.exe": "Microsoft Visio",
    "teams.exe": "Microsoft Teams",
    "ms-teams.exe": "Microsoft Teams",
    "soffice.bin": "LibreOffice",
    "notepad.exe": "Bloc-notes",
    "notepad++.exe": "Notepad++",
    # PDF
    "acrobat.exe": "Adobe Acrobat",
    "acrord32.exe": "Adobe Acrobat Reader",
    "foxitpdfeditor.exe": "Foxit PDF",
    "foxitphantom.exe": "Foxit PDF",
    "foxitpdfreader.exe": "Foxit PDF Reader",
    "sumatrapdf.exe": "SumatraPDF",
    # Navigateurs
    "msedge.exe": "Microsoft Edge",
    "chrome.exe": "Google Chrome",
    "firefox.exe": "Mozilla Firefox",
    "opera.exe": "Opera",
    "brave.exe": "Brave",
    # Métier : dessin, SIG, calcul
    "acad.exe": "AutoCAD",
    "revit.exe": "Revit",
    "sketchup.exe": "SketchUp",
    "qgis-bin.exe": "QGIS",
    "qgis-ltr-bin.exe": "QGIS",
    "arcmap.exe": "ArcMap",
    "arcgispro.exe": "ArcGIS Pro",
    "mapinfow.exe": "MapInfo",
    "googleearth.exe": "Google Earth",
    "epanet2w.exe": "EPANET",
    "ras.exe": "HEC-RAS",
    "robot.exe": "Robot Structural Analysis",
    # Communication, assistants
    "claude.exe": "Claude",
    "chatgpt.exe": "ChatGPT",
    "whatsapp.exe": "WhatsApp",
    "zoom.exe": "Zoom",
    "anydesk.exe": "AnyDesk",
    "teamviewer.exe": "TeamViewer",
    # Outils
    "explorer.exe": "Explorateur de fichiers",
    "7zg.exe": "7-Zip",
    "7zfm.exe": "7-Zip",
    "winrar.exe": "WinRAR",
    "idman.exe": "Internet Download Manager",
    "photos.exe": "Photos",
    "mspaint.exe": "Paint",
    "snippingtool.exe": "Outil Capture d'écran",
    "calc.exe": "Calculatrice",
    "calculatorapp.exe": "Calculatrice",
    "mstsc.exe": "Bureau à distance",
    "taskmgr.exe": "Gestionnaire des tâches",
    "systemsettings.exe": "Paramètres Windows",
    "fontview.exe": "Aperçu des polices",
    "code.exe": "Visual Studio Code",
    "windowsterminal.exe": "Terminal Windows",
    "powershell.exe": "PowerShell",
    "pwsh.exe": "PowerShell",
    "cmd.exe": "Invite de commandes",
    "gesco-app.exe": "Gesco",
    # Pseudo-application de l'agent : poste inactif ou verrouillé
    "session": "Session Windows",
}

# Petits programmes de l'interface de Windows : regroupés, ils n'apprennent rien un par un
for _exe in (
    "shellexperiencehost.exe",
    "shellhost.exe",
    "startmenuexperiencehost.exe",
    "searchhost.exe",
    "searchapp.exe",
    "searchui.exe",
    "pickerhost.exe",
    "lockapp.exe",
    "applicationframehost.exe",
    "textinputhost.exe",
    "sihost.exe",
    "dwm.exe",
    "ctfmon.exe",
    "rundll32.exe",
    "consent.exe",
):
    NOMS[_exe] = WINDOWS


def table() -> dict[str, str]:
    """Noms du code, complétés ou corrigés par le paramètre `noms_applications`."""
    from suivi.services import parametre

    supplement = parametre("noms_applications", {}) or {}
    return {**NOMS, **{str(k).lower(): str(v) for k, v in supplement.items()}}


def nom_application(executable: str, noms: dict[str, str] | None = None) -> str:
    """WINWORD.EXE → Microsoft Word ; inconnu : le nom sans « .exe » (IDMan.exe → IDMan)."""
    if not executable:
        return ""
    noms = noms if noms is not None else table()
    connu = noms.get(executable.lower())
    if connu:
        return connu
    return executable[:-4] if executable.lower().endswith(".exe") else executable


def regrouper(lignes: Iterable[dict], noms: dict[str, str] | None = None) -> list[dict]:
    """[{application: exe, duree_s}] → mêmes lignes au nom lisible, fusionnées, triées."""
    noms = noms if noms is not None else table()
    totaux: dict[str, dict] = {}
    for ligne in lignes:
        nom = nom_application(ligne["application"], noms)
        t = totaux.setdefault(nom, {"application": nom, "duree_s": 0, "executables": []})
        t["duree_s"] += int(ligne["duree_s"])
        t["executables"].append(ligne["application"])
    return sorted(totaux.values(), key=lambda t: -t["duree_s"])
