"""Types échangés entre l'agent, le moteur et le serveur."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum


class EtatSession(StrEnum):
    ACTIVE = "active"
    VERROUILLEE = "verrouillee"
    VEILLE = "veille"
    FERMEE = "fermee"


class Etat(StrEnum):
    ACTIF = "ACTIF"
    INACTIF = "INACTIF"


@dataclass(frozen=True)
class Observation:
    """Ce que l'agent voit toutes les cinq secondes."""

    instant: datetime
    application: str  # nom du processus, ex. "WINWORD.EXE"
    fichier: str | None  # nom du fichier ouvert, ou None
    chemin: str | None  # chemin complet si connu
    inactif_depuis_s: float  # secondes depuis la dernière action clavier/souris
    session: EtatSession = EtatSession.ACTIVE
    fenetre_id: int | None = None  # identifiant de la fenêtre, pour suivre un brouillon renommé

    @property
    def est_brouillon(self) -> bool:
        return self.fichier is not None and self.chemin is None


@dataclass
class Segment:
    """Une période continue sur une même application et un même fichier."""

    debut: datetime
    fin: datetime
    application: str
    fichier: str | None
    chemin: str | None
    etat: Etat = Etat.ACTIF
    fenetre_id: int | None = None

    @property
    def duree_s(self) -> float:
        return (self.fin - self.debut).total_seconds()

    def vers_dict(self) -> dict:
        d = asdict(self)
        d["debut"] = self.debut.isoformat()
        d["fin"] = self.fin.isoformat()
        d["etat"] = self.etat.value
        d["duree_s"] = round(self.duree_s, 1)
        return d


@dataclass(frozen=True)
class Racine:
    """Racine de classement : les dossiers de projet sont à `profondeur` niveaux sous `chemin`."""

    chemin: str  # UNC canonique, ex. \\AD-SERVEUR\GIC\MISSIONS_EN_COURS
    profondeur: int = 1
    motif_code: str = r"^(GIC-[A-Z]{3}-[A-Z]{3}-\d{3}|\d{4}-[A-Z0-9]+-\d{3})"


@dataclass(frozen=True)
class RegleException:
    """Rattachement hors convention, saisi par la direction depuis la file « à classer »."""

    motif: str  # un chemin, un dossier (préfixe) ou un mot-clé
    type: str  # "chemin" | "prefixe" | "mot_cle"
    dossier_chemin: str  # le dossier de projet auquel rattacher
    code: str | None = None


@dataclass(frozen=True)
class Classement:
    statut: str  # "dossier" | "a_classer" | "brouillon" | "application" | "ignore"
    racine: str | None = None
    dossier_chemin: str | None = None  # chemin UNC du dossier de projet
    dossier_nom: str | None = None
    code: str | None = None
    par_exception: bool = False  # rattaché par une RegleException, pas par la convention


@dataclass
class Parametres:
    intervalle_s: int = 5
    seuil_inactivite_s: int = 300
    duree_max_segment_s: int = 300
    extensions_ignorees: tuple[str, ...] = (".tmp", ".bak", ".dwl", ".dwl2", ".asd", ".wbk")
    prefixes_ignores: tuple[str, ...] = ("~$",)
    navigateurs: tuple[str, ...] = (
        "chrome.exe",
        "msedge.exe",
        "firefox.exe",
        "brave.exe",
        "opera.exe",
    )
    correspondance_lecteurs: dict[str, str] = field(
        default_factory=dict
    )  # {"H:": r"\\AD-SERVEUR\GIC"}
