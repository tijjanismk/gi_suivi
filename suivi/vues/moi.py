"""Page « Mon activité du jour » : celle qu'ouvre l'icône de l'agent. Chaque personne y voit
ses propres heures, et rien d'autre (principe de transparence du blueprint)."""

from django.contrib import admin
from django.shortcuts import render

from suivi.services import activite_du_jour, employe_de


def mon_activite(request):
    activite = activite_du_jour(employe_de(request.user))
    return render(
        request, "suivi/moi.html", {**admin.site.each_context(request), "activite": activite}
    )
