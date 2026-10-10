import json

from django.conf import settings
from django.db import connection
from django.http import JsonResponse


def _version_deployee() -> str | None:
    """Commit du code en mémoire, lu au démarrage dans VERSION.json (écrit par installer.ps1).
    Permet de voir si c'est bien la nouvelle version qui répond, et non un processus orphelin."""
    try:
        return json.loads((settings.BASE_DIR / "VERSION.json").read_text(encoding="utf-8-sig"))[
            "commit"
        ]
    except (OSError, ValueError, KeyError, TypeError):
        return None


VERSION = _version_deployee()


def sante(request):
    """Supervision IIS : servi sans identité. 503 si la base ne répond pas.

    `version` : commit du code qui répond (absent hors serveur). `?identite=1` ajoute ce que
    l'application voit de l'appelant (adresse, en-têtes), pour diagnostiquer la chaîne
    IIS → ARR → Uvicorn sans rien révéler d'autre que ce que l'appelant envoie lui-même."""
    try:
        with connection.cursor() as c:
            c.execute("SELECT 1")
    except Exception:  # noqa: BLE001 — toute panne de base doit donner 503, pas une trace
        return JsonResponse({"etat": "base indisponible"}, status=503)
    corps = {"etat": "ok"}
    if VERSION:
        corps["version"] = VERSION
    if "identite" in request.GET:
        meta = request.META
        corps["identite"] = {
            "remote_addr": meta.get("REMOTE_ADDR"),
            "authorization": (meta.get("HTTP_AUTHORIZATION") or "").split(" ")[0] or None,
            "remote_user": meta.get("REMOTE_USER") or None,
            "x_remote_user": meta.get("HTTP_X_REMOTE_USER") or None,
            "x_forwarded_proto": meta.get("HTTP_X_FORWARDED_PROTO") or None,
            "x_forwarded_host": meta.get("HTTP_X_FORWARDED_HOST") or None,
            "hote": meta.get("HTTP_HOST"),
        }
    return JsonResponse(corps)
