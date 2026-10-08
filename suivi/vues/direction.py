"""Écrans de la direction (T02 à T07). Réservés à GI-Direction et au compte de consultation ;
chaque consultation est journalisée. Les chiffres viennent de suivi.rapports, le rendu est du
HTML + SVG côté serveur (ADR 0002 : pas de bibliothèque JavaScript de graphiques)."""

from __future__ import annotations

from datetime import date

from django.contrib import admin
from django.db.models import Max
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from identite.decorateurs import consultation_requise
from suivi import rapports
from suivi.models import Employe, Segment
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
def dossiers(request):
    """T03 : temps par dossier (barres) et tableau dossier × employé."""
    selection = selection_de(request.GET)
    journaliser(
        request, "consulter:dossiers", f"{selection.periode.debut}..{selection.periode.fin}"
    )
    rapport = rapports.dossiers(selection.periode)

    maxi = max((d["duree_s"] for d in rapport["dossiers"]), default=0) or 1
    noms: dict[int, str] = {}
    for d in rapport["dossiers"]:
        d["largeur_pct"] = round(100 * d["duree_s"] / maxi, 1)
        d["heures"] = _hm(d["duree_s"])
        for e in d["par_employe"]:
            noms[e["employe_id"]] = e["employe"]
    employes = sorted(noms.items(), key=lambda x: x[1])
    for d in rapport["dossiers"]:
        par_id = {e["employe_id"]: e["duree_s"] for e in d["par_employe"]}
        d["cellules"] = [
            {"duree_s": par_id.get(eid, 0), "heures": _hm(par_id[eid]) if eid in par_id else ""}
            for eid, _ in employes
        ]
    total = sum(d["duree_s"] for d in rapport["dossiers"])
    hors = rapport["a_classer_s"] + rapport["brouillon_s"] + rapport["sans_fichier_s"]
    return render(
        request,
        "suivi/dossiers.html",
        _contexte(
            request,
            selection,
            titre="Dossiers",
            rapport=rapport,
            employes=[nom for _, nom in employes],
            total_heures=_hm(total),
            hors_heures=_hm(hors),
            part_rattachee=str(indicateurs_pct(total, total + hors)) if total + hors else None,
            a_classer_heures=_hm(rapport["a_classer_s"]),
            brouillon_heures=_hm(rapport["brouillon_s"]),
            sans_fichier_heures=_hm(rapport["sans_fichier_s"]),
        ),
    )


PALETTE = ["#2563eb", "#059669", "#7c3aed", "#d97706", "#db2777", "#0891b2", "#4f46e5", "#65a30d"]
COULEUR_INACTIF, COULEUR_A_CLASSER, COULEUR_SANS_FICHIER, COULEUR_BROUILLON = (
    "#e5e7eb",
    "#9ca3af",
    "#cbd5e1",
    "#fbbf24",
)
HEURE_MIN, HEURE_MAX = 7, 19  # fenêtre de la chronologie (élargie si l'activité déborde)


@consultation_requise
def employes(request):
    """T04 : liste des personnes avec un état indicatif sur la période."""
    selection = selection_de(request.GET)
    journaliser(
        request, "consulter:employes", f"{selection.periode.debut}..{selection.periode.fin}"
    )
    synthese = rapports.synthese(selection.periode)
    debut, fin = rapports._bornes(selection.periode)
    dernieres = dict(
        Segment.objects.filter(debut__gte=debut, debut__lt=fin, etat=Segment.Etat.ACTIF)
        .values_list("employe_id")
        .annotate(d=Max("fin"))
        .values_list("employe_id", "d")
    )
    for e in synthese["employes"]:
        e["heures"] = _hm(e["effectif_s"])
        e["etat"] = _couleur(e["prevu_pct"], e["effectif_s"])
        derniere = dernieres.get(e["employe_id"])
        e["derniere_activite"] = timezone.localtime(derniere) if derniere else None
    return render(
        request,
        "suivi/employes.html",
        _contexte(request, selection, titre="Personnes", employes=synthese["employes"]),
    )


@consultation_requise
def employe(request, employe_id: int):
    """T04 : fiche d'une personne — journées, chronologie d'un jour colorée par dossier,
    fichiers et applications."""
    selection = selection_de(request.GET)
    personne = get_object_or_404(Employe, pk=employe_id)
    jour = None
    if request.GET.get("jour"):
        try:
            jour = date.fromisoformat(request.GET["jour"])
        except ValueError:
            jour = None
    journaliser(
        request,
        "consulter:employe",
        f"employé {personne.pk} {selection.periode.debut}..{selection.periode.fin}",
    )
    rapport = rapports.activite_employe(personne, selection.periode, jour)

    couleurs: dict[str, str] = {}
    for j in rapport["journees"]:
        j["couleur"] = _couleur(j["prevu_pct"], j["effectif_s"])
        j["heures"] = _hm(j["effectif_s"]) if j["effectif_s"] else ""
        j["actif"] = j["jour"] == rapport["jour"]
    for f in rapport["fichiers"]:
        f["heures"] = _hm(f["duree_s"])
        if f["dossier"] and f["dossier"] not in couleurs:
            couleurs[f["dossier"]] = PALETTE[len(couleurs) % len(PALETTE)]
    for a in rapport["applications"]:
        a["heures"] = _hm(a["duree_s"])

    heures = [int(s["debut"][:2]) for s in rapport["chronologie"]] + [
        int(s["fin"][:2]) + 1 for s in rapport["chronologie"]
    ]
    h_min = min([HEURE_MIN, *heures]) if heures else HEURE_MIN
    h_max = max([HEURE_MAX, *heures]) if heures else HEURE_MAX
    etendue = max(1, (h_max - h_min) * 60)
    for s in rapport["chronologie"]:
        d_min = int(s["debut"][:2]) * 60 + int(s["debut"][3:5]) - h_min * 60
        f_min = int(s["fin"][:2]) * 60 + int(s["fin"][3:5]) - h_min * 60
        s["x"] = round(100 * d_min / etendue, 2)
        s["largeur"] = round(100 * max(f_min - d_min, 1) / etendue, 2)
        if s["etat"] != "ACTIF":
            s["couleur"] = COULEUR_INACTIF
        elif s["dossier"]:
            s["couleur"] = couleurs.setdefault(s["dossier"], PALETTE[len(couleurs) % len(PALETTE)])
        elif s["statut"] == "a_classer":
            s["couleur"] = COULEUR_A_CLASSER
        elif s["statut"] == "brouillon":
            s["couleur"] = COULEUR_BROUILLON
        else:
            s["couleur"] = COULEUR_SANS_FICHIER
    graduations = [
        {"heure": h, "x": round(100 * (h - h_min) * 60 / etendue, 2)}
        for h in range(h_min, h_max + 1)
    ]
    return render(
        request,
        "suivi/employe.html",
        _contexte(
            request,
            selection,
            titre=str(personne),
            personne=personne,
            rapport=rapport,
            legende=[{"dossier": d, "couleur": c} for d, c in couleurs.items()],
            graduations=graduations,
            couleur_inactif=COULEUR_INACTIF,
            couleur_a_classer=COULEUR_A_CLASSER,
            couleur_sans_fichier=COULEUR_SANS_FICHIER,
            couleur_brouillon=COULEUR_BROUILLON,
        ),
    )


def indicateurs_pct(part: int, total: int):
    from moteur.suivi.indicateurs import pourcentage

    return pourcentage(part, total)


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
