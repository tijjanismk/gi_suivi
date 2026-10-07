"""Service de supervision (G06) : garde un agent dans chaque session ouverte.

Toutes les 15 s, le service liste les sessions actives (verrouillées comprises,
déconnectées exclues) et les processus gisuivi-agent.exe. Dans chaque session
active sans agent, il lance l'agent avec le jeton de l'utilisateur de la session
(WTSQueryUserToken + CreateProcessAsUser) : le service tourne en LocalSystem,
l'agent toujours sous l'identité de la personne. Il couvre ainsi l'ouverture de
session (CONTROLE n° 6) et l'agent tué (n° 8). Il ne mesure rien lui-même.

Même exécutable que l'agent, lancé avec `--service` par le gestionnaire de services.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from collections.abc import Iterable
from pathlib import Path

from gisuivi_agent.config import DOSSIER_DONNEES

NOM_SERVICE = "GiSuivi"
NOM_EXE = "gisuivi-agent.exe"
INTERVALLE_S = 15

log = logging.getLogger("gisuivi.service")


def sessions_a_pourvoir(actives: Iterable[int], avec_agent: Iterable[int]) -> list[int]:
    """Sessions actives sans agent. La session 0 (services) n'en reçoit jamais. Fonction pure."""
    deja = set(avec_agent)
    return sorted(s for s in set(actives) if s != 0 and s not in deja)


def _sessions_actives() -> list[int]:
    import win32ts

    return [
        s["SessionId"]
        for s in win32ts.WTSEnumerateSessions(win32ts.WTS_CURRENT_SERVER_HANDLE)
        if s["State"] == win32ts.WTSActive
    ]


def _sessions_avec_agent() -> list[int]:
    import win32ts

    # (SessionId, ProcessId, ProcessName, UserSid)
    return [
        p[0]
        for p in win32ts.WTSEnumerateProcesses(win32ts.WTS_CURRENT_SERVER_HANDLE)
        if str(p[2]).lower() == NOM_EXE
    ]


def _lancer_dans_session(session_id: int, exe: Path) -> int:
    import win32con
    import win32process
    import win32profile
    import win32ts

    jeton = win32ts.WTSQueryUserToken(session_id)  # jeton filtré (non élevé) de la personne
    try:
        env = win32profile.CreateEnvironmentBlock(jeton, False)
        si = win32process.STARTUPINFO()
        si.lpDesktop = "winsta0\\default"
        processus, fil, pid, _ = win32process.CreateProcessAsUser(
            jeton,
            str(exe),
            None,
            None,
            None,
            False,
            win32con.CREATE_UNICODE_ENVIRONMENT,
            env,
            str(exe.parent),
            si,
        )
        processus.Close()
        fil.Close()
        return pid
    finally:
        jeton.Close()


def superviser(exe: Path) -> None:
    """Un tour : lance l'agent là où il manque. L'échec d'une session n'arrête pas les autres."""
    for session in sessions_a_pourvoir(_sessions_actives(), _sessions_avec_agent()):
        try:
            pid = _lancer_dans_session(session, exe)
            log.info("Agent lancé dans la session %s (processus %s).", session, pid)
        except Exception as e:  # noqa: BLE001 — session fermée entre-temps, jeton refusé… : on réessaie au tour suivant
            log.warning("Lancement de l'agent dans la session %s impossible : %s", session, e)


def _journal() -> None:
    DOSSIER_DONNEES.mkdir(parents=True, exist_ok=True)
    h = logging.handlers.RotatingFileHandler(
        DOSSIER_DONNEES / "service.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8"
    )
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s : %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[h])


def _classe_service():
    import win32event
    import win32service
    import win32serviceutil

    class ServiceGiSuivi(win32serviceutil.ServiceFramework):
        _svc_name_ = NOM_SERVICE
        _svc_display_name_ = "GI-Suivi - supervision de l'agent"
        _svc_description_ = (
            "Garde l'agent GI-Suivi ouvert dans chaque session (relance s'il est fermé). "
            "Ne mesure rien lui-même."
        )

        def __init__(self, args) -> None:
            super().__init__(args)
            self.arret = win32event.CreateEvent(None, True, False, None)

        def SvcStop(self) -> None:  # noqa: N802 — nom imposé par pywin32
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            win32event.SetEvent(self.arret)

        def SvcDoRun(self) -> None:  # noqa: N802
            _journal()
            exe = Path(sys.executable).with_name(NOM_EXE)
            log.info("Service démarré ; agent surveillé : %s", exe)
            while True:
                superviser(exe)
                if (
                    win32event.WaitForSingleObject(self.arret, INTERVALLE_S * 1000)
                    == win32event.WAIT_OBJECT_0
                ):
                    break
            log.info("Service arrêté.")

    return ServiceGiSuivi


def executer_service() -> int:
    """Point d'entrée quand le gestionnaire de services lance `gisuivi-agent.exe --service`."""
    import servicemanager

    servicemanager.Initialize()
    servicemanager.PrepareToHostSingle(_classe_service())
    servicemanager.StartServiceCtrlDispatcher()
    return 0
