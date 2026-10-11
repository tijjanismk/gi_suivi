"""Page « Mon activité du jour » : celle qu'ouvre l'icône de l'agent. Chaque personne y voit
ses propres heures et les tâches qui lui sont confiées, et rien d'autre (principe de
transparence du blueprint)."""

from datetime import timedelta

from django.contrib import admin
from django.db.models import Q
from django.shortcuts import render
from django.utils import timezone

from suivi.models import Tache
from suivi.services import activite_du_jour, employe_de
from suivi.taches import preparer
from suivi.vues.frise import duree_courte


def mes_taches(employe) -> list[Tache]:
    """Ouvertes, plus celles faites ces 7 derniers jours ; les annulées n'apparaissent pas."""
    if employe is None:
        return []
    qs = (
        Tache.objects.filter(personne=employe)
        .filter(
            Q(etat__in=Tache.OUVERTES)
            | Q(etat=Tache.Etat.FAITE, faite_le__gte=timezone.now() - timedelta(days=7))
        )
        .select_related("dossier")
        .order_by("etat", "echeance", "creee_le")
    )
    return preparer(qs)


def mon_activite(request):
    employe = employe_de(request.user)
    activite = activite_du_jour(employe)
    # durées lisibles : minutes sous l'heure, « h » au-delà (l'API, elle, reste en secondes)
    for ligne in [*activite["par_dossier"], *activite["par_application"]]:
        ligne["duree"] = duree_courte(ligne["duree_s"])
    activite["a_classer"] = duree_courte(activite["a_classer_s"])
    activite["sans_fichier"] = duree_courte(activite["sans_fichier_s"])
    return render(
        request,
        "suivi/moi.html",
        {
            **admin.site.each_context(request),
            "activite": activite,
            "taches": mes_taches(employe),
        },
    )
