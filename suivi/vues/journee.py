"""Écran « Journée » (accueil) : un jour, toutes les personnes — arrivée, départ, temps actif,
pauses, frise colorée par dossier ; et le détail d'une personne, bloc par bloc, pauses et trous
hors mesure compris."""

from __future__ import annotations

from datetime import date, timedelta

from django.contrib import admin
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from identite.decorateurs import consultation_requise
from suivi import rapports
from suivi.models import Employe
from suivi.services import journaliser
from suivi.vues.direction import (
    COULEUR_A_CLASSER,
    COULEUR_BROUILLON,
    COULEUR_INACTIF,
    COULEUR_SANS_FICHIER,
    HEURE_MAX,
    HEURE_MIN,
    PALETTE,
    _hm,
)

COULEUR_HORS_MESURE = "#f3f4f6"
COULEURS_FIXES = {
    "pause": COULEUR_INACTIF,
    "hors_mesure": COULEUR_HORS_MESURE,
    "a_classer": COULEUR_A_CLASSER,
    "brouillon": COULEUR_BROUILLON,
    "sans_fichier": COULEUR_SANS_FICHIER,
}


def _jour(request) -> date:
    brut = request.GET.get("jour")
    if brut:
        try:
            return date.fromisoformat(brut)
        except ValueError:
            pass
    return timezone.localdate()


def _frise(journees: list[dict], couleurs: dict[str, str]) -> tuple[list[dict], int, int]:
    """Positions (en % d'une frise 0-100) de chaque bloc ; fenêtre commune à toutes les lignes."""
    heures = [HEURE_MIN, HEURE_MAX]
    for j in journees:
        for b in j["blocs"]:
            heures += [b["debut"].hour, b["fin"].hour + 1]
    h_min, h_max = min(heures), min(max(heures), 24)
    etendue = max(1, (h_max - h_min) * 60)
    for j in journees:
        for b in j["blocs"]:
            d_min = b["debut"].hour * 60 + b["debut"].minute - h_min * 60
            f_min = b["fin"].hour * 60 + b["fin"].minute - h_min * 60
            b["x"] = round(100 * max(d_min, 0) / etendue, 2)
            b["largeur"] = round(100 * max(f_min - d_min, 1) / etendue, 2)
            if b["type"] == "dossier":
                b["couleur"] = couleurs.setdefault(
                    b["libelle"], PALETTE[len(couleurs) % len(PALETTE)]
                )
            else:
                b["couleur"] = COULEURS_FIXES[b["type"]]
            b["heures"] = _hm(b["duree_s"])
        j["actif_hm"] = _hm(j["actif_s"])
        j["pause_hm"] = _hm(j["pause_s"])
        j["hors_mesure_hm"] = _hm(j["hors_mesure_s"])
        j["amplitude_hm"] = _hm(j["amplitude_s"])
    graduations = [
        {"heure": h, "x": round(100 * (h - h_min) * 60 / etendue, 2)}
        for h in range(h_min, h_max + 1)
    ]
    return graduations, h_min, h_max


def _contexte_jour(request, jour: date, titre: str) -> dict:
    return {
        **admin.site.each_context(request),
        "titre": titre,
        "jour": jour,
        "veille": jour - timedelta(days=1),
        "lendemain": jour + timedelta(days=1),
        "aujourd_hui": timezone.localdate(),
        "couleur_pause": COULEUR_INACTIF,
        "couleur_hors_mesure": COULEUR_HORS_MESURE,
        "couleur_a_classer": COULEUR_A_CLASSER,
        "couleur_brouillon": COULEUR_BROUILLON,
        "couleur_sans_fichier": COULEUR_SANS_FICHIER,
    }


@consultation_requise
def journee(request):
    jour = _jour(request)
    journaliser(request, "consulter:journee", jour.isoformat())
    journees = rapports.journee_equipe(jour)
    couleurs: dict[str, str] = {}
    graduations, _, _ = _frise(journees, couleurs)
    return render(
        request,
        "suivi/journee.html",
        {
            **_contexte_jour(request, jour, "Journée"),
            "journees": journees,
            "graduations": graduations,
            "legende": [{"dossier": d, "couleur": c} for d, c in couleurs.items()],
            "presents": sum(1 for j in journees if j["arrivee"]),
            "total_actif_hm": _hm(sum(j["actif_s"] for j in journees)),
            "total_pause_hm": _hm(sum(j["pause_s"] for j in journees)),
        },
    )


@consultation_requise
def journee_personne(request, employe_id: int):
    jour = _jour(request)
    personne = get_object_or_404(Employe, pk=employe_id)
    journaliser(request, "consulter:journee_personne", f"employé {personne.pk} {jour}")
    j = rapports.journee_personne(personne, jour)
    couleurs: dict[str, str] = {}
    graduations, _, _ = _frise([j], couleurs)
    return render(
        request,
        "suivi/journee_personne.html",
        {
            **_contexte_jour(request, jour, f"{personne} — {jour:%A %d %B %Y}"),
            "personne": personne,
            "j": j,
            "graduations": graduations,
            "legende": [{"dossier": d, "couleur": c} for d, c in couleurs.items()],
        },
    )
