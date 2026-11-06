"""L'utilisateur de chaque requête vient de Windows, jamais d'un formulaire.

- `IDENTITE_SOURCE = "negotiate"` : l'application valide elle-même le ticket Kerberos de l'en-tête
  `Authorization: Negotiate …` (SSPI, voir identite/negotiate.py et ADR 0007). Sans ticket : 401
  avec `WWW-Authenticate: Negotiate`, ce qui fait envoyer le ticket par le navigateur ou l'agent.
- `IDENTITE_SOURCE = "iis"` : `REMOTE_USER` (si le serveur le transmet), sinon l'en-tête
  `X-Remote-User` posé par IIS, cru seulement s'il arrive d'une adresse de confiance
  (IIS sur la même machine). Sans identité : 401.
- `IDENTITE_SOURCE = "dev"` : utilisateur fictif `UTILISATEUR_DEV`, groupes `GROUPES_DEV`.
"""

from __future__ import annotations

from collections.abc import Mapping

from django.conf import settings
from django.http import HttpResponse
from django.utils.module_loading import import_string

from identite.services import obtenir_utilisateur


class IdentiteMiddleware:
    def __init__(self, get_response) -> None:
        self.get_response = get_response

    def __call__(self, request):
        if any(request.path.startswith(p) for p in settings.IDENTITE_CHEMINS_PUBLICS):
            return self.get_response(request)
        if settings.IDENTITE_SOURCE == "negotiate":
            return self._negotiate(request)
        login = login_de_la_requete(request)
        if not login:
            return HttpResponse(
                "Identité Windows absente.", status=401, content_type="text/plain; charset=utf-8"
            )
        request.user = obtenir_utilisateur(login)
        return self.get_response(request)

    def _negotiate(self, request):
        authentifier = import_string(settings.IDENTITE_AUTHENTIFICATEUR_NEGOTIATE)
        login, jeton = authentifier(request.META.get("HTTP_AUTHORIZATION"))
        if not login:
            reponse = HttpResponse(
                "Authentification Windows (Kerberos) requise.",
                status=401,
                content_type="text/plain; charset=utf-8",
            )
            reponse["WWW-Authenticate"] = "Negotiate"
            return reponse
        request.user = obtenir_utilisateur(login)
        reponse = self.get_response(request)
        if jeton:  # authentification mutuelle : le client peut vérifier qu'il parle au bon serveur
            reponse["WWW-Authenticate"] = f"Negotiate {jeton}"
        return reponse


def login_de_la_requete(request) -> str | None:
    return login_des_meta(request.META)


def login_des_meta(meta: Mapping[str, str]) -> str | None:
    """Modes « dev » et « iis » ; `meta` au format de `request.META` (aussi lu par le serveur MCP,
    qui n'est pas une vue Django)."""
    if settings.IDENTITE_SOURCE == "dev":
        return settings.UTILISATEUR_DEV
    login = meta.get("REMOTE_USER")
    if not login and meta.get("REMOTE_ADDR") in settings.IDENTITE_PROXYS_DE_CONFIANCE:
        login = meta.get("HTTP_X_REMOTE_USER")
    return (login or "").strip() or None
