from django.conf import settings
from django.contrib import admin
from django.shortcuts import render


def qui_suis_je(request):
    """Test manuel après chaque déploiement : login et groupes tels que l'application les voit."""
    return render(
        request,
        "identite/qui_suis_je.html",
        {
            **admin.site.each_context(request),  # menu latéral et thème Unfold
            "source": settings.IDENTITE_SOURCE,
            "direction": request.user.direction,
            "lecture_seule": request.user.lecture_seule,
        },
    )


def refus_admin(request, extra_context=None):
    """Remplace la page de connexion de l'admin : pas de mot de passe, seulement un refus."""
    contexte = {
        **admin.site.each_context(request),
        "groupes": [settings.GROUPE_DIRECTION, settings.GROUPE_DIRECTION_LECTURE],
    }
    return render(request, "identite/refus.html", contexte, status=403)
