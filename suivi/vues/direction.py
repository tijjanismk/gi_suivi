"""Écrans de la direction (T02 à T07). Réservés à GI-Direction et au compte de consultation ;
chaque consultation est journalisée. Les chiffres viennent de suivi.rapports, le rendu est du
HTML + SVG côté serveur (ADR 0002 : pas de bibliothèque JavaScript de graphiques)."""

from __future__ import annotations

from datetime import date, timedelta

from django.contrib import admin
from django.db.models import Max
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from identite.decorateurs import consultation_requise
from suivi import rapports
from suivi.applications import regrouper
from suivi.models import Dossier, Employe, Segment
from suivi.services import journaliser
from suivi.vues.frise import _hm, contexte_couleurs, couleur_dossier, frise, legende
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


def _filtre_dossier(selection) -> dict:
    """Pour les écrans qui acceptent le filtre dossier (T09) : la liste et le dossier choisi."""
    dossiers = Dossier.objects.exclude(statut=Dossier.Statut.CLOS).order_by("code", "nom")
    choisi = dossiers.filter(pk=selection.dossier_id).first() if selection.dossier_id else None
    # un identifiant inconnu est ignoré : on montre tout, pas rien
    return {
        "dossiers_filtre": dossiers,
        "dossier_filtre": choisi,
        "dossier_id": choisi.pk if choisi else None,
    }


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


@consultation_requise
def employes(request):
    """T04 : liste des personnes avec un état indicatif sur la période."""
    selection = selection_de(request.GET)
    journaliser(
        request, "consulter:employes", f"{selection.periode.debut}..{selection.periode.fin}"
    )
    filtre = _filtre_dossier(selection)
    synthese = rapports.synthese(selection.periode, filtre["dossier_id"])
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
        _contexte(
            request,
            selection,
            titre="Personnes",
            employes=synthese["employes"],
            **filtre,
        ),
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
    filtre = _filtre_dossier(selection)
    rapport = rapports.activite_employe(personne, selection.periode, jour, filtre["dossier_id"])
    jour_choisi = date.fromisoformat(rapport["jour"])

    couleurs: dict[str, str] = {}
    for f in rapport["fichiers"]:
        f["heures"] = _hm(f["duree_s"])
        if f["dossier"]:
            couleur_dossier(couleurs, f["dossier"])
    rapport["applications"] = regrouper(rapport["applications"])  # noms lisibles
    for a in rapport["applications"]:
        a["heures"] = _hm(a["duree_s"])

    # Jour par jour : arrivée, départ, actif, pauses, hors mesure (indépendants du filtre dossier)
    prevu = {j["jour"]: j for j in rapport["journees"]}
    jours: list[dict] = []
    d = selection.periode.debut
    while d <= selection.periode.fin:
        jd = rapports.journee_personne(personne, d)
        info = prevu.get(d.isoformat(), {})
        jd["prevu_pct"] = info.get("prevu_pct")
        jd["couleur"] = _couleur(jd["prevu_pct"], jd["actif_s"])
        jd["actif"] = d == jour_choisi
        jours.append(jd)
        d += timedelta(days=1)
    detail = next((jd for jd in jours if jd["actif"]), None) or rapports.journee_personne(
        personne, jour_choisi
    )
    graduations = frise([*jours, detail] if detail not in jours else jours, couleurs)

    prevu_total = sum(j["prevu_s"] for j in rapport["journees"])
    actif_total = sum(jd["actif_s"] for jd in jours)
    return render(
        request,
        "suivi/employe.html",
        _contexte(
            request,
            selection,
            titre=str(personne),
            **filtre,
            **contexte_couleurs(),
            personne=personne,
            rapport=rapport,
            jours=jours,
            detail=detail,
            jour_choisi=jour_choisi,
            titre_chronologie=f"Chronologie du {jour_choisi.isoformat()}",
            graduations=graduations,
            legende=legende(couleurs),
            totaux={
                "actif": _hm(actif_total),
                "pauses": _hm(sum(jd["pause_s"] for jd in jours)),
                "hors_mesure": _hm(sum(jd["hors_mesure_s"] for jd in jours)),
                "jours_travailles": sum(1 for jd in jours if jd["actif_s"]),
                "prevu_pct": str(indicateurs_pct(actif_total, prevu_total))
                if prevu_total
                else None,
            },
        ),
    )


@consultation_requise
def postes(request):
    """T07 : état des postes — version de l'agent, dernier envoi, démarrages, alertes."""
    journaliser(request, "consulter:postes")
    etats = rapports.etat_postes()
    derniers = {
        s.poste_id: s
        for s in Segment.objects.order_by("poste_id", "-debut")
        .distinct("poste_id")
        .select_related("employe")
    }
    for p in etats:
        dernier = derniers.get(p["id"])
        p["personne"] = str(dernier.employe) if dernier else None
        p["dernier_envoi_local"] = (
            timezone.datetime.fromisoformat(p["dernier_envoi"]) if p["dernier_envoi"] else None
        )
    return render(
        request,
        "suivi/postes.html",
        {
            **admin.site.each_context(request),
            "titre": "État des postes",
            "postes": etats,
            "rouges": sum(1 for p in etats if p["alerte"] == "rouge"),
            "oranges": sum(1 for p in etats if p["alerte"] == "orange"),
            "sains": sum(1 for p in etats if p["alerte"] is None),
            "versions": sorted({p["version_agent"] for p in etats if p["version_agent"]}),
        },
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
    filtre = _filtre_dossier(selection)
    synthese = rapports.synthese(selection.periode, filtre["dossier_id"])

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
            **filtre,
            synthese=synthese,
            jours=jours,
            total_heures=_hm(synthese["effectif_s"]),
            a_classer_heures=_hm(synthese["a_classer_s"]),
            postes_rouges=sum(1 for p in rapports.etat_postes() if p["alerte"] == "rouge"),
        ),
    )
