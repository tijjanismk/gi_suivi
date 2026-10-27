"""Import des diplômes lus sur les scans des dossiers d'experts (chantier 5, ADR 0012).

    manage.py experts_diplomes diplomes.csv --simuler   # montre, ne garde rien
    manage.py experts_diplomes diplomes.csv

Colonnes : dossier (« NOM Prénom », comme EXPERTS\\NOM Prénom), fichier (le scan, qui devient le
justificatif), intitule, etablissement, pays, annee, niveau (bac+2 à bac+8). Code de sortie 1
s'il y a des erreurs de ligne (les autres lignes sont gardées, sauf en simulation).
"""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from experts import services


class Command(BaseCommand):
    help = "Importe les diplômes des experts lus sur les scans (chantier 5)."

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
        rapport = services.importer_diplomes(lignes, simuler=simuler)
        for erreur in rapport.erreurs:
            self.stdout.write(f"ERREUR {erreur}")
        prefixe = "Simulation, rien n'est gardé : " if simuler else ""
        self.stdout.write(f"{prefixe}{len(lignes)} ligne(s) lue(s) ; {rapport.resume}.")
        if rapport.erreurs:
            raise SystemExit(1)
