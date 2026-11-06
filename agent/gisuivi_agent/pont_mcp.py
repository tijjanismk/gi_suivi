"""Pont MCP du poste (ADR 0016) : Claude Desktop le lance et lui parle en stdio (un message
JSON-RPC par ligne) ; le pont relaie chaque message vers `https://app.giconseils.local/mcp/` en
HTTP, avec le ticket Kerberos de la session Windows (Negotiate, comme l'agent), et rend les
réponses à Claude Desktop. Il ne lit ni n'écrit rien d'autre : la base, les droits et les outils
sont sur le serveur.

Le serveur est sans état et répond en JSON : un message = une requête POST. Le pont recopie en
en-têtes ce que le transport HTTP de MCP demande (version du protocole, méthode, nom de l'outil),
et répond lui-même par une erreur JSON-RPC quand le serveur est injoignable ou refuse l'identité,
pour que Claude Desktop dise pourquoi au lieu d'attendre. Les messages sont traités un par un.

    pont-mcp.exe                  # lancé par Claude Desktop (claude_desktop_config.json)
    pont-mcp.exe --url https://app.giconseils.local/mcp/
    pont-mcp.exe --claude         # ajoute le pont à la configuration Claude Desktop de la session

L'adresse vient de la configuration de l'agent (`UrlApi`, GPO ou config.json), suivie de /mcp/.
Journal sur la sortie d'erreur : Claude Desktop le range dans ses journaux (mcp-server-….log).
"""

from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import re
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from gisuivi_agent import __version__

log = logging.getLogger("pont-mcp")

URL_DEFAUT = "https://app.giconseils.local"
NOM_SERVEUR = "gi-conseils"  # nom de l'entrée dans Claude Desktop
DELAIS = (10, 300)  # connexion, réponse (s)
CLE_VERSION = "io.modelcontextprotocol/protocolVersion"
# Méthode → paramètre recopié dans l'en-tête Mcp-Name (transport HTTP de MCP)
NOMMES = {"tools/call": "name", "prompts/get": "name", "resources/read": "uri"}
ERREUR_INTERNE = -32603
ERREUR_LECTURE = -32700
_IMPRIMABLE = re.compile(r"^[\x20-\x7E]*$")
_SENTINELLE = re.compile(r"^=\?base64\?.*\?=$")


def valeur_d_entete(valeur: str) -> str:
    """Telle quelle si elle passe dans un en-tête HTTP, sinon `=?base64?…?=` (comme le SDK)."""
    if _IMPRIMABLE.fullmatch(valeur) and valeur == valeur.strip() and not _SENTINELLE.match(valeur):
        return valeur
    return f"=?base64?{base64.b64encode(valeur.encode('utf-8')).decode('ascii')}?="


def lire_sse(lignes: Iterable[bytes | str]) -> Iterator[Any]:
    """Les messages d'un flux `text/event-stream` : chaque événement porte un JSON en `data:`.
    Lu en UTF-8 (requests supposerait ISO-8859-1 sans `charset`)."""
    donnees: list[str] = []
    for brute in [*lignes, ""]:
        ligne = brute.decode("utf-8") if isinstance(brute, bytes) else brute
        if ligne == "":
            if donnees:
                yield json.loads("\n".join(donnees))
                donnees = []
        elif ligne.startswith("data:"):
            donnees.append(ligne[5:].removeprefix(" "))


def _en_liste(corps: Any) -> list[Any]:
    return corps if isinstance(corps, list) else [corps]


