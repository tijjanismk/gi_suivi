"""T06 — la file « à classer » : groupes (fichier, chemin, personne), rattachement en un clic
à un dossier par une exception (chemin exact, dossier parent ou mot-clé), brouillons signalés.
Le compteur baisse après rattachement parce que le recalcul suit immédiatement."""

from __future__ import annotations

from django.conf import settings
from django.contrib import admin, messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from identite.decorateurs import consultation_requise, groupe_requis
from suivi import rapports
from suivi.models import Dossier, Segment
from suivi.services import journaliser, rattacher
from suivi.vues.periode import selection_de

TYPES = (
    ("chemin", "ce fichier seulement (chemin exact)"),
    ("prefixe", "tout le dossier qui le contient"),
    ("mot_cle", "tout chemin contenant ce mot-clé"),
)


def _hm(secondes) -> str:
    s = int(secondes or 0)
    return f"{s // 3600} h {s % 3600 // 60:02d}"


@consultation_requise
def a_classer(request):
    selection = selection_de(request.GET)
    journaliser(
        request, "consulter:a_classer", f"{selection.periode.debut}..{selection.periode.fin}"
    )
    rapport = rapports.a_classer(selection.periode)
    total = 0
    for g in rapport["groupes"]:
        total += g["duree_s"]
        g["heures"] = _hm(g["duree_s"])
        g["dernier_local"] = timezone.localtime(timezone.datetime.fromisoformat(g["dernier"]))
        g["rattachable"] = bool(
            g["chemin"]
        )  # un nom seul (PDF dans un navigateur) ne se rattache pas
        g["dossier_parent"] = (
            g["chemin"].rsplit("\\", 1)[0] if g["chemin"] and "\\" in g["chemin"] else ""
        )
    dossiers = Dossier.objects.exclude(statut=Dossier.Statut.CLOS).order_by("statut", "code", "nom")
    return render(
        request,
        "suivi/a_classer.html",
        {
            **admin.site.each_context(request),
            "titre": "À classer",
            "selection": selection,
            "periode": selection.periode,
            "liens_periode": selection.liens(),
            "requete_periode": selection.requete,
            "groupes": rapport["groupes"],
            "nb_groupes": len(rapport["groupes"]),
            "total_heures": _hm(total),
            "brouillons": rapport["brouillons"],
            "brouillons_heures": _hm(rapport["brouillons"]["duree_s"]),
            "dossiers": dossiers,
            "types": TYPES,
            "peut_agir": request.user.direction,
        },
    )


@require_POST
@groupe_requis(settings.GROUPE_DIRECTION)
def rattacher_groupe(request):
    retour = request.POST.get("retour") or "/suivi/a-classer/"
    if not retour.startswith("/suivi/a-classer/"):
        retour = "/suivi/a-classer/"
    segment = get_object_or_404(Segment, pk=request.POST.get("segment"))
    dossier = get_object_or_404(Dossier, pk=request.POST.get("dossier"))
    if segment.statut_classement != Segment.StatutClassement.A_CLASSER:
        messages.warning(request, "Ce groupe n'est plus à classer (déjà rattaché ?).")
        return redirect(retour)
    try:
        regle, resultat = rattacher(
            segment, dossier, request.POST.get("type"), request.POST.get("motif", ""), request.user
        )
    except ValueError as e:
        messages.error(request, str(e))
        return redirect(retour)
    journaliser(
        request,
        "rattacher",
        f"segment {segment.pk} → dossier {dossier.pk} par {regle.type} « {regle.motif} »",
    )
    messages.success(
        request,
        f"{resultat['modifies']} segment(s) rattaché(s) à {dossier} — règle « {regle.motif} » "
        f"({regle.get_type_display()}) ; elle s'appliquera aussi aux prochains.",
    )
    return redirect(retour)
