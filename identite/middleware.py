"""L'utilisateur de chaque requête vient de Windows, jamais d'un formulaire.

- `IDENTITE_SOURCE = "iis"` : `REMOTE_USER` (si le serveur le transmet), sinon l'en-tête
  `X-Remote-User` posé par IIS, cru seulement s'il arrive d'une adresse de confiance
  (IIS sur la même machine). Sans identité : 401.
- `IDENTITE_SOURCE = "dev"` : utilisateur fictif `UTILISATEUR_DEV`, groupes `GROUPES_DEV`.
"""

from __future__ import annotations

from django.conf import settings
from django.http import HttpResponse

from identite.services import obtenir_utilisateur


class IdentiteMiddleware:
    def __init__(self, get_response) -> None:
        self.get_response = get_response

    def __call__(self, request):
        if any(request.path.startswith(p) for p in settings.IDENTITE_CHEMINS_PUBLICS):
            return self.get_response(request)
        login = login_de_la_requete(request)
        if not login:
            return HttpResponse(
                "Identité Windows absente.", status=401, content_type="text/plain; charset=utf-8"
            )
        request.user = obtenir_utilisateur(login)
        return self.get_response(request)


def login_de_la_requete(request) -> str | None:
    if settings.IDENTITE_SOURCE == "dev":
        return settings.UTILISATEUR_DEV
    login = request.META.get("REMOTE_USER")
    if not login and request.META.get("REMOTE_ADDR") in settings.IDENTITE_PROXYS_DE_CONFIANCE:
        login = request.META.get("HTTP_X_REMOTE_USER")
    return (login or "").strip() or None
