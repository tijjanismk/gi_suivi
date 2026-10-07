from django.conf import settings
from django.shortcuts import render


def qui_suis_je(request):
    """Test manuel après chaque déploiement : login et groupes tels que l'application les voit."""
    return render(
        request,
        "identite/qui_suis_je.html",
        {
            "source": settings.IDENTITE_SOURCE,
            "direction": request.user.dans_groupe(settings.GROUPE_DIRECTION),
        },
    )


def refus_admin(request, extra_context=None):
    """Remplace la page de connexion de l'admin : pas de mot de passe, seulement un refus."""
    return render(
        request, "identite/refus.html", {"groupes": [settings.GROUPE_DIRECTION]}, status=403
    )
