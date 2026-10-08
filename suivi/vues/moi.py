"""Page « Mon activité du jour » : celle qu'ouvre l'icône de l'agent. Chaque personne y voit
ses propres heures, et rien d'autre (principe de transparence du blueprint)."""

from django.contrib import admin
from django.shortcuts import render

from suivi.services import activite_du_jour, employe_de
from suivi.vues.frise import duree_courte


def mon_activite(request):
    activite = activite_du_jour(employe_de(request.user))
    # durées lisibles : minutes sous l'heure, « h » au-delà (l'API, elle, reste en secondes)
    for ligne in [*activite["par_dossier"], *activite["par_application"]]:
        ligne["duree"] = duree_courte(ligne["duree_s"])
    activite["a_classer"] = duree_courte(activite["a_classer_s"])
    activite["sans_fichier"] = duree_courte(activite["sans_fichier_s"])
    return render(
        request, "suivi/moi.html", {**admin.site.each_context(request), "activite": activite}
    )
