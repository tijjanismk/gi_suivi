"""Ce qui déclenche une demande de recalcul (A03) : une exception créée ou retirée, une racine
ajoutée, modifiée ou désactivée. La validation d'un dossier passe par services.valider_dossier."""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from suivi.models import Racine, RegleException
from suivi.services import demander_recalcul


@receiver([post_save, post_delete], sender=RegleException)
def _exception_changee(sender, instance, **kwargs) -> None:
    demander_recalcul(f"exception {instance.get_type_display()} « {instance.motif} »")


@receiver([post_save, post_delete], sender=Racine)
def _racine_changee(sender, instance, **kwargs) -> None:
    demander_recalcul(f"racine {instance.chemin}")