class Pont:
    def __init__(self, url: str, session: Any) -> None:
        self.url = url
        self.session = session
        self.version: str | None = None  # négociée à l'initialisation (protocoles avant 2026)
        self.id_session: str | None = None  # seulement si le serveur en donne un

    def entetes(self, message: Any) -> dict[str, str]:
        h = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if isinstance(message, dict):
            methode = message.get("method")
            params = message.get("params") if isinstance(message.get("params"), dict) else {}
            meta = params.get("_meta") if isinstance(params.get("_meta"), dict) else {}
            # 2026-07-28 : la version voyage dans chaque message ; avant : celle de l'initialisation
            version = meta.get(CLE_VERSION) or (None if methode == "initialize" else self.version)
            if isinstance(version, str):
                h["Mcp-Protocol-Version"] = version
            if isinstance(methode, str):
                h["Mcp-Method"] = methode
                nom = params.get(NOMMES.get(methode, ""))
                if isinstance(nom, str):
                    h["Mcp-Name"] = valeur_d_entete(nom)
        if self.id_session:
            h["Mcp-Session-Id"] = self.id_session
        return h

    def relayer_ligne(self, ligne: str) -> list[Any]:
        try:
            message = json.loads(ligne)
        except json.JSONDecodeError as e:
            log.warning("Message illisible de Claude Desktop : %s", e)
            return [_erreur(None, ERREUR_LECTURE, f"message JSON illisible : {e}")]
        return self.relayer(message)

    def relayer(self, message: Any) -> list[Any]:
        """Les messages à rendre à Claude Desktop pour ce message (aucun pour une notification)."""
        corps = json.dumps(message, ensure_ascii=False).encode("utf-8")
        try:
            reponse = self.session.post(
                self.url, data=corps, headers=self.entetes(message), timeout=DELAIS, stream=True
            )
        except Exception as e:  # noqa: BLE001 — réseau, DNS, certificat : dit à Claude, pas levé
            log.error("Serveur injoignable (%s) : %s", self.url, e)
            return _echec(message, f"serveur injoignable ({self.url}) : {e}")
        try:
            return self._lire(message, reponse)
        finally:
            reponse.close()

    def _lire(self, message: Any, reponse: Any) -> list[Any]:
        statut = reponse.status_code
        if statut == 202:  # notification ou réponse acceptée : rien à rendre
            return []
        type_ = reponse.headers.get("Content-Type", "")
        try:
            if "text/event-stream" in type_:
                messages = list(lire_sse(reponse.iter_lines()))
            elif "application/json" in type_:
                messages = _en_liste(json.loads(reponse.content))
            else:
                messages = []
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            log.error("Réponse illisible du serveur (HTTP %s) : %s", statut, e)
            return _echec(message, f"réponse illisible du serveur (HTTP {statut})")
        if statut >= 400 and not messages:
            log.error("Refus du serveur : HTTP %s", statut)
            return _echec(message, _explication(statut))
        self._noter(message, messages, reponse.headers)
        return messages

    def _noter(self, message: Any, messages: list[Any], entetes: Any) -> None:
        if isinstance(message, dict) and message.get("method") == "initialize":
            for m in messages:
                if not isinstance(m, dict) or m.get("id") != message.get("id"):
                    continue
                resultat = m.get("result")
                if isinstance(resultat, dict):
                    self.version = resultat.get("protocolVersion") or self.version
        self.id_session = entetes.get("Mcp-Session-Id") or self.id_session


def _explication(statut: int) -> str:
    if statut == 401:
        return (
            "identité Windows refusée (HTTP 401) : ouvrir la session sur le domaine GICONSEILS, "
            "puis réessayer (klist purge si le problème persiste)"
        )
    if statut == 403:
        return "accès refusé par le serveur (HTTP 403)"
    return f"le serveur a répondu HTTP {statut}"


def _erreur(ident: Any, code: int, texte: str) -> dict:
    erreur = {"code": code, "message": f"GI-CONSEILS : {texte}"}
    return {"jsonrpc": "2.0", "id": ident, "error": erreur}


def _echec(message: Any, texte: str) -> list[Any]:
    """Une requête attend une réponse : on la donne, en erreur ; une notification, rien."""
    if isinstance(message, dict) and "id" in message and "method" in message:
        return [_erreur(message["id"], ERREUR_INTERNE, texte)]
    return []


