"""Saisit les racines de classement (et la correspondance des lecteurs) à partir du fichier de
configuration de l'agent, pour que le serveur et les postes classent avec les mêmes racines.

    manage.py suivi_racines agent\\config-pilote.json
    manage.py suivi_racines agent\\config-pilote.json --simuler
    manage.py suivi_racines agent\\config-pilote.json --desactiver-les-autres

Idempotent : une racine déjà saisie est mise à jour (profondeur, réactivée), les autres sont
laissées telles quelles sauf --desactiver-les-autres. Un recalcul est demandé si quelque chose
a changé (les segments « à classer » sont réexaminés avec les nouvelles racines)."""

from __future__ import annotations

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from suivi.models import Parametre, Racine
from suivi.services import CORRESPONDANCE_LECTEURS


class Command(BaseCommand):
    help = "Saisit les racines de classement à partir d'un config.json de l'agent."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "fichier", help="config.json de l'agent (racines, correspondance_lecteurs)"
        )
        parser.add_argument("--simuler", action="store_true", help="montrer sans écrire")
        parser.add_argument(
            "--desactiver-les-autres",
            action="store_true",
            help="désactiver les racines actives absentes du fichier",
        )

    def handle(self, *args, fichier: str, simuler: bool, **options) -> None:
        chemin = Path(fichier)
        if not chemin.exists():
            raise CommandError(f"Fichier introuvable : {chemin}")
        try:
            brut = json.loads(chemin.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as e:
            raise CommandError(f"JSON invalide : {e}") from e
        racines = brut.get("racines") or []
        if not racines:
            raise CommandError("Aucune racine dans le fichier.")

        change = False
        vus: set[str] = set()
        for r in racines:
            chemin_unc, profondeur = r["chemin"], int(r.get("profondeur", 1))
            vus.add(chemin_unc.lower())
            existante = Racine.objects.filter(chemin__iexact=chemin_unc).first()
            if existante is None:
                self.stdout.write(f"+ {chemin_unc} (profondeur {profondeur})")
                if not simuler:
                    Racine.objects.create(chemin=chemin_unc, profondeur=profondeur)
                change = True
            elif existante.profondeur != profondeur or not existante.active:
                self.stdout.write(
                    f"~ {chemin_unc} : profondeur {existante.profondeur} → {profondeur}, active"
                )
                if not simuler:
                    existante.profondeur, existante.active = profondeur, True
                    existante.save(update_fields=["profondeur", "active"])
                change = True
            else:
                self.stdout.write(f"= {chemin_unc} (profondeur {profondeur})")

        if options["desactiver_les_autres"]:
            for autre in Racine.objects.filter(active=True):
                if autre.chemin.lower() not in vus:
                    self.stdout.write(f"- {autre.chemin} : désactivée")
                    if not simuler:
                        autre.active = False
                        autre.save(update_fields=["active"])
                    change = True

        lecteurs = brut.get("correspondance_lecteurs")
        if lecteurs:
            self.stdout.write(f"correspondance_lecteurs : {lecteurs}")
            if not simuler:
                Parametre.objects.update_or_create(
                    cle=CORRESPONDANCE_LECTEURS,
                    defaults={
                        "valeur": lecteurs,
                        "description": "Lettre de lecteur réseau → chemin UNC.",
                    },
                )

        if change and not simuler:
            # chaque racine créée ou modifiée a déjà déposé sa demande (signaux) ; on le dit
            self.stdout.write("Recalcul demandé (suivi_recalculer).")
        actives = Racine.objects.filter(active=True).count()
        self.stdout.write(f"{'Simulation : ' if simuler else ''}{actives} racine(s) active(s).")
