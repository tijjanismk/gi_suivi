"""Écrans de la direction (T02 à T07). Réservés à GI-Direction et au compte de consultation ;
chaque consultation est journalisée. Les chiffres viennent de suivi.rapports, le rendu est du
HTML + SVG côté serveur (ADR 0002 : pas de bibliothèque JavaScript de graphiques)."""

from __future__ import annotations

from django.contrib import admin
from django.shortcuts import render

from identite.decorateurs import consultation_requise
from suivi import rapports
from suivi.services import journaliser
from suivi.vues.periode import selection_de


def _contexte(request, selection, **extra) -> dict:
    return {
        **admin.site.each_context(request),
        "selection": selection,
        "periode": selection.periode,
        "liens_periode": selection.liens(),
        "requete_periode": selection.requete,
        **extra,
    }


def _hm(secondes: int) -> str:
    return f"{secondes // 3600} h {secondes % 3600 // 60:02d}"


def _couleur(prevu_pct: str | None, effectif_s: int) -> str:
    """Classe de la cellule jour × employé : vert ≥ 80 % du prévu, jaune ≥ 50 %, rouge en
    dessous, gris quand rien n'est prévu (week-end, férié) ou rien de mesuré."""
    if prevu_pct is None:
        return "repos" if effectif_s == 0 else "hors_prevu"
    pct = float(prevu_pct)
    if effectif_s == 0:
        return "absent"
    if pct >= 80:
        return "bien"
    if pct >= 50:
        return "moyen"
    return "faible"


@consultation_requise
def vue_ensemble(request):
    selection = selection_de(request.GET)
    journaliser(
        request, "consulter:vue_ensemble", f"{selection.periode.debut}..{selection.periode.fin}"
    )
    synthese = rapports.synthese(selection.periode)

    maxi = max((e["effectif_s"] for e in synthese["employes"]), default=0) or 1
    for e in synthese["employes"]:
        e["largeur_pct"] = round(100 * e["effectif_s"] / maxi, 1)
        e["prevu_largeur_pct"] = (
            round(100 * min(e["prevu_s"], maxi) / maxi, 1) if e["prevu_s"] else 0
        )
        e["heures"] = f"{e['effectif_s'] // 3600} h {e['effectif_s'] % 3600 // 60:02d}"
        for j in e["journees"]:
            j["couleur"] = _couleur(j["prevu_pct"], j["effectif_s"])
            j["heures"] = (
                f"{j['effectif_s'] // 3600}h{j['effectif_s'] % 3600 // 60:02d}"
                if j["effectif_s"]
                else ""
            )
    jours = [j["jour"] for j in synthese["employes"][0]["journees"]] if synthese["employes"] else []

    return render(
        request,
        "suivi/vue_ensemble.html",
        _contexte(
            request,
            selection,
            titre="Vue d'ensemble",
            synthese=synthese,
            jours=jours,
            total_heures=_hm(synthese["effectif_s"]),
            a_classer_heures=_hm(synthese["a_classer_s"]),
            postes_rouges=sum(1 for p in rapports.etat_postes() if p["alerte"] == "rouge"),
        ),
    )
