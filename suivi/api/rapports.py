"""A05 — points d'accès JSON des rapports, réservés à la direction (et au compte de consultation).
Paramètres communs : debut, fin (AAAA-MM-JJ, fin incluse) ; par défaut les 7 derniers jours."""

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from identite.decorateurs import consultation_requise
from suivi import rapports
from suivi.models import Employe
from suivi.services import journaliser


def _periode(request):
    """Période demandée ; la consultation est journalisée (qui a regardé quoi, A06)."""
    try:
        p = rapports.periode_depuis(request.GET)
    except ValueError as e:
        return None, JsonResponse({"erreur": str(e)}, status=400)
    journaliser(request, f"consulter:{request.resolver_match.url_name}", f"{p.debut}..{p.fin}")
    return p, None


@require_GET
@consultation_requise
def synthese(request):
    p, erreur = _periode(request)
    return erreur or JsonResponse(rapports.synthese(p))


@require_GET
@consultation_requise
def dossiers(request):
    p, erreur = _periode(request)
    return erreur or JsonResponse(rapports.dossiers(p))


@require_GET
@consultation_requise
def liste_dossiers(request):
    p, erreur = _periode(request)
    return erreur or JsonResponse({"dossiers": rapports.liste_dossiers(p)})


@require_GET
@consultation_requise
def activite_employe(request, employe_id: int):
    p, erreur = _periode(request)
    if erreur:
        return erreur
    employe = get_object_or_404(Employe, pk=employe_id)
    jour = None
    if request.GET.get("jour"):
        try:
            from datetime import date

            jour = date.fromisoformat(request.GET["jour"])
        except ValueError:
            return JsonResponse({"erreur": "jour doit être une date AAAA-MM-JJ"}, status=400)
    return JsonResponse(rapports.activite_employe(employe, p, jour))


@require_GET
@consultation_requise
def a_classer(request):
    p, erreur = _periode(request)
    return erreur or JsonResponse(rapports.a_classer(p))


@require_GET
@consultation_requise
def etat_postes(request):
    journaliser(request, "consulter:postes_etat")
    return JsonResponse({"postes": rapports.etat_postes()})
