"""Premier remplissage du registre des pièces administratives (chantier 8, ADR 0010).

    manage.py administratif_importer registre.csv --simuler   # montre, ne garde rien
    manage.py administratif_importer registre.csv

Colonnes : type (code du type de pièce), fichier (nom du fichier dans le dossier du type),
emise_le, valide_jusqu_au (vide : règle du type), numero, rescan (oui : meilleur scan de la
version précédente). Code de sortie 1 s'il y a des erreurs de ligne (les autres lignes sont
enregistrées quand même, sauf en simulation).
"""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from administratif import services


class Command(BaseCommand):
    help = "Enregistre les pièces administratives déjà posées sur le partage (chantier 8)."

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
