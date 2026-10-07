from django.db import connection
from django.http import JsonResponse


def sante(request):
    """Supervision IIS : servi sans identité. 503 si la base ne répond pas."""
    try:
        with connection.cursor() as c:
            c.execute("SELECT 1")
        return JsonResponse({"etat": "ok"})
    except Exception:  # noqa: BLE001 — toute panne de base doit donner 503, pas une trace
        return JsonResponse({"etat": "base indisponible"}, status=503)
