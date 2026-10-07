"""Observe le poste : fenêtre au premier plan, processus, titre, inactivité, état de session.

Tout ce qui touche à Windows est ici. Le reste de l'agent ne voit que des
`Observation`. Sur un autre système (tests), `observer()` lève NotImplementedError.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime

from gisuivi_agent import fichiers
from moteur.suivi.types import EtatSession, Observation, Racine

log = logging.getLogger(__name__)

_PROCESSUS_VERROU = {"logonui.exe", "lockapp.exe"}


class Observateur:
    def __init__(
        self, racines: list[Racine] | None = None, lecteurs: dict[str, str] | None = None
    ) -> None:
        self._racines = list(racines or [])
        self._lecteurs = lecteurs or {}
        if sys.platform != "win32":
            raise NotImplementedError("L'observation n'existe que sous Windows.")
        import psutil  # noqa: F401
        import win32api  # noqa: F401
        import win32gui  # noqa: F401
        import win32process  # noqa: F401

        self._cache_processus: dict[int, str] = {}
        self._verrouille = False  # mis à jour par les événements de session (voir icone/principal)

    # -- événements de session, appelés depuis la fenêtre cachée -------------
    def session_verrouillee(self, oui: bool) -> None:
        self._verrouille = oui

    # -- observation ------------------------------------------------------------
    def inactif_depuis_s(self) -> float:
        import win32api

        tick = win32api.GetTickCount()
        derniere = win32api.GetLastInputInfo()
        return max(0.0, (tick - derniere) / 1000.0)

    def _processus(self, hwnd: int) -> tuple[str, int]:
        import psutil
        import win32process

        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if pid not in self._cache_processus:
            try:
                self._cache_processus[pid] = psutil.Process(pid).name()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                self._cache_processus[pid] = "inconnu"
            if len(self._cache_processus) > 500:
                self._cache_processus.clear()
        return self._cache_processus[pid], pid

    def observer(self) -> Observation:
        import win32gui

        maintenant = datetime.now()
        inactif = self.inactif_depuis_s()
        hwnd = win32gui.GetForegroundWindow()
        if self._verrouille:
            return Observation(
                maintenant, "session", None, None, inactif, EtatSession.VERROUILLEE, None
            )
        if not hwnd:
            # Pas de fenêtre au premier plan : écran de verrouillage ou bureau sécurisé
            return Observation(
                maintenant, "session", None, None, inactif, EtatSession.VERROUILLEE, None
            )

        application, pid = self._processus(hwnd)
        if application.lower() in _PROCESSUS_VERROU:
            return Observation(
                maintenant, "session", None, None, inactif, EtatSession.VERROUILLEE, None
            )

        titre = win32gui.GetWindowText(hwnd) or ""
        fichier, chemin = fichiers.identifier(
            application, titre, hwnd, pid, self._racines, self._lecteurs
        )
        return Observation(
            maintenant, application, fichier, chemin, inactif, EtatSession.ACTIVE, hwnd
        )
