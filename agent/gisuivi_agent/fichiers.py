"""Devine le fichier ouvert dans la fenêtre active.

Trois sources, dans l'ordre (ADR 0003) : l'automation COM d'Office (chemin
exact), le titre de la fenêtre (chemin si l'application l'affiche), puis les
fichiers que le processus garde ouverts, limités à ceux qui sont sous une
racine. Le choix parmi les fichiers ouverts et les règles par titre sont des
fonctions pures, testées sans Windows.
Les navigateurs ne sont jamais identifiés : seul le processus compte.
"""

from __future__ import annotations

import logging
import re
import sys
import threading
import time
from collections.abc import Iterable

from moteur.suivi.classement import classer_chemin, normaliser_chemin
from moteur.suivi.types import Parametres, Racine

log = logging.getLogger(__name__)

_NAVIGATEURS = {"chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe", "iexplore.exe"}
_OFFICE_COM = {
    "winword.exe": "Word.Application",
    "excel.exe": "Excel.Application",
    "powerpnt.exe": "PowerPoint.Application",
    "winproj.exe": "MSProject.Application",
}
# Liste fermée pour le titre seul ; les autres logiciels passent par les fichiers ouverts.
# Ajouts ADR 0003 : Revit, IFC, Navisworks, SketchUp, ArchiCAD, MicroStation, Google Earth,
# SIG (GeoPackage, ArcGIS), Visio, Access, DWF.
_EXT = (
    r"\.(docx?|docm|dotx?|xlsx?|xlsm|xlsb|csv|pptx?|pptm|pdf|dwg|dxf|dwt|qgz|qgs|shp|mpp|txt|rtf|odt|ods|odp"
    r"|jpg|jpeg|png|tif|tiff|zip|rar|7z|xml|json|md"
    r"|rvt|rfa|rte|ifc|nwd|nwc|nwf|skp|pln|dgn|kmz|kml|gpkg|aprx|mxd|vsdx?|accdb|mdb|dwfx?)"
)
_CHEMIN = re.compile(
    r"([A-Za-z]:\\[^\"<>|?*\[\]\r\n]+?" + _EXT + r"|\\\\[^\"<>|?*\[\]\r\n]+?" + _EXT + r")",
    re.IGNORECASE,
)
_NOM = re.compile(r"([^\\/:*?\"<>|\[\]\r\n]+?" + _EXT + r")", re.IGNORECASE)
# Documents jamais enregistrés : « Document1 - Word », « Dessin1 - AutoCAD »
_BROUILLON = (
    r"^(Document|Classeur|Présentation|Presentation|Dessin|Drawing|Sans titre|Untitled|Projet)\d*$"
)
_SEPARATEURS = (" - ", " – ", " — ", " | ", " – ")


def _nettoyer(titre: str) -> str:
    t = titre.strip()
    for prefixe in ("● ", "* ", "•"):
        if t.startswith(prefixe):
            t = t[len(prefixe) :]
    return (
        t.replace("[Mode de compatibilité]", "")
        .replace("[Compatibility Mode]", "")
        .replace("[Lecture seule]", "")
        .replace("[Read-Only]", "")
        .strip()
    )


# PDF lu dans un navigateur : « TDR - Bargondaga.pdf - Google Chrome ».
# Pas de « / » ni de « : » dans le nom : jamais une adresse.
# Edge ajoute « et 2 pages de plus » (« and 2 more pages ») quand plusieurs onglets sont groupés.
_PDF_NAVIGATEUR = re.compile(
    r"^([^\\/:*?\"<>|]+?\.pdf)(?=$|\s+[-–—|]\s|\s+(?:et|and)\s+\d+\s)", re.IGNORECASE
)


