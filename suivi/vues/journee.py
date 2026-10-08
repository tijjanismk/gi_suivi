"""Écran « Journée » (accueil) : un jour, toutes les personnes — arrivée, départ, temps actif,
pauses, frise colorée par dossier ; et le détail d'une personne, bloc par bloc, pauses et trous
hors mesure compris."""

from __future__ import annotations

from datetime import date, timedelta

from django.contrib import admin
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.formats import date_format

from identite.decorateurs import consultation_requise
from suivi import rapports
from suivi.models import Employe
from suivi.services import journaliser
from suivi.vues.frise import _hm, contexte_couleurs, frise, legende


def _jour(request) -> date:
    brut = request.GET.get("jour")
    if brut:
        try:
            return date.fromisoformat(brut)
        except ValueError:
            pass
    return timezone.localdate()


def _contexte_jour(request, jour: date, titre: str) -> dict:
    return {
        **admin.site.each_context(request),
        **contexte_couleurs(),
        "titre": titre,
        "jour": jour,
        "veille": jour - timedelta(days=1),
        "lendemain": jour + timedelta(days=1),
        "aujourd_hui": timezone.localdate(),
    }


@consultation_requise
def journee(request):
    jour = _jour(request)
    journaliser(request, "consulter:journee", jour.isoformat())
    journees = rapports.journee_equipe(jour)
    couleurs: dict[str, str] = {}
    graduations = frise(journees, couleurs)
    return render(
        request,
        "suivi/journee.html",
        {
            **_contexte_jour(request, jour, "Journée"),
            "journees": journees,
            "graduations": graduations,
            "legende": legende(couleurs),
            "presents": sum(1 for j in journees if j["arrivee"]),
            "total_actif_hm": _hm(sum(j["actif_s"] for j in journees)),
            "total_pause_hm": _hm(sum(j["pause_s"] for j in journees)),
        },
    )


@consultation_requise
def journee_personne(request, employe_id: int):
    jour = _jour(request)
    personne = get_object_or_404(Employe, pk=employe_id)
    journaliser(request, "consulter:journee_personne", f"employé {personne.pk} {jour}")
    j = rapports.journee_personne(personne, jour)
    couleurs: dict[str, str] = {}
    graduations = frise([j], couleurs)
    return render(
        request,
        "suivi/journee_personne.html",
        {
            **_contexte_jour(request, jour, f"{personne} — {date_format(jour, 'l j F Y')}"),
            "personne": personne,
            "j": j,
            "graduations": graduations,
            "legende": legende(couleurs),
        },
    )
