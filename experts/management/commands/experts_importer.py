"""Import du registre du chantier 5, `EXPERTS\\_registre\\experts.csv` (ADR 0012).

    manage.py experts_importer experts.csv --simuler
    manage.py experts_importer experts.csv

Colonnes reconnues : dossier (« NOM Prénom ») ou nom et prenoms, categorie, specialite, actif
(oui / non). Les affectations ne viennent pas du registre : elles se saisissent avec leur preuve.
"""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from experts import services


class Command(BaseCommand):
    help = "Importe le registre des experts (chantier 5)."

    def add_arguments(self, parser) -> None:
        parser.add_argument("fichier")
        parser.add_argument("--simuler", action="store_true", help="afficher sans rien garder")

    def handle(self, *args, fichier: str, simuler: bool = False, **options) -> None:
        chemin = Path(fichier)
        if not chemin.is_file():
            raise CommandError(f"fichier introuvable : {chemin}")
        try:
            lignes = services.lire_csv(chemin.read_text(encoding="utf-8-sig"))
        except (ValueError, UnicodeDecodeError) as e:
            raise CommandError(f"{chemin.name} : {e}") from e
        rapport = services.importer(lignes, simuler=simuler)
        for erreur in rapport.erreurs:
            self.stdout.write(f"ERREUR {erreur}")
        prefixe = "Simulation, rien n'est gardé : " if simuler else ""
        self.stdout.write(f"{prefixe}{len(lignes)} ligne(s) lue(s) ; {rapport.resume}.")
        if rapport.erreurs:
            raise SystemExit(1)
