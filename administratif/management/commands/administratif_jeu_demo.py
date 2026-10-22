"""Base d'essai : remplit la base locale de pièces fictives et écrit leurs PDF dans un dossier
LOCAL qui joue le rôle du partage. Pour essayer les écrans sur un poste de développement, jamais
sur le serveur (la commande refuse un chemin réseau et une base qui a déjà des versions).

    manage.py administratif_jeu_demo --partage C:\\dev\\essai-gic
    puis, dans .env : PARTAGE_GIC=C:\\dev\\essai-gic   (et redémarrer le serveur de développement)
"""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from administratif import demo
from administratif.models import PieceAdministrative


class Command(BaseCommand):
    help = (
        "Crée des pièces administratives fictives dans un dossier local (poste de développement)."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("--partage", required=True, help="dossier local qui joue le partage")

    def handle(self, *args, partage: str, **options) -> None:
        if PieceAdministrative.objects.exists():
            raise CommandError(
                "la base a déjà des versions : jeu fictif refusé (base d'essai vide)"
            )
        racine = Path(partage)
        try:
            resultat = demo.remplir(racine)
        except ValueError as e:
            raise CommandError(str(e)) from e
        self.stdout.write(
            f"{resultat['versions']} versions fictives enregistrées ; fichiers dans {racine}.\n"
            f"Pour que l'application les lise : PARTAGE_GIC={racine} dans .env, puis redémarrer."
        )
