"""Serveur MCP du module avis (ADR 0016) : les outils de `avis/outils_mcp.py`, servis sous `/mcp/`
en HTTP « streamable », dans le même processus que Django (ADR 0001, `config/asgi.py`).

- SDK `mcp` 2 : l'ancien `FastMCP` s'y appelle `MCPServer`. Sans état et en réponses JSON : chaque
  message est une requête HTTP indépendante, qui survit à un redémarrage du service et passe telle
  quelle par IIS ; aucun outil n'a besoin de rappeler le poste.
- Identité : celle des écrans (ADR 0007). Le pont du poste (`agent/pont-mcp.py`) envoie le ticket
  Kerberos de la session Windows ; sans ticket valide, 401 et `WWW-Authenticate: Negotiate`.
- Droits : la lecture suit la consultation des écrans d'avis ; les écritures (proposition, critère
  en brouillon, terme proposé) sont réservées à GI-Direction et GI-Offres, et attribuées à la
  personne du ticket, jamais à un nom donné par Claude.
- Les outils sont enregistrés tels quels (`OUTILS`) ; l'ORM est synchrone, d'où `sync_to_async`.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

from asgiref.sync import sync_to_async
from django.conf import settings
from django.db import close_old_connections, connection
from django.utils.module_loading import import_string
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations

from avis import outils_mcp
from identite.middleware import login_des_meta
from identite.services import obtenir_utilisateur

Portee = MutableMapping[str, Any]
Recevoir = Callable[[], Awaitable[MutableMapping[str, Any]]]
Envoyer = Callable[[MutableMapping[str, Any]], Awaitable[None]]
ApplicationASGI = Callable[[Portee, Recevoir, Envoyer], Awaitable[None]]

CHEMIN = "/mcp/"
NOM = "gi-conseils"
CLE_UTILISATEUR = "gic.utilisateur"  # posée dans la portée ASGI, lue par chaque outil
ECRITURES = frozenset({"creer_proposition", "enregistrer_brouillon_critere", "proposer_terme"})
# `rechercher_missions(**filtre)` : les clés du filtre d'un critère (moteur/avis/filtres.py, CLES),
# exposées une à une pour que Claude en voie le schéma.
CLES_FILTRE: dict[str, Any] = {
    "natures": list[str],
    "domaines": list[str],
    "categories": list[str],
    "types_ouvrage": list[str],
    "familles_ouvrage": list[str],
    "roles": list[str],
    "pays": list[str],
    "clients": list[str],
    "bailleurs": list[str],
    "localites": list[str],
    "mots_cles": list[str],
    "quantites_min": dict,
    "annee_min": int,
    "annee_max": int,
    "pieces_requises": list[str],
    "pieces_completes_requises": bool,
}
INSTRUCTIONS = (
    "Base des références, des avis et des experts de GI-CONSEILS (bureau d'études, Bamako). "
    "Avant de proposer un filtre, apprendre le vocabulaire avec lister_referentiel ou "
    "proposer_filtre_critere. Les écritures ne créent que des propositions d'avis, des critères "
    "en brouillon et des termes proposés : une personne les valide à l'écran."
)


def groupes_autorises(ecriture: bool) -> tuple[str, ...]:
    """Écriture : la saisie des écrans d'avis ; lecture : leur consultation (avis/vues)."""
    saisie = (settings.GROUPE_DIRECTION, settings.GROUPE_OFFRES)
    return saisie if ecriture else (*saisie, settings.GROUPE_DIRECTION_LECTURE)


def _a_jour() -> None:
    """Comme Django avant et après chaque requête : une connexion trop vieille ou cassée (base
    redémarrée) est refermée. Jamais dans une transaction ouverte (tests)."""
    if not connection.in_atomic_block:
        close_old_connections()


def _appeler(fonction: Callable[..., dict], arguments: dict[str, Any]) -> dict:
    _a_jour()
    try:
        return fonction(**arguments)
    finally:
        _a_jour()


def _utilisateur(ctx: Context) -> Any:
    try:
        requete = ctx.request_context.request
    except ValueError:  # hors d'une requête
        return None
    return getattr(requete, "scope", {}).get(CLE_UTILISATEUR)


def _parametres(fonction: Callable[..., dict]) -> list[inspect.Parameter]:
    """La signature vue par Claude : sans `par` (posé ici), le filtre détaillé, plus le contexte."""
    parametres = []
    for p in inspect.signature(fonction, eval_str=True).parameters.values():
        if p.name == "par":
            continue
        if p.kind is inspect.Parameter.VAR_KEYWORD:
            parametres += [
                inspect.Parameter(
                    cle, inspect.Parameter.KEYWORD_ONLY, default=None, annotation=type_ | None
                )
                for cle, type_ in CLES_FILTRE.items()
            ]
            continue
        parametres.append(p)
    parametres.append(inspect.Parameter("ctx", inspect.Parameter.KEYWORD_ONLY, annotation=Context))
    return parametres


