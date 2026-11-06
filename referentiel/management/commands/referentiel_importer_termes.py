"""Import des décisions du porteur sur les termes proposés par la collecte du 06/11/2026
(ADR 0019, `synonymes-a-valider.csv`).

    manage.py referentiel_importer_termes synonymes.csv --par "GICONSEILS\\odicko" --simuler
    manage.py referentiel_importer_termes synonymes.csv --par "GICONSEILS\\odicko"

Colonnes : type_ouvrage, synonyme, la colonne « decision » (oui / non / une clé de type), et en
option pays_propose, portee_proposee, exemple, nb_avis, nb_avis_api_bm. `--par` est le login
Windows de la personne qui a décidé (comme dans l'application) : elle est notée sur chaque terme.
Code de sortie 1 s'il y a des erreurs de ligne (les autres lignes sont gardées, sauf en
simulation).
"""

from __future__ import annotations

from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from identite.models import normaliser_login
from referentiel import services


class Command(BaseCommand):
    help = "Importe les décisions du porteur sur les termes des types d'ouvrages (ADR 0019)."

    def add_arguments(self, parser) -> None:
        parser.add_argument("fichier", help="CSV des synonymes avec la colonne « decision »")
        parser.add_argument("--par", required=True, help="login Windows de la personne qui décide")
        parser.add_argument("--simuler", action="store_true", help="afficher sans rien garder")

    def handle(self, *args, fichier: str, par: str, simuler: bool = False, **options) -> None:
        chemin = Path(fichier)
        if not chemin.is_file():
            raise CommandError(f"fichier introuvable : {chemin}")
        try:
            personne = get_user_model().objects.get_by_natural_key(normaliser_login(par))
        except get_user_model().DoesNotExist as e:
            raise CommandError(f"utilisateur inconnu : {par}") from e
        try:
            lignes = services.lire_csv(chemin.read_text(encoding="utf-8-sig"))
        except (ValueError, UnicodeDecodeError) as e:
            raise CommandError(f"{chemin.name} : {e}") from e
        rapport = services.importer_decisions(lignes, personne, source=chemin.name, simuler=simuler)
        for ligne in rapport.types_a_creer:
            self.stdout.write(f"TYPE À CRÉER {ligne}")
        for ligne in rapport.conflits:
            self.stdout.write(f"CONFLIT {ligne}")
        for ligne in rapport.erreurs:
            self.stdout.write(f"ERREUR {ligne}")
        prefixe = "Simulation, rien n'est gardé : " if simuler else ""
        self.stdout.write(f"{prefixe}{len(lignes)} ligne(s) lue(s) ; {rapport.resume}.")
        if rapport.erreurs:
            raise SystemExit(1)
