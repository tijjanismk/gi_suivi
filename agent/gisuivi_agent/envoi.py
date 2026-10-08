"""Envoie les lots de segments à l'API avec l'identité Windows de la session (Kerberos)."""

from __future__ import annotations

import logging
import os
import platform
import sys
from datetime import datetime

log = logging.getLogger(__name__)


class Envoyeur:
    def __init__(self, url_api: str, version_agent: str) -> None:
        import requests

        self.url = url_api.rstrip("/") + "/api/segments"
        self.version = version_agent
        self.session = requests.Session()
        self.session.headers["User-Agent"] = f"GiSuivi-Agent/{version_agent}"
        self.session.auth = self._auth()
        self.echecs = 0
        self.dernier_envoi: datetime | None = None
        self.derniere_erreur: str | None = None

    @staticmethod
    def _auth():
        """Negotiate avec les identifiants de la session, sans mot de passe (SSPI sous Windows)."""
        if sys.platform == "win32":
            try:
                from requests_negotiate_sspi import HttpNegotiateAuth

                return HttpNegotiateAuth()
            except ImportError:
                pass
        try:
            from requests_kerberos import OPTIONAL, HTTPKerberosAuth

            return HTTPKerberosAuth(mutual_authentication=OPTIONAL)
        except ImportError:
            log.warning("Aucune bibliothèque Negotiate : les envois seront refusés par IIS.")
            return None

    def attente_s(self) -> int:
        """Attente avant nouvel essai après échec : 30 s, 60, 120 … plafonné à 30 min."""
        return min(1800, 30 * (2 ** min(self.echecs, 6))) if self.echecs else 0

    @staticmethod
    def _sid() -> str | None:
        """SID de la session : clé stable de l'employé côté serveur (le login change parfois)."""
        if sys.platform != "win32":
            return None
        try:
            import win32api
            import win32security

            sid, _, _ = win32security.LookupAccountName(None, win32api.GetUserNameEx(2))
            return win32security.ConvertSidToStringSid(sid)
        except Exception as e:  # noqa: BLE001 — sans SID, le serveur reconnaît la personne au login
            log.debug("SID indisponible : %s", e)
            return None

    def envoyer(self, lot_id: str, segments: list[dict]) -> bool:
        import requests

        corps = {
            "lot_id": lot_id,
            "poste": platform.node(),
            "utilisateur": os.environ.get("USERNAME", ""),
            "sid": self._sid(),
            "version_agent": self.version,
            "segments": segments,
        }
        try:
            r = self.session.post(self.url, json=corps, timeout=(10, 60))
            if r.status_code in (200, 201):
                self.echecs = 0
                self.dernier_envoi = datetime.now()
                self.derniere_erreur = None
                return True
            if r.status_code == 401:
                self.derniere_erreur = (
                    "401 : identité refusée (ticket Kerberos expiré ou SPN absent)"
                )
            elif r.status_code == 403:
                self.derniere_erreur = "403 : compte non autorisé à envoyer"
            elif 400 <= r.status_code < 500:
                # Lot refusé définitivement : journalisé, puis considéré traité pour ne pas boucler
                self.derniere_erreur = f"{r.status_code} : {r.text[:200]}"
                log.error("Lot %s refusé par le serveur : %s", lot_id, self.derniere_erreur)
                return True
            else:
                self.derniere_erreur = f"{r.status_code} : {r.text[:200]}"
        except requests.exceptions.RequestException as e:
            self.derniere_erreur = f"réseau : {type(e).__name__}"
        self.echecs += 1
        log.warning(
            "Envoi du lot %s échoué (%s), nouvel essai dans %d s",
            lot_id,
            self.derniere_erreur,
            self.attente_s(),
        )
        return False