def outil(fonction: Callable[..., dict]) -> Callable[..., Awaitable[dict]]:
    """Enveloppe une fonction de `outils_mcp` : même nom, même documentation, mêmes paramètres ;
    identité et droits vérifiés, écriture attribuée, appel synchrone hors de la boucle."""
    ecriture = fonction.__name__ in ECRITURES
    parametres = _parametres(fonction)
    filtre = {p.name for p in parametres if p.name in CLES_FILTRE}
    attribuee = "par" in inspect.signature(fonction).parameters

    async def appel(ctx: Context, **arguments: Any) -> dict:
        utilisateur = _utilisateur(ctx)
        if utilisateur is None:
            return {"erreur": "identité Windows absente : passer par le pont du poste"}
        groupes = groupes_autorises(ecriture)
        if not (utilisateur.is_active and utilisateur.dans_groupe(*groupes)):
            return {"erreur": f"réservé aux membres de {', '.join(groupes)}"}
        for cle in filtre:  # une clé absente garde la valeur par défaut du filtre
            if arguments.get(cle) is None:
                arguments.pop(cle, None)
        if attribuee:
            arguments["par"] = utilisateur.login_windows
        return await sync_to_async(_appeler)(fonction, arguments)

    appel.__name__ = appel.__qualname__ = fonction.__name__
    appel.__doc__ = fonction.__doc__
    appel.__module__ = fonction.__module__
    appel.__signature__ = inspect.Signature(parametres, return_annotation=dict)
    appel.__annotations__ = {p.name: p.annotation for p in parametres} | {"return": dict}
    return appel


def creer_serveur() -> MCPServer:
    serveur = MCPServer(NOM, title="GI-CONSEILS", instructions=INSTRUCTIONS)
    for fonction in outils_mcp.OUTILS:
        ecriture = fonction.__name__ in ECRITURES
        serveur.add_tool(
            outil(fonction),
            annotations=ToolAnnotations(
                read_only_hint=not ecriture, destructive_hint=False, open_world_hint=False
            ),
            structured_output=False,
        )
    return serveur


def _securite() -> TransportSecuritySettings:
    """Les noms d'hôte de Django (ALLOWED_HOSTS) ; une requête qui porte un en-tête `Origin` (une
    page web, même du domaine) est refusée : seul le pont parle à /mcp/."""
    hotes = list(settings.ALLOWED_HOSTS)
    if "*" in hotes:
        return TransportSecuritySettings(enable_dns_rebinding_protection=False)
    return TransportSecuritySettings(
        allowed_hosts=[nom for h in hotes for nom in (h, f"{h}:*")], allowed_origins=[]
    )


def _identifier(entetes: dict[str, str], adresse: str | None) -> tuple[Any, str | None]:
    """(utilisateur ou None, jeton d'authentification mutuelle), comme `IdentiteMiddleware`."""
    _a_jour()
    try:
        if settings.IDENTITE_SOURCE == "negotiate":
            authentifier = import_string(settings.IDENTITE_AUTHENTIFICATEUR_NEGOTIATE)
            login, jeton = authentifier(entetes.get("authorization"))
        else:
            meta = {"REMOTE_ADDR": adresse, "HTTP_X_REMOTE_USER": entetes.get("x-remote-user")}
            login, jeton = login_des_meta(meta), None
        return (obtenir_utilisateur(login) if login else None), jeton
    finally:
        _a_jour()


async def _refuser(send: Envoyer) -> None:
    corps = b"Authentification Windows (Kerberos) requise."
    entetes = [
        (b"content-type", b"text/plain; charset=utf-8"),
        (b"content-length", str(len(corps)).encode()),
    ]
    if settings.IDENTITE_SOURCE == "negotiate":
        entetes.append((b"www-authenticate", b"Negotiate"))
    await send({"type": "http.response.start", "status": 401, "headers": entetes})
    await send({"type": "http.response.body", "body": corps})


def identifier(application: ApplicationASGI) -> ApplicationASGI:
    """Pose l'utilisateur dans la portée ASGI avant le SDK, ou répond 401."""

    async def application_identifiee(scope: Portee, receive: Recevoir, send: Envoyer) -> None:
        if scope["type"] != "http":  # cycle de vie : démarre le gestionnaire de sessions du SDK
            await application(scope, receive, send)
            return
        entetes = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
        adresse = (scope.get("client") or (None, None))[0]
        utilisateur, jeton = await sync_to_async(_identifier)(entetes, adresse)
        if utilisateur is None:
            await _refuser(send)
            return

        async def envoyer(message: MutableMapping[str, Any]) -> None:
            if jeton and message["type"] == "http.response.start":
                mutuelle = (b"www-authenticate", f"Negotiate {jeton}".encode("latin-1"))
                message = {**message, "headers": [*message.get("headers", []), mutuelle]}
            await send(message)

        await application({**scope, CLE_UTILISATEUR: utilisateur}, receive, envoyer)

    return application_identifiee


def creer_application(serveur: MCPServer | None = None) -> ApplicationASGI:
    serveur = serveur or creer_serveur()
    return identifier(
        serveur.streamable_http_app(
            streamable_http_path=CHEMIN,
            stateless_http=True,
            json_response=True,
            transport_security=_securite(),
        )
    )


def vers_mcp(chemin: str) -> bool:
    return chemin == CHEMIN.rstrip("/") or chemin.startswith(CHEMIN)


def aiguiller(django: ApplicationASGI, mcp: ApplicationASGI) -> ApplicationASGI:
    """`/mcp/` au serveur MCP, le reste à Django ; le cycle de vie (démarrage et arrêt d'Uvicorn)
    au serveur MCP, que Django n'utilise pas."""

    async def application(scope: Portee, receive: Recevoir, send: Envoyer) -> None:
        if scope["type"] == "lifespan" or (scope["type"] == "http" and vers_mcp(scope["path"])):
            await mcp(scope, receive, send)
        else:
            await django(scope, receive, send)

    return application