def depuis_titre(application: str, titre: str) -> tuple[str | None, str | None]:
    """(fichier, chemin) déduits du titre, ou (None, None). Fonction pure.

    Navigateurs : seul le nom d'un PDF est retenu (ADR 0003), jamais l'adresse ni le titre de page.
    """
    app = application.lower()
    if not titre:
        return None, None
    if app in _NAVIGATEURS:
        m = _PDF_NAVIGATEUR.match(_nettoyer(titre))
        return (m.group(1).strip(), None) if m else (None, None)
    t = _nettoyer(titre)

    # Chemin complet affiché (Acrobat, Bloc-notes « C:\... », AutoCAD avec chemin, explorateur)
    m = _CHEMIN.search(t)
    if m:
        chemin = m.group(1).rstrip(" .")
        return chemin.replace("/", "\\").split("\\")[-1], chemin

    # Nom de fichier seul dans le titre : « rapport.docx - Word », « Dessin1.dwg - AutoCAD »
    m = _NOM.search(t)
    if m:
        nom = m.group(1).strip()
        # On retire l'éventuel suffixe « - Application » collé au nom
        for sep in _SEPARATEURS:
            if sep in nom:
                nom = nom.split(sep)[0].strip()
        return nom, None

    # Brouillons Office / AutoCAD sans extension : « Document1 - Word », « Dessin1 - AutoCAD »
    for sep in _SEPARATEURS:
        if sep in t:
            premier = t.split(sep)[0].strip()
            if re.match(
                _BROUILLON,
                premier,
                re.IGNORECASE,
            ):
                return premier, None
            if app in _OFFICE_COM and premier and len(premier) < 120:
                return premier, None
            break
    return None, None


def depuis_com(application: str) -> tuple[str | None, str | None]:
    """Chemin exact du document actif via COM Office. (None, None) si indisponible."""
    if sys.platform != "win32":
        return None, None
    prog = _OFFICE_COM.get(application.lower())
    if not prog:
        return None, None
    try:
        import pythoncom
        import win32com.client

        pythoncom.CoInitialize()
        try:
            appli = win32com.client.GetActiveObject(prog)
            if prog == "Word.Application":
                doc = appli.ActiveDocument
            elif prog == "Excel.Application":
                doc = appli.ActiveWorkbook
            elif prog == "PowerPoint.Application":
                doc = appli.ActivePresentation
            else:
                doc = appli.ActiveProject
            if doc is None:
                return None, None
            chemin = str(doc.FullName or "")
            nom = str(doc.Name or "")
            if chemin and ("\\" in chemin or "/" in chemin):
                return nom, chemin
            return nom or None, None  # non enregistré : brouillon
        finally:
            pythoncom.CoUninitialize()
    except Exception as e:  # noqa: BLE001 — COM lève des erreurs variées ; on retombe sur le titre
        log.debug("COM %s indisponible : %s", prog, e)
        return None, None


_PARAMETRES = Parametres()
# Fichiers que les logiciels tiennent ouverts sans que ce soit le document de travail
_TECHNIQUES = (
    *_PARAMETRES.extensions_ignorees,
    ".slog",
    ".lck",
    ".lock",
    ".log",
    ".ini",
    ".ldb",
    ".laccdb",
)
_NOMS_TECHNIQUES = {"desktop.ini", "thumbs.db"}


def _nom(chemin: str) -> str:
    return chemin.replace("/", "\\").rstrip("\\").rsplit("\\", 1)[-1]


def choisir_ouvert(
    candidats: Iterable[str],
    titre: str,
    nom_indique: str | None,
    racines: Iterable[Racine],
    lecteurs: dict[str, str] | None = None,
) -> str | None:
    """Parmi les fichiers ouverts par un processus, celui de la fenêtre. Fonction pure.

    Seuls les fichiers sous une racine sont considérés : un fichier personnel n'est jamais
    retenu (ADR 0003). Parmi eux : celui dont le nom figure dans le titre ; sinon, si le
    titre ou COM n'indique aucun nom, le seul restant ; sinon aucun.
    """
    racines = list(racines)
    retenus: dict[str, str] = {}
    for c in candidats:
        nom = _nom(c).lower()
        if (
            not nom
            or nom in _NOMS_TECHNIQUES
            or nom.startswith(_PARAMETRES.prefixes_ignores)
            or nom.endswith(_TECHNIQUES)
        ):
            continue
        if classer_chemin(c, racines, lecteurs).racine is None:
            continue
        retenus.setdefault(normaliser_chemin(c, lecteurs), c)
    if not retenus:
        return None
    t = titre.lower()
    dans_titre = [c for c in retenus.values() if _nom(c).lower() in t]
    if dans_titre:
        return max(dans_titre, key=lambda c: len(_nom(c)))
    if nom_indique is None and len(retenus) == 1:
        return next(iter(retenus.values()))
    return None


