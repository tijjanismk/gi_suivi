"""Couleurs et frise horaire partagées par la fiche personne et l'écran Journée.

Une frise : des blocs (debut, fin, type, libelle) placés en % d'une fenêtre horaire commune
(7 h–19 h, élargie si l'activité déborde), colorés par dossier (palette fixe) ou par nature.
"""

from __future__ import annotations

PALETTE = ["#2563eb", "#059669", "#7c3aed", "#d97706", "#db2777", "#0891b2", "#4f46e5", "#65a30d"]
COULEUR_INACTIF = "#e5e7eb"
COULEUR_A_CLASSER = "#9ca3af"
COULEUR_SANS_FICHIER = "#cbd5e1"
COULEUR_BROUILLON = "#fbbf24"
COULEUR_HORS_MESURE = "#f3f4f6"
COULEURS_FIXES = {
    "pause": COULEUR_INACTIF,
    "hors_mesure": COULEUR_HORS_MESURE,
    "a_classer": COULEUR_A_CLASSER,
    "brouillon": COULEUR_BROUILLON,
    "sans_fichier": COULEUR_SANS_FICHIER,
}
HEURE_MIN, HEURE_MAX = 7, 19


def _hm(secondes: int) -> str:
    s = int(secondes or 0)
    return f"{s // 3600} h {s % 3600 // 60:02d}"


def duree_courte(secondes: int) -> str:
    """« 45 min » sous l'heure, « 1 h 15 » au-delà (page « Mon activité »)."""
    s = int(secondes or 0)
    if 0 < s < 60:
        return "< 1 min"
    return f"{s // 60} min" if s < 3600 else _hm(s)


def couleur_dossier(couleurs: dict[str, str], dossier: str) -> str:
    return couleurs.setdefault(dossier, PALETTE[len(couleurs) % len(PALETTE)])


def frise(journees: list[dict], couleurs: dict[str, str]) -> list[dict]:
    """Place les blocs de chaque journée (rapports.journee_personne) sur une fenêtre commune ;
    rend les graduations horaires. Enrichit les blocs (x, largeur, couleur, heures) et les
    journées (actif_hm, pause_hm, hors_mesure_hm, amplitude_hm)."""
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
            b["couleur"] = (
                couleur_dossier(couleurs, b["libelle"])
                if b["type"] == "dossier"
                else COULEURS_FIXES[b["type"]]
            )
            b["heures"] = _hm(b["duree_s"])
        j["actif_hm"] = _hm(j["actif_s"])
        j["pause_hm"] = _hm(j["pause_s"])
        j["hors_mesure_hm"] = _hm(j["hors_mesure_s"])
        j["amplitude_hm"] = _hm(j["amplitude_s"])
    return [
        {"heure": h, "x": round(100 * (h - h_min) * 60 / etendue, 2)}
        for h in range(h_min, h_max + 1)
    ]


def legende(couleurs: dict[str, str]) -> list[dict]:
    return [{"dossier": d, "couleur": c} for d, c in couleurs.items()]


def contexte_couleurs() -> dict:
    return {
        "couleur_pause": COULEUR_INACTIF,
        "couleur_hors_mesure": COULEUR_HORS_MESURE,
        "couleur_a_classer": COULEUR_A_CLASSER,
        "couleur_brouillon": COULEUR_BROUILLON,
        "couleur_sans_fichier": COULEUR_SANS_FICHIER,
        "couleur_inactif": COULEUR_INACTIF,
    }
