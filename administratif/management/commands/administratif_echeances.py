"""Rappel des échéances des pièces administratives (ADR 0010, § 7 ; AD06), chaque matin par la
tâche planifiée « GIC <env> - pièces administratives ». Écrit l'état des pièces à traiter dans la
sortie (journal de la tâche) et rend le code de sortie 1 s'il y a une pièce expirée parmi celles
exigées par défaut, pour qu'une supervision simple puisse réagir.

    manage.py administratif_echeances
    manage.py administratif_echeances --date 2026-11-12   # état à une autre date
"""

from __future__ import annotations

from datetime import date

from django.core.management.base import BaseCommand, CommandError

from administratif import services
from moteur.administratif.echeances import Etat


class Command(BaseCommand):
    help = (
        "Pièces expirées, à renouveler ou manquantes ; "
        "code de sortie 1 si une pièce exigée est expirée."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("--date", help="date de référence AAAA-MM-JJ (aujourd'hui par défaut)")

    def handle(self, *args, date: str | None = None, **options) -> None:
        try:
            reference = _date(date)
        except ValueError as e:
            raise CommandError(str(e)) from e
        lignes = services.registre(reference)
        for x in sorted(lignes, key=lambda x: x.type.ordre):
            if not x.alerte:
                continue
            marque = {
                Etat.EXPIREE: "EXPIRÉE",
                Etat.A_RENOUVELER: "À RENOUVELER",
                Etat.MANQUANTE: "MANQUANTE",
            }[x.etat.etat]
            demande = (
                f" ; demandée le {x.demande.demandee_le:%d/%m/%Y}" if x.demande else " ; à demander"
            )
            self.stdout.write(f"{marque:<13} {x.type.code} : {x.libelle_etat}{demande}")
        n = services.compteurs(lignes)
        self.stdout.write(
            f"{len(lignes)} type(s) au {reference:%d/%m/%Y} : {n['expirees']} expirée(s), "
            f"{n['a_renouveler']} à renouveler, {n['manquantes']} manquante(s) exigée(s)."
        )
        if any(x.etat.etat == Etat.EXPIREE and x.exigee for x in lignes):
            raise SystemExit(1)


def _date(valeur: str | None) -> date:
    from django.utils import timezone

    if not valeur:
        return timezone.localdate()
    try:
        return date.fromisoformat(valeur)
    except ValueError as e:
        raise ValueError("--date : AAAA-MM-JJ attendu") from e
