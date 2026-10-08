"""Sélecteur de période des écrans direction (T09) : 7 jours, semaine en cours, 30 jours, mois
en cours, ou dates libres. La période vit dans l'URL (debut, fin, p) : un lien se partage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from urllib.parse import urlencode

from django.utils import timezone

from suivi.rapports import Periode, periode_depuis

PREREGLAGES = (
    ("7j", "7 derniers jours"),
    ("semaine", "Semaine en cours"),
    ("30j", "30 derniers jours"),
    ("mois", "Mois en cours"),
)


def _prereglage(cle: str, aujourd_hui: date) -> Periode | None:
    if cle == "7j":
        return Periode(aujourd_hui - timedelta(days=6), aujourd_hui)
    if cle == "semaine":
        lundi = aujourd_hui - timedelta(days=aujourd_hui.weekday())
        return Periode(lundi, aujourd_hui)
    if cle == "30j":
        return Periode(aujourd_hui - timedelta(days=29), aujourd_hui)
    if cle == "mois":
        return Periode(aujourd_hui.replace(day=1), aujourd_hui)
    return None


@dataclass(frozen=True)
class Selection:
    periode: Periode
    prereglage: str | None  # "7j", "semaine", … ou None pour des dates libres
    erreur: str | None = None

    def liens(self) -> list[dict]:
        return [
            {"cle": cle, "libelle": libelle, "actif": cle == self.prereglage, "url": f"?p={cle}"}
            for cle, libelle in PREREGLAGES
        ]

    @property
    def requete(self) -> str:
        """Paramètres à reporter dans les liens vers les autres écrans."""
        if self.prereglage:
            return urlencode({"p": self.prereglage})
        return urlencode(
            {"debut": self.periode.debut.isoformat(), "fin": self.periode.fin.isoformat()}
        )


def selection_de(params) -> Selection:
    """Pré-réglage `p` s'il est connu ; sinon debut/fin ; sinon 7 derniers jours.
    Une période invalide donne les 7 derniers jours et un message."""
    aujourd_hui = timezone.localdate()
    p = params.get("p")
    if p:
        periode = _prereglage(p, aujourd_hui)
        if periode:
            return Selection(periode, p)
    if params.get("debut") or params.get("fin"):
        try:
            return Selection(periode_depuis(params), None)
        except ValueError as e:
            return Selection(_prereglage("7j", aujourd_hui), "7j", str(e))
    return Selection(_prereglage("7j", aujourd_hui), "7j")
