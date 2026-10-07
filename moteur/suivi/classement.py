"""Rattache un chemin de fichier à un dossier de projet par convention de dossiers.

Un projet = un dossier Windows situé à `profondeur` niveaux sous une racine.
Tout fichier dedans, à n'importe quelle profondeur, appartient au projet. Le
code est lu dans le nom du dossier (GIC-HYD-ETU-052_... ou 2026-SOMAPEP-001_...).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

from .types import Classement, Observation, Parametres, Racine, RegleException

_SEP = re.compile(r"[\\/]+")
_EXTENSION = re.compile(r"\.[A-Za-z0-9]{1,5}$")


def normaliser_chemin(chemin: str, correspondance_lecteurs: dict[str, str] | None = None) -> str:
    """Rend un chemin comparable : UNC, antislashs simples, minuscules, sans accents.

    `H:\\Dossier\\f.docx` avec {"H:": "\\\\AD-SERVEUR\\GIC"}
    -> `\\\\ad-serveur\\gic\\dossier\\f.docx`.
    """
    c = chemin.strip()
    if correspondance_lecteurs and len(c) >= 2 and c[1] == ":":
        unc = correspondance_lecteurs.get(c[:2].upper())
        if unc:
            c = unc.rstrip("\\/") + c[2:]
    c = _SEP.sub(lambda _m: "\\", c)
    if c.startswith("\\") and not c.startswith("\\\\"):
        c = "\\" + c  # UNC dont le double antislash a été réduit
    c = unicodedata.normalize("NFKD", c).encode("ascii", "ignore").decode()
    return c.lower().rstrip("\\")


def _niveaux(chemin_norm: str) -> list[str]:
    return [x for x in chemin_norm.split("\\") if x]


def est_technique(nom_ou_chemin: str, p: Parametres | None = None) -> bool:
    """Fichier de travail d'un logiciel (~$rapport.docx, plan.dwl, x.tmp) : jamais un document."""
    p = p or Parametres()
    nom = _SEP.split(nom_ou_chemin.strip())[-1].lower()
    return nom.startswith(p.prefixes_ignores) or nom.endswith(p.extensions_ignorees)


def _par_exception(
    c: str, exceptions: Iterable[RegleException], lecteurs: dict[str, str] | None
) -> RegleException | None:
    """Règle la plus précise : chemin exact, puis plus long préfixe, puis plus long mot-clé."""
    exactes, prefixes, mots = [], [], []
    for r in exceptions:
        if r.type == "mot_cle":
            m = normaliser_chemin(r.motif)
            if m and m in c:
                mots.append((len(m), r))
            continue
        m = normaliser_chemin(r.motif, lecteurs)
        if r.type == "chemin" and c == m:
            exactes.append(r)
        elif r.type == "prefixe" and (c == m or c.startswith(m + "\\")):
            prefixes.append((len(m), r))
    if exactes:
        return exactes[0]
    for candidats in (prefixes, mots):
        if candidats:
            return max(candidats, key=lambda x: x[0])[1]
    return None


def classer_chemin(
    chemin: str | None,
    racines: Iterable[Racine],
    correspondance_lecteurs: dict[str, str] | None = None,
    exceptions: Iterable[RegleException] = (),
) -> Classement:
    if not chemin:
        return Classement("application")
    if est_technique(chemin):
        return Classement("ignore")
    res = _par_convention(chemin, racines, correspondance_lecteurs)
    if res.statut != "a_classer":
        return res
    regle = _par_exception(
        normaliser_chemin(chemin, correspondance_lecteurs), exceptions, correspondance_lecteurs
    )
    if regle is None:
        return res
    dossier = normaliser_chemin(regle.dossier_chemin, correspondance_lecteurs)
    return Classement(
        "dossier",
        racine=res.racine,
        dossier_chemin=dossier,
        dossier_nom=_niveaux(dossier)[-1] if _niveaux(dossier) else None,
        code=regle.code,
        par_exception=True,
    )


def _par_convention(
    chemin: str, racines: Iterable[Racine], correspondance_lecteurs: dict[str, str] | None
) -> Classement:
    c = normaliser_chemin(chemin, correspondance_lecteurs)
    niveaux = _niveaux(c)
    meilleure: tuple[int, Racine, str] | None = None
    for r in racines:
        rn = normaliser_chemin(r.chemin, correspondance_lecteurs)
        if c == rn or c.startswith(rn + "\\"):
            if meilleure is None or len(rn) > meilleure[0]:
                meilleure = (len(rn), r, rn)
    if meilleure is None:
        return Classement("a_classer")
    _, racine, rn = meilleure
    reste = niveaux[len(_niveaux(rn)) :]
    if len(reste) <= racine.profondeur:
        # Fichier posé directement dans la racine ou au-dessus du niveau projet
        return Classement("a_classer", racine=racine.chemin)
    dossier = reste[: racine.profondeur]
    dossier_chemin = "\\".join([rn, *dossier])
    nom = dossier[-1]
    m = re.match(racine.motif_code, nom, flags=re.IGNORECASE)
    return Classement(
        "dossier",
        racine=racine.chemin,
        dossier_chemin=dossier_chemin,
        dossier_nom=nom,
        code=m.group(1).upper() if m else None,
    )


def classer_observation(
    obs: Observation,
    racines: Iterable[Racine],
    correspondance_lecteurs: dict[str, str] | None = None,
    exceptions: Iterable[RegleException] = (),
) -> Classement:
    if obs.fichier and est_technique(obs.fichier):
        return Classement("ignore")
    if obs.fichier and obs.chemin is None:
        # Brouillon = document jamais enregistré (Document1, Classeur2, Dessin1 : pas d'extension).
        # Un nom avec extension mais sans chemin (PDF lu dans un navigateur) est un fichier connu
        # qu'on ne sait pas rattacher : à classer.
        return (
            Classement("a_classer") if _EXTENSION.search(obs.fichier) else Classement("brouillon")
        )
    return classer_chemin(obs.chemin, racines, correspondance_lecteurs, exceptions)
