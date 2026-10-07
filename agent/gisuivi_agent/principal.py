"""Point d'entrée de l'agent de session.

Boucle toutes les `intervalle_s` secondes : observer → segmenter → tampon.
Toutes les `envoi_toutes_les_s` secondes : envoyer un lot (si une API est
configurée). L'icône reflète l'état. Les événements de verrouillage et de
fermeture de session arrivent par une fenêtre cachée.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
import threading
import time
from datetime import datetime

from gisuivi_agent import __version__
from gisuivi_agent.config import Config, charger
from gisuivi_agent.tampon import Tampon
from moteur.suivi.segmentation import Segmenteur

log = logging.getLogger("gisuivi")

# Messages et codes de session Windows (winuser.h, wtsapi32.h)
WM_WTSSESSION_CHANGE = 0x02B1
WTS_SESSION_LOCK, WTS_SESSION_UNLOCK, WTS_SESSION_LOGOFF = 0x7, 0x8, 0x6


def _journal(cfg: Config) -> None:
    cfg.dossier_donnees.mkdir(parents=True, exist_ok=True)
    h = logging.handlers.RotatingFileHandler(
        cfg.dossier_donnees / "agent.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s : %(message)s"))
    logging.basicConfig(
        level=getattr(logging, cfg.journal_niveau.upper(), logging.INFO), handlers=[h]
    )


class Agent:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.tampon = Tampon(cfg.dossier_donnees / "tampon.db")
        self.segmenteur = Segmenteur(cfg.parametres_moteur())
        self.arret = threading.Event()
        self.observateur = None
        self.icone = None
        self.envoyeur = None
        self.prochain_envoi = time.monotonic() + 30

    # -- démarrage ---------------------------------------------------------
    def demarrer(self) -> None:
        from gisuivi_agent.observation import Observateur

        self.observateur = Observateur(self.cfg.racines, self.cfg.correspondance_lecteurs)
        self._ecouter_session()
        try:
            from gisuivi_agent.icone import Icone

            self.icone = Icone(
                __version__, self._resume, self.cfg.url_mon_activite, self.cfg.mode_local
            )
            self.icone.demarrer()
            time.sleep(1.5)
            self.icone.notifier_demarrage()
        except Exception as e:  # noqa: BLE001 — sans icône on mesure quand même, mais on le journalise fort
            log.error("Icône indisponible : %s", e)
        if not self.cfg.mode_local:
            from gisuivi_agent.envoi import Envoyeur

            self.envoyeur = Envoyeur(self.cfg.url_api, __version__)
        self.tampon.ecrire_etat(
            "demarrages", str(int(self.tampon.lire_etat("demarrages") or 0) + 1)
        )
        log.info(
            "Agent %s démarré, mode %s, %d racines",
            __version__,
            "local" if self.cfg.mode_local else "connecté",
            len(self.cfg.racines),
        )
        self._boucle()

    def _resume(self) -> dict:
        return self.tampon.resume_du_jour(
            racines=self.cfg.racines, lecteurs=self.cfg.correspondance_lecteurs
        )

    # -- événements de session (verrouillage, fermeture) ------------------------
    def _ecouter_session(self) -> None:
        if sys.platform != "win32":
            return

        def boucle_messages() -> None:
            import win32api
            import win32con
            import win32gui
            import win32ts

            def proc(hwnd, msg, wparam, lparam):
                if msg == WM_WTSSESSION_CHANGE:
                    if wparam == WTS_SESSION_LOCK:
                        self.observateur.session_verrouillee(True)
                    elif wparam == WTS_SESSION_UNLOCK:
                        self.observateur.session_verrouillee(False)
                    elif wparam == WTS_SESSION_LOGOFF:
                        self.arreter()
                elif msg in (win32con.WM_QUERYENDSESSION, win32con.WM_ENDSESSION):
                    self.arreter()
                    return 1
                return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

            wc = win32gui.WNDCLASS()
            wc.lpszClassName, wc.lpfnWndProc, wc.hInstance = (
                "GiSuiviSession",
                proc,
                win32api.GetModuleHandle(None),
            )
            atom = win32gui.RegisterClass(wc)
            hwnd = win32gui.CreateWindow(
                atom, "GiSuiviSession", 0, 0, 0, 0, 0, 0, 0, wc.hInstance, None
            )
            win32ts.WTSRegisterSessionNotification(hwnd, win32ts.NOTIFY_FOR_THIS_SESSION)
            win32gui.PumpMessages()

        threading.Thread(target=boucle_messages, name="session", daemon=True).start()

    # -- boucle ---------------------------------------------------------------
    def _boucle(self) -> None:
        while not self.arret.is_set():
            debut = time.monotonic()
            try:
                obs = self.observateur.observer()
                clos = self.segmenteur.observer(obs)
                if clos:
                    self.tampon.ajouter(clos)
                if time.monotonic() >= self.prochain_envoi:
                    self._envoyer()
                self._rafraichir_icone(obs)
            except Exception as e:  # noqa: BLE001 — l'agent ne doit jamais mourir sur une erreur d'observation
                log.exception("Erreur dans la boucle : %s", e)
            self.arret.wait(max(0.5, self.cfg.intervalle_s - (time.monotonic() - debut)))
        self._terminer()

    def _envoyer(self) -> None:
        self.prochain_envoi = time.monotonic() + self.cfg.envoi_toutes_les_s
        if self.envoyeur is None:
            self.tampon.purger(jours=30)  # mode local : on garde un mois
            return
        if self.envoyeur.attente_s() and self.envoyeur.echecs:
            self.prochain_envoi = time.monotonic() + self.envoyeur.attente_s()
        for _ in range(5):  # jusqu'à 5 lots par cycle pour rattraper après une coupure
            lot = self.tampon.preparer_lot()
            if not lot:
                break
            lot_id, segments = lot
            if not self.envoyeur.envoyer(lot_id, segments):
                self.prochain_envoi = time.monotonic() + self.envoyeur.attente_s()
                break
            self.tampon.acquitter(lot_id)
            if self.icone:
                self.icone.dernier_envoi_texte = datetime.now().strftime("%H:%M")
        self.tampon.purger(jours=7)

    def _rafraichir_icone(self, obs) -> None:
        if not self.icone:
            return
        if self.cfg.mode_local:
            self.icone.etat("vert", "actif (mode local)")
            return
        attente = self.tampon.en_attente()
        if self.envoyeur and self.envoyeur.echecs >= 3:
            self.icone.etat("gris", f"hors réseau, {attente} segments en attente")
        elif attente > 200:
            self.icone.etat("orange", f"{attente} segments en attente d'envoi")
        else:
            self.icone.etat("vert", "actif")

    # -- arrêt ----------------------------------------------------------------
    def arreter(self) -> None:
        self.arret.set()

    def _terminer(self) -> None:
        restes = self.segmenteur.clore_tout(datetime.now())
        self.tampon.ajouter(restes)
        if self.envoyeur:
            self._envoyer()
        log.info("Agent arrêté proprement.")


MUTEX_SESSION = "Local\\GiSuivi-Agent"  # « Local\ » : un par session Windows


def _seul_dans_la_session():
    """Rend le mutex si cet agent est le seul de la session, None si un autre tourne déjà.

    Deux agents dans une session compteraient chaque minute deux fois (même tampon).
    """
    if sys.platform != "win32":
        return True
    import win32api
    import win32event
    import winerror

    mutex = win32event.CreateMutex(None, False, MUTEX_SESSION)
    if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
        win32api.CloseHandle(mutex)
        return None
    return mutex  # gardé ouvert jusqu'à la fin du processus


def main() -> int:
    cfg = charger()
    _journal(cfg)
    for message in cfg.avertissements:
        log.warning("Configuration : %s", message)
    mutex = _seul_dans_la_session()
    if mutex is None:
        log.info("Un agent tourne déjà dans cette session ; ce lancement s'arrête.")
        return 0
    try:
        Agent(cfg).demarrer()
    except NotImplementedError as e:
        print(e, file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
