from django.db import connection
from django.http import JsonResponse


def sante(request):
    """Supervision IIS : servi sans identité. 503 si la base ne répond pas.

    `?identite=1` ajoute ce que l'application voit de l'appelant (adresse d'où arrive la requête,
    en-têtes d'identité et de protocole) : pour diagnostiquer la chaîne IIS → ARR → Uvicorn sans
    rien révéler d'autre que ce que l'appelant envoie lui-même."""
    try:
        with connection.cursor() as c:
            c.execute("SELECT 1")
    except Exception:  # noqa: BLE001 — toute panne de base doit donner 503, pas une trace
        return JsonResponse({"etat": "base indisponible"}, status=503)
    corps = {"etat": "ok"}
    if "identite" in request.GET:
        meta = request.META
        corps["identite"] = {
            "remote_addr": meta.get("REMOTE_ADDR"),
            "remote_user": meta.get("REMOTE_USER") or None,
            "x_remote_user": meta.get("HTTP_X_REMOTE_USER") or None,
            "x_forwarded_proto": meta.get("HTTP_X_FORWARDED_PROTO") or None,
            "x_forwarded_host": meta.get("HTTP_X_FORWARDED_HOST") or None,
            "hote": meta.get("HTTP_HOST"),
        }
    return JsonResponse(corps)
