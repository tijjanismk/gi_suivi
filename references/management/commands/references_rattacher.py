"""Rattachement en masse des justificatifs posés dans REFERENCES\\02_JUSTIFICATIFS (chantier 3,
ADR 0011).

    manage.py references_rattacher --simuler   # montre, ne garde rien
    manage.py references_rattacher
    manage.py references_rattacher --detail    # liste aussi les références incomplètes

Seules les références dont GARDE.pdf, SIGNATURE.pdf et ATTESTATION.pdf sont tous trois là sont
rattachées ; les pièces restent à auditer à l'écran. Code de sortie 1 s'il y a des erreurs (les
références sans erreur sont rattachées quand même, sauf en simulation).
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from administratif.services import PartageIndisponibleError
from references import justificatifs as js


class Command(BaseCommand):
    help = "Rattache les justificatifs des références complètes (chantier 3)."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--simuler", action="store_true", help="afficher sans rien garder")
        parser.add_argument(
            "--detail", action="store_true", help="lister aussi les références incomplètes"
        )

    def handle(self, *args, simuler: bool = False, detail: bool = False, **options) -> None:
        try:
            rapport = js.rattacher_dossiers(simuler=simuler)
        except (PartageIndisponibleError, OSError) as e:
            raise CommandError(str(e)) from e
        for erreur in rapport.erreurs:
            self.stdout.write(f"ERREUR {erreur}")
        if detail:
            for incomplete in rapport.incompletes:
                self.stdout.write(f"INCOMPLÈTE {incomplete}")
        prefixe = "Simulation, rien n'est gardé : " if simuler else ""
        self.stdout.write(f"{prefixe}{rapport.resume}.")
        if rapport.erreurs:
            raise SystemExit(1)
