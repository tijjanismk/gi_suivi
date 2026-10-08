"""Purge nocturne (A07) : segments plus vieux que la rétention, demandes de recalcul traitées
depuis longtemps. Le journal d'accès n'est jamais purgé.

    manage.py suivi_purger            # supprime
    manage.py suivi_purger --simuler  # compte sans rien supprimer
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from suivi.models import DemandeRecalcul, Segment
from suivi.services import parametre

CONSERVATION_DEMANDES_TRAITEES_J = 90


def moins_des_mois(jour: date, mois: int) -> date:
    """`jour` reculé de `mois` mois civils, le quantième ramené au dernier jour si besoin."""
    total = jour.year * 12 + (jour.month - 1) - mois
    annee, mois_index = divmod(total, 12)
    premier_du_suivant = date(annee + (mois_index + 1) // 12, (mois_index + 1) % 12 + 1, 1)
    dernier_jour = (premier_du_suivant - timedelta(days=1)).day
    return date(annee, mois_index + 1, min(jour.day, dernier_jour))


def limite_retention(aujourd_hui: date | None = None) -> datetime:
    """Tout segment commencé avant cet instant est hors rétention."""
    aujourd_hui = aujourd_hui or timezone.localdate()
    mois = int(parametre("retention_mois", settings.SUIVI_RETENTION_MOIS) or 24)
    return timezone.make_aware(datetime.combine(moins_des_mois(aujourd_hui, mois), time.min))


class Command(BaseCommand):
    help = "Supprime les segments au-delà de la rétention (paramètre retention_mois, défaut 24)."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--simuler", action="store_true", help="compter sans supprimer")

    def handle(self, *args, simuler: bool = False, **options) -> None:
        limite = limite_retention()
        segments = Segment.objects.filter(debut__lt=limite)
        demandes = DemandeRecalcul.objects.filter(
            traitee_le__lt=timezone.now() - timedelta(days=CONSERVATION_DEMANDES_TRAITEES_J)
        )
        n_segments, n_demandes = segments.count(), demandes.count()
        if not simuler:
            segments.delete()
            demandes.delete()
        verbe = "à supprimer" if simuler else "supprimés"
        self.stdout.write(
            f"Rétention jusqu'au {timezone.localtime(limite):%d/%m/%Y} : "
            f"{n_segments} segments {verbe}, {n_demandes} demandes de recalcul traitées {verbe}."
        )
