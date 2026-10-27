"""Recodage de références avant la production (ADR 0014 § 3).

    manage.py references_recoder <table> --simuler
    manage.py references_recoder <table>

La table est rangée avec les registres, par exemple
D:/GIC/REFERENCES/00_REGISTRE/recodages/2026-10-27-vrd.csv (les données ne vont pas dans Git).
Change, dans la base, le code, les domaines et le chemin des pièces de chaque référence de la
table. Les fichiers se déplacent sur le partage par `Recoder-Missions.ps1`, avec la même table.
Refusée en production. Code de sortie 1 s'il y a des erreurs (les lignes sans erreur sont
recodées quand même, sauf en simulation).
"""

from __future__ import annotations

import getpass
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from references import recodage


class Command(BaseCommand):
    help = "Recode des références avant la production (ADR 0014), d'après une table."

    def add_arguments(self, parser) -> None:
        parser.add_argument("table", help="CSV « ; » : Ancien, Nouveau, Domaine, Secondaires")
        parser.add_argument("--simuler", action="store_true", help="afficher sans rien garder")

    def handle(self, *args, table: str, simuler: bool = False, **options) -> None:
        try:
            lignes = recodage.lire_table(Path(table).read_text(encoding="utf-8"))
            rapport = recodage.recoder(lignes, simuler=simuler, par=getpass.getuser())
        except (OSError, ValueError, recodage.RecodageRefuseError) as e:
            raise CommandError(str(e)) from e
        for fait in rapport.faits:
            self.stdout.write(f"{'SIMULÉ' if simuler else 'RECODÉ'} {fait}")
        for passe in rapport.passes:
            self.stdout.write(f"DÉJÀ   {passe}")
        for erreur in rapport.erreurs:
            self.stdout.write(f"ERREUR {erreur}")
        for code in rapport.retires:
            self.stdout.write(f"{'SERAIT RETIRÉ' if simuler else 'RETIRÉ'} domaine {code}")
        prefixe = "Simulation, rien n'est gardé : " if simuler else ""
        self.stdout.write(f"{prefixe}{rapport.resume}.")
        if rapport.erreurs:
            raise SystemExit(1)
