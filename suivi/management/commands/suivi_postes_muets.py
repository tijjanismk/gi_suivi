"""Alertes des postes (A07), chaque heure ouvrée : rouge = muet depuis plus de 24 h ouvrées ou
jamais vu envoyer ; orange = trop de démarrages dans la semaine. Le calcul vit dans
suivi.rapports.etat_postes (le même que l'écran et /api/postes/etat) ; la commande l'écrit dans
la sortie (journal de la tâche planifiée) et rend un code de sortie non nul s'il y a du rouge,
pour qu'une supervision simple puisse réagir.

    manage.py suivi_postes_muets
    manage.py suivi_postes_muets --remettre-demarrages   # le lundi : compteur hebdomadaire à zéro
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from suivi.models import Poste
from suivi.rapports import etat_postes


class Command(BaseCommand):
    help = (
        "Liste les postes muets (rouge) ou instables (orange) ; code de sortie 1 s'il y a du rouge."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--remettre-demarrages",
            action="store_true",
            help="remettre à zéro le compteur de démarrages de la semaine (à planifier le lundi)",
        )

    def handle(self, *args, remettre_demarrages: bool = False, **options) -> None:
        if remettre_demarrages:
            n = Poste.objects.exclude(demarrages_semaine=0).update(demarrages_semaine=0)
            self.stdout.write(f"Compteur de démarrages remis à zéro sur {n} poste(s).")
        etats = etat_postes()
        rouges = [p for p in etats if p["alerte"] == "rouge"]
        oranges = [p for p in etats if p["alerte"] == "orange"]
        for p in rouges:
            depuis = (
                f"muet depuis {p['muet_depuis_h_ouvrees']} h ouvrées"
                if p["muet_depuis_h_ouvrees"] is not None
                else "n'a jamais envoyé"
            )
            self.stdout.write(f"ROUGE  {p['nom']} : {depuis}")
        for p in oranges:
            self.stdout.write(
                f"ORANGE {p['nom']} : {p['demarrages_semaine']} démarrages cette semaine"
            )
        self.stdout.write(
            f"{len(etats)} poste(s), {len(rouges)} rouge(s), {len(oranges)} orange(s)."
        )
        if rouges:
            raise SystemExit(1)