def url_mcp(url_api: str | None) -> str:
    return (url_api or URL_DEFAUT).rstrip("/") + "/mcp/"


def _url_de_l_agent() -> str | None:
    try:
        from gisuivi_agent.config import charger

        return charger().url_api
    except Exception as e:  # noqa: BLE001 — sans configuration lisible : l'adresse par défaut
        log.warning("Configuration de l'agent illisible (%s) : %s pris par défaut.", e, URL_DEFAUT)
        return None


def ouvrir_session() -> Any:
    """Comme l'agent : certificat vérifié avec le magasin Windows, Negotiate avec la session."""
    import requests

    from gisuivi_agent.envoi import Envoyeur

    Envoyeur._faire_confiance_au_magasin_windows()
    session = requests.Session()
    session.headers["User-Agent"] = f"GiSuivi-PontMCP/{__version__}"
    session.auth = Envoyeur._auth()
    return session


def entree_claude(executable: str, script: str | None = None) -> dict:
    """L'entrée `mcpServers` de Claude Desktop qui lance ce pont."""
    if script:  # pont lancé par Python (développement) : l'interpréteur, puis le script
        return {"command": executable, "args": [script]}
    return {"command": executable, "args": []}


def ajouter_a_claude(chemin: Path, entree: dict) -> bool:
    """Ajoute (ou remplace) l'entrée du pont dans claude_desktop_config.json, sans toucher au
    reste. Rend True si le fichier a changé."""
    config: dict = {}
    if chemin.exists():
        texte = chemin.read_text(encoding="utf-8-sig").strip()
        config = json.loads(texte) if texte else {}
    serveurs = config.setdefault("mcpServers", {})
    if serveurs.get(NOM_SERVEUR) == entree:
        return False
    serveurs[NOM_SERVEUR] = entree
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def chemin_config_claude() -> Path:
    appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    return Path(appdata) / "Claude" / "claude_desktop_config.json"


def installer_dans_claude() -> int:
    if getattr(sys, "frozen", False):
        entree = entree_claude(sys.executable)
    else:
        entree = entree_claude(sys.executable, str(Path(sys.argv[0]).resolve()))
    chemin = chemin_config_claude()
    try:
        change = ajouter_a_claude(chemin, entree)
    except (OSError, json.JSONDecodeError) as e:
        print(f"Configuration de Claude Desktop non modifiée ({chemin}) : {e}", file=sys.stderr)
        return 1
    etat = "ajouté à" if change else "déjà dans"
    print(f"Pont « {NOM_SERVEUR} » {etat} {chemin}.")
    print("Redémarrer Claude Desktop (menu Fichier, Quitter, puis le rouvrir).")
    return 0


def servir(pont: Pont, entree: Iterable[bytes], sortie: Any) -> None:
    """Boucle stdio : une ligne JSON en entrée, zéro ou plusieurs lignes JSON en sortie."""
    for brute in entree:
        ligne = brute.decode("utf-8", errors="replace").strip()
        if not ligne:
            continue
        for message in pont.relayer_ligne(ligne):
            sortie.write(json.dumps(message, ensure_ascii=False).encode("utf-8") + b"\n")
            sortie.flush()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pont-mcp", description=__doc__.splitlines()[0])
    parser.add_argument("--url", help="adresse du serveur MCP (défaut : UrlApi de l'agent + /mcp/)")
    parser.add_argument(
        "--claude", action="store_true", help="ajouter le pont à la configuration de Claude Desktop"
    )
    args = parser.parse_args(argv)
    if args.claude:
        return installer_dans_claude()
    logging.basicConfig(
        stream=sys.stderr, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    url = args.url or url_mcp(_url_de_l_agent())
    log.info("Pont MCP %s vers %s", __version__, url)
    servir(Pont(url, ouvrir_session()), sys.stdin.buffer, sys.stdout.buffer)
    log.info("Fin de la session Claude Desktop.")
    return 0