# L'énumération coûte 0,3 à 1 s (psutil parcourt toutes les poignées du système) : elle tourne
# en arrière-plan, une fois par (processus, titre), et l'observation suivante lit le résultat.
_cache_ouverts: dict[tuple[int, str], str | None] = {}
_en_cours: set[tuple[int, str]] = set()
_verrou_ouverts = threading.Lock()


# Lettres de lecteur réseau → chemin UNC, lues auprès de Windows (comme « net use ») et gardées
# 5 minutes. Un fichier ouvert par E:\ETUDES\… est ainsi transmis \\AD-SERVEUR\ETUDES\… et se
# rattache à sa racine sans aucun réglage sur le poste.
_lecteurs_reseau: dict[str, tuple[float, str | None]] = {}
_DUREE_LECTEURS_S = 300


def _connexion_reseau(lettre: str) -> str | None:
    if sys.platform != "win32":
        return None
    maintenant = time.monotonic()
    connu = _lecteurs_reseau.get(lettre)
    if connu and maintenant - connu[0] < _DUREE_LECTEURS_S:
        return connu[1]
    try:
        import win32wnet

        unc = win32wnet.WNetGetConnection(lettre) or None
    except Exception:  # noqa: BLE001 — lecteur local ou déconnecté : pas de chemin réseau
        unc = None
    _lecteurs_reseau[lettre] = (maintenant, unc)
    return unc


def vers_unc(chemin: str | None, resoudre=None) -> str | None:
    """E:\\ETUDES\\x.docx → \\\\AD-SERVEUR\\ETUDES\\x.docx si E: est un lecteur réseau."""
    if not chemin or len(chemin) < 3 or chemin[1] != ":" or chemin[2] not in "\\/":
        return chemin
    unc = (resoudre or _connexion_reseau)(chemin[:2].upper())
    return unc.rstrip("\\/") + chemin[2:] if unc else chemin


def _ouverts_du_processus(pid: int) -> list[str]:
    import psutil

    p = psutil.Process(pid)
    chemins = [vers_unc(f.path) for f in p.open_files()]
    try:
        # Fichier passé au double-clic : « revit.exe C:\...\projet.rvt »
        chemins += [
            vers_unc(a)
            for a in p.cmdline()[1:]
            if len(a) > 3 and (a[1:3] == ":\\" or a.startswith("\\\\"))
        ]
    except psutil.Error:
        pass
    return chemins


def depuis_processus(
    pid: int,
    titre: str,
    nom_indique: str | None,
    racines: list[Racine],
    lecteurs: dict[str, str] | None,
) -> str | None:
    """Fichier de projet ouvert par le processus, ou None tant que l'énumération n'a pas rendu.

    Ne bloque jamais la boucle : la première demande lance l'énumération en arrière-plan,
    les suivantes (5 s plus tard) lisent le résultat mis en cache.
    """
    cle = (pid, titre)
    with _verrou_ouverts:
        if cle in _cache_ouverts:
            return _cache_ouverts[cle]
        if cle in _en_cours or _en_cours:  # une énumération à la fois
            return None
        _en_cours.add(cle)

    def enumerer() -> None:
        chemin = None
        try:
            chemin = choisir_ouvert(
                _ouverts_du_processus(pid), titre, nom_indique, racines, lecteurs
            )
        except Exception as e:  # noqa: BLE001 — accès refusé, processus disparu… : on s'en passe
            log.debug("Fichiers ouverts du processus %s indisponibles : %s", pid, e)
        with _verrou_ouverts:
            if len(_cache_ouverts) > 500:
                _cache_ouverts.clear()
            _cache_ouverts[cle] = chemin
            _en_cours.discard(cle)

    threading.Thread(target=enumerer, name="fichiers-ouverts", daemon=True).start()
    return None


def identifier(
    application: str,
    titre: str,
    hwnd: int | None = None,
    pid: int | None = None,
    racines: list[Racine] | None = None,
    lecteurs: dict[str, str] | None = None,
) -> tuple[str | None, str | None]:
    fichier, chemin = depuis_com(application)
    if chemin:
        return fichier, vers_unc(chemin)
    f2, c2 = depuis_titre(application, titre)
    if c2:
        return (fichier or f2), vers_unc(c2)
    if pid and racines and application.lower() not in _NAVIGATEURS:
        c3 = depuis_processus(pid, titre, fichier or f2, racines, lecteurs)
        if c3:
            return _nom(c3), c3
    return (fichier or f2), None
