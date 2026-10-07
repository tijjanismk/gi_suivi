"""Paramètres de l'agent.

Ordre de priorité : registre HKLM\\SOFTWARE\\GI-CONSEILS\\Suivi (poussé par
GPO) > fichier JSON à côté de l'exécutable (développement et pilote) > défauts.
Sans UrlApi, l'agent fonctionne en mode local : il mesure et conserve, sans envoyer.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from moteur.suivi.types import Parametres, Racine

CLE_REGISTRE = r"SOFTWARE\GI-CONSEILS\Suivi"
# Commun au poste : config.json (posé par l'administrateur) et journal du service.
DOSSIER_DONNEES = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "GiSuivi"
# Propre à chaque utilisateur : tampon et journal de l'agent. Sur un poste partagé, les segments
# d'une personne ne peuvent ni être lus par une autre, ni partir sous son identité.
DOSSIER_UTILISATEUR = (
    Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "GiSuivi"
)


@dataclass
class Config:
    url_api: str | None = None
    intervalle_s: int = 5
    seuil_inactivite_s: int = 300
    envoi_toutes_les_s: int = 180
    racines: list[Racine] = field(default_factory=list)
    correspondance_lecteurs: dict[str, str] = field(default_factory=dict)
    url_mon_activite: str | None = None  # page « mon activité du jour » ; sinon résumé local
    journal_niveau: str = "INFO"
    dossier_donnees: Path = DOSSIER_UTILISATEUR  # tampon.db, agent.log
    avertissements: list[str] = field(default_factory=list)  # journalisés au démarrage

    @property
    def mode_local(self) -> bool:
        return not self.url_api

    def parametres_moteur(self) -> Parametres:
        return Parametres(
            intervalle_s=self.intervalle_s,
            seuil_inactivite_s=self.seuil_inactivite_s,
            correspondance_lecteurs=self.correspondance_lecteurs,
        )


def _depuis_registre() -> dict:
    if sys.platform != "win32":
        return {}
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, CLE_REGISTRE) as k:
            valeurs: dict = {}
            i = 0
            while True:
                try:
                    nom, val, _ = winreg.EnumValue(k, i)
                    valeurs[nom] = val
                    i += 1
                except OSError:
                    break
            return valeurs
    except OSError:
        return {}


def _chemins_fichier() -> tuple[Path, ...]:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return (
        base / "config.json",
        Path(sys.executable).parent / "config.json",
        DOSSIER_DONNEES / "config.json",
    )


def _depuis_fichier(avertissements: list[str], chemins: tuple[Path, ...] | None = None) -> dict:
    """Premier config.json lisible. utf-8-sig : le Bloc-notes et PowerShell 5.1 ajoutent un BOM."""
    for chemin in chemins or _chemins_fichier():
        if chemin.exists():
            try:
                return json.loads(chemin.read_text(encoding="utf-8-sig"))
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                avertissements.append(f"{chemin} ignoré, illisible : {e}")
    return {}


def _racines(valeur) -> list[Racine]:
    """Liste de chaînes « chemin|profondeur » (REG_MULTI_SZ) ou liste de dicts (JSON)."""
    res: list[Racine] = []
    for v in valeur or []:
        if isinstance(v, dict):
            res.append(Racine(v["chemin"], int(v.get("profondeur", 1))))
        else:
            chemin, _, prof = str(v).partition("|")
            res.append(Racine(chemin.strip(), int(prof) if prof.strip() else 1))
    return res


def _lecteurs(valeur) -> dict[str, str]:
    """Accepte « H:=\\\\srv\\gic » (REG_MULTI_SZ) ou un dict JSON."""
    if isinstance(valeur, dict):
        return {k.upper(): v for k, v in valeur.items()}
    res = {}
    for v in valeur or []:
        lettre, _, unc = str(v).partition("=")
        if unc:
            res[lettre.strip().upper()] = unc.strip()
    return res


def charger() -> Config:
    cfg = Config()
    brut = {
        **_depuis_fichier(cfg.avertissements),
        **_depuis_registre(),
    }  # le registre (GPO) l'emporte
    cfg.url_api = brut.get("UrlApi") or brut.get("url_api") or None
    cfg.intervalle_s = int(brut.get("IntervalleS", brut.get("intervalle_s", cfg.intervalle_s)))
    cfg.seuil_inactivite_s = int(
        brut.get("SeuilInactiviteS", brut.get("seuil_inactivite_s", cfg.seuil_inactivite_s))
    )
    cfg.envoi_toutes_les_s = int(
        brut.get("EnvoiToutesLesS", brut.get("envoi_toutes_les_s", cfg.envoi_toutes_les_s))
    )
    cfg.racines = _racines(brut.get("Racines", brut.get("racines")))
    cfg.correspondance_lecteurs = _lecteurs(
        brut.get("CorrespondanceLecteurs", brut.get("correspondance_lecteurs"))
    )
    cfg.url_mon_activite = (
        brut.get("UrlMonActivite")
        or brut.get("url_mon_activite")
        or (f"{cfg.url_api.rstrip('/')}/moi" if cfg.url_api else None)
    )
    cfg.journal_niveau = str(
        brut.get("JournalNiveau", brut.get("journal_niveau", cfg.journal_niveau))
    )
    cfg.dossier_donnees.mkdir(parents=True, exist_ok=True)
    return cfg
