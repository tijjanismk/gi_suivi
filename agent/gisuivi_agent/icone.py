"""Le voyant : icône dans la zone de notification, à côté de l'horloge et du réseau.

Trois couleurs : vert (mesure active, envoi récent ou mode local), orange
(données en attente d'envoi), gris (session inactive / hors réseau depuis
longtemps). Un clic droit : « Mon activité du jour », « Dernier envoi »,
« Version ». Aucune entrée « Quitter » : l'agent vit avec la session.

Windows masque les nouvelles icônes dans le tiroir « ^ » : une notification au
démarrage le dit, et la note à l'équipe explique comment épingler l'icône.
"""

from __future__ import annotations

import logging
import os
import threading
import webbrowser
from collections.abc import Callable

log = logging.getLogger(__name__)

COULEURS = {"vert": (46, 160, 67), "orange": (219, 142, 23), "gris": (128, 128, 128)}


def _image(couleur: tuple[int, int, int]):
    from PIL import Image, ImageDraw

    taille = 64
    im = Image.new("RGBA", (taille, taille), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse(
        (6, 6, taille - 6, taille - 6), fill=couleur + (255,), outline=(255, 255, 255, 230), width=4
    )
    # Un « G » stylisé : simple barre horizontale pour rester lisible en 16 px
    d.rectangle((24, 30, 42, 36), fill=(255, 255, 255, 255))
    return im


def _ouvrir_windows(url: str) -> None:
    try:
        import pythoncom

        pythoncom.CoInitialize()  # l'ouverture par le shell attend COM dans ce fil
    except Exception as e:  # noqa: BLE001 — hors Windows ou déjà initialisé
        log.debug("COM non initialisé : %s", e)
    os.startfile(url)  # noqa: S606 — adresse fixe de la configuration, navigateur par défaut


def ouvrir(url: str, ouvreur=None) -> threading.Thread:
    """Ouvre `url` dans un fil à part. Appelée dans le fil de l'icône, une ouverture qui tarde
    (navigateur lent à répondre) bloquait l'icône : les clics suivants ne faisaient plus rien.
    En cas d'échec, essai par `webbrowser`, et trace dans le journal."""

    def faire() -> None:
        try:
            (ouvreur or _ouvrir_windows)(url)
        except Exception as e:  # noqa: BLE001
            log.warning("Ouverture de %s impossible (%s), essai par webbrowser", url, e)
            try:
                webbrowser.open(url)
            except Exception as e2:  # noqa: BLE001
                log.error("Ouverture de %s impossible : %s", url, e2)

    fil = threading.Thread(target=faire, name="ouvrir-page", daemon=True)
    fil.start()
    return fil


def _duree(s: float) -> str:
    h, m = int(s // 3600), int((s % 3600) // 60)
    return f"{h} h {m:02d}" if h else f"{m} min"


class Icone:
    def __init__(
        self,
        version: str,
        resume_du_jour: Callable[[], dict],
        url_mon_activite: str | None,
        mode_local: bool,
    ) -> None:
        import pystray

        self.version = version
        self.resume_du_jour = resume_du_jour
        self.url = url_mon_activite
        self.mode_local = mode_local
        self.dernier_envoi_texte = "jamais" if not mode_local else "mode local (pas d'envoi)"
        self._images = {k: _image(v) for k, v in COULEURS.items()}
        self.icone = pystray.Icon(
            "GI-Suivi",
            self._images["vert"],
            "GI-CONSEILS — Suivi d'activité : actif",
            menu=pystray.Menu(
                pystray.MenuItem("Mon activité du jour", self._mon_activite, default=True),
                pystray.MenuItem(
                    lambda _i: f"Dernier envoi : {self.dernier_envoi_texte}", None, enabled=False
                ),
                pystray.MenuItem(lambda _i: f"GI-Suivi agent {self.version}", None, enabled=False),
                pystray.MenuItem("Qu'est-ce qui est mesuré ?", self._explication),
            ),
        )

    # -- API ---------------------------------------------------------------
    def demarrer(self) -> None:
        threading.Thread(target=self.icone.run, name="icone", daemon=True).start()

    def etat(self, couleur: str, texte: str) -> None:
        try:
            self.icone.icon = self._images[couleur]
            self.icone.title = f"GI-CONSEILS — Suivi d'activité : {texte}"
        except Exception:  # noqa: BLE001 — l'icône n'est pas encore prête
            log.debug("Icône pas encore prête : état « %s » non affiché", couleur)

    def notifier(self, titre: str, texte: str) -> None:
        try:
            self.icone.notify(texte, titre)
        except Exception:  # noqa: BLE001
            log.debug("Notification impossible")

    def notifier_demarrage(self) -> None:
        self.notifier(
            "Suivi d'activité actif",
            "Comme convenu, le temps passé sur vos dossiers est mesuré. "
            "Cliquez sur l'icône pour voir votre journée. "
            "Glissez-la près de l'horloge pour la garder visible.",
        )

    # -- actions du menu -----------------------------------------------------
    def _mon_activite(self, _icon=None, _item=None) -> None:
        if self.url and not self.mode_local:
            log.info("Clic : ouverture de %s", self.url)
            ouvrir(self.url)
            return
        r = self.resume_du_jour()
        lignes = [f"Aujourd'hui : {_duree(r['total_s'])} d'activité"]
        for nom, s in list(r["par_dossier"].items())[:4]:
            lignes.append(f"• {nom} : {_duree(s)}")
        if not r["par_dossier"]:
            for app, s in list(r["par_application"].items())[:4]:
                lignes.append(f"• {app} : {_duree(s)}")
        self.notifier("Mon activité du jour", "\n".join(lignes))

    def _explication(self, _icon=None, _item=None) -> None:
        self.notifier(
            "Ce qui est mesuré",
            "Logiciel au premier plan, nom et dossier du fichier, heures d'activité. "
            "Jamais : contenu des fichiers, frappes, captures d'écran, pages web, courriels.",
        )
