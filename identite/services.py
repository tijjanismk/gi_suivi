from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from identite.groupes import lire_groupes
from identite.models import Utilisateur, normaliser_login

log = logging.getLogger(__name__)

# Pas d'écriture en base à chaque requête : la dernière activité est notée à 5 min près.
_PRECISION_ACTIVITE = timedelta(minutes=5)


def obtenir_utilisateur(login: str) -> Utilisateur:
    """L'utilisateur du login Windows, créé à sa première requête, groupes rafraîchis à 10 min."""
    maintenant = timezone.now()
    u, cree = Utilisateur.objects.get_or_create(login_windows=normaliser_login(login))
    if cree:
        u.set_unusable_password()
    champs: list[str] = ["password"] if cree else []

    validite = timedelta(seconds=settings.IDENTITE_GROUPES_VALIDITE_S)
    if cree or u.groupes_lus_le is None or maintenant - u.groupes_lus_le > validite:
        try:
            u.groupes = lire_groupes(u.login_windows)
            u.groupes_lus_le = maintenant
            champs += ["groupes", "groupes_lus_le"]
        except Exception:  # noqa: BLE001 — annuaire injoignable : on garde les groupes connus
            log.warning("Groupes AD non rafraîchis pour %s : groupes précédents conservés.", u)

    if u.derniere_activite is None or maintenant - u.derniere_activite > _PRECISION_ACTIVITE:
        u.derniere_activite = maintenant
        champs.append("derniere_activite")
    if champs:
        u.save(update_fields=champs)
    return u
