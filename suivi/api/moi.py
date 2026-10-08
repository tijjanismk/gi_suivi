"""A04 — ce que chaque personne authentifiée peut lire, et seulement pour elle :
GET /api/moi/aujourdhui (sa journée) ; GET /api/racines (ce que l'agent lit au démarrage)."""

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from suivi.services import activite_du_jour, employe_de, racines_pour_agent


@require_GET
def moi_aujourdhui(request) -> JsonResponse:
    return JsonResponse(activite_du_jour(employe_de(request.user)))


@require_GET
def racines(request) -> JsonResponse:
    return JsonResponse(racines_pour_agent())
