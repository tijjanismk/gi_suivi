from __future__ import annotations

from functools import wraps

from django.shortcuts import render


def groupe_requis(*groupes: str):
    """Réserve une vue aux membres d'au moins un des groupes AD. Sinon 403, page de refus.

    @groupe_requis("GI-Direction")
    def vue_d_ensemble(request): ...
    """

    def decorateur(vue):
        @wraps(vue)
        def enveloppe(request, *args, **kwargs):
            u = request.user
            if getattr(u, "is_authenticated", False) and u.is_active and u.dans_groupe(*groupes):
                return vue(request, *args, **kwargs)
            return render(request, "identite/refus.html", {"groupes": groupes}, status=403)

        return enveloppe

    return decorateur


def consultation_requise(vue):
    """Écrans de consultation : direction ET compte « visionneuse » (lecture seule).

    Les actions (valider, rattacher, paramétrer) restent sous @groupe_requis(GROUPE_DIRECTION).
    """
    from django.conf import settings

    return groupe_requis(settings.GROUPE_DIRECTION, settings.GROUPE_DIRECTION_LECTURE)(vue)
