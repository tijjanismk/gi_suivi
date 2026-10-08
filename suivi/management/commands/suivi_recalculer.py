"""Traite la file de recalcul (A03). Appelée toutes les 10 min par une tâche planifiée (A07).

manage.py suivi_recalculer          # ne fait rien si aucune demande n'attend
manage.py suivi_recalculer --force  # reclasse quand même
"""

from django.core.management.base import BaseCommand

from suivi.models import DemandeRecalcul
from suivi.services import recalculer


class Command(BaseCommand):
    help = "Reclasse les segments après validation d'un dossier, exception ou racine modifiée."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--force", action="store_true", help="recalculer même sans demande")

    def handle(self, *args, force: bool = False, **options) -> None:
        if not force and not DemandeRecalcul.objects.filter(traitee_le=None).exists():
            self.stdout.write("Rien à recalculer.")
            return
        r = recalculer()
        self.stdout.write(
            f"{r['examines']} segments examinés, {r['modifies']} modifiés, "
            f"{r['demandes']} demande(s) traitée(s)."
        )
