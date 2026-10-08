"""Sélecteur de période des écrans direction (T09) : 7 jours, semaine en cours, 30 jours, mois
en cours, ou dates libres ; et un filtre dossier. Tout vit dans l'URL (debut, fin, p, dossier) :
un lien se partage."""

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
    dossier_id: int | None = None  # filtre dossier, sur les écrans qui le proposent
    erreur: str | None = None

    def _params(self, **extra) -> dict:
        params = (
            {"p": self.prereglage}
            if self.prereglage
            else {"debut": self.periode.debut.isoformat(), "fin": self.periode.fin.isoformat()}
        )
        params.update(extra)
        if self.dossier_id and "dossier" not in extra:
            params["dossier"] = self.dossier_id
        return {k: v for k, v in params.items() if v not in (None, "")}

    def liens(self) -> list[dict]:
        return [
            {
                "cle": cle,
                "libelle": libelle,
                "actif": cle == self.prereglage,
                "url": "?" + urlencode(self._params(p=cle, debut=None, fin=None)),
            }
            for cle, libelle in PREREGLAGES
        ]

    @property
    def requete(self) -> str:
        """Paramètres à reporter dans les liens vers les autres écrans."""
        return urlencode(self._params())

    @property
    def requete_sans_dossier(self) -> str:
        """Même période, filtre dossier retiré (lien « tous » du sélecteur)."""
        return urlencode(self._params(dossier=None))


def selection_de(params) -> Selection:
    """Pré-réglage `p` s'il est connu ; sinon debut/fin ; sinon 7 derniers jours.
    Une période invalide donne les 7 derniers jours et un message. `dossier` : entier ou rien."""
    aujourd_hui = timezone.localdate()
    dossier_id = None
    if params.get("dossier"):
        try:
            dossier_id = int(params["dossier"]) or None
        except (TypeError, ValueError):
            dossier_id = None
    p = params.get("p")
    if p:
        periode = _prereglage(p, aujourd_hui)
        if periode:
            return Selection(periode, p, dossier_id)
    if params.get("debut") or params.get("fin"):
        try:
            return Selection(periode_depuis(params), None, dossier_id)
        except ValueError as e:
            return Selection(_prereglage("7j", aujourd_hui), "7j", dossier_id, str(e))
    return Selection(_prereglage("7j", aujourd_hui), "7j", dossier_id)
