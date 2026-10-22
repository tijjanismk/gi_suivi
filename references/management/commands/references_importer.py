"""Import de la liste maîtresse des missions (chantier 2, onglet Missions ; ADR 0008, § 5).

    manage.py references_importer liste-maitresse.csv --simuler   # montre, ne garde rien
    manage.py references_importer liste-maitresse.csv

Colonnes : code, statut_code, absorbe_par, intitule_court, client, annee, nature, categorie,
montant, source_word, numero_source, observations (séparateur « ; » ou « , », UTF-8).
Code de sortie 1 s'il y a des erreurs de ligne (les lignes valides sont importées quand même,
sauf en simulation).
"""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from references import services


class Command(BaseCommand):
    help = "Importe la liste maîtresse des missions (CSV de l'onglet Missions)."

    def add_arguments(self, parser) -> None:
        parser.add_argument("fichier", help="CSV de l'onglet Missions")
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
        for absorption in rapport.absorbees:
            self.stdout.write(f"ABSORBÉE {absorption}")
        prefixe = "Simulation, rien n'est gardé : " if simuler else ""
        self.stdout.write(f"{prefixe}{len(lignes)} ligne(s) lue(s) ; {rapport.resume}.")
        if rapport.erreurs:
            raise SystemExit(1)
