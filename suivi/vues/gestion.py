"""T05 — gestion des dossiers : racines (lecture), dossiers détectés à valider avec le temps déjà
enregistré, dossiers actifs modifiables, dossiers clos. Formulaires classiques (POST + redirection),
jeton CSRF, journal d'accès. La consultation seule voit tout sans aucun bouton."""

from __future__ import annotations

from django.conf import settings
from django.contrib import admin, messages
from django.db.models import Count, Max, Min, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from identite.decorateurs import consultation_requise, groupe_requis
from suivi.models import Dossier, Employe, Racine
from suivi.services import journaliser, valider_dossier

ACTIF = Q(segments__etat="ACTIF")


def _hm(secondes) -> str:
    s = int(secondes or 0)
    return f"{s // 3600} h {s % 3600 // 60:02d}"


def _avec_temps(qs):
    return qs.select_related("racine", "responsable").annotate(
        duree_s=Sum("segments__duree_s", filter=ACTIF),
        premiere=Min("segments__debut", filter=ACTIF),
        derniere=Max("segments__fin", filter=ACTIF),
        nb_segments=Count("segments", filter=ACTIF),
    )


@consultation_requise
def gestion_dossiers(request):
    journaliser(request, "consulter:gestion_dossiers")
    racines = Racine.objects.annotate(nb_dossiers=Count("dossiers")).order_by("chemin")
    detectes = list(
        _avec_temps(Dossier.objects.filter(statut=Dossier.Statut.DETECTE)).order_by("-duree_s")
    )
    actifs = list(
        _avec_temps(Dossier.objects.filter(statut=Dossier.Statut.ACTIF)).order_by("code", "nom")
    )
    clos = list(
        _avec_temps(Dossier.objects.filter(statut=Dossier.Statut.CLOS)).order_by("code", "nom")
    )
    for d in detectes + actifs + clos:
        d.heures = _hm(d.duree_s)
        d.premiere_locale = timezone.localtime(d.premiere) if d.premiere else None
        d.derniere_locale = timezone.localtime(d.derniere) if d.derniere else None
    return render(
        request,
        "suivi/gestion_dossiers.html",
        {
            **admin.site.each_context(request),
            "titre": "Gestion des dossiers",
            "racines": racines,
            "detectes": detectes,
            "actifs": actifs,
            "clos": clos,
            "employes": Employe.objects.filter(actif=True).order_by("nom_affiche", "login"),
            "peut_agir": request.user.direction,
        },
    )


def _champs(request) -> tuple[dict, str | None]:
    champs: dict = {}
    nom = request.POST.get("nom", "").strip()
    if "nom" in request.POST:
        if not nom:
            return {}, "Le nom ne peut pas être vide."
        champs["nom"] = nom[:300]
    if "client" in request.POST:
        champs["client"] = request.POST.get("client", "").strip()[:200]
    if "responsable" in request.POST:
        valeur = request.POST.get("responsable", "").strip()
        if not valeur:
            champs["responsable"] = None
        else:
            responsable = Employe.objects.filter(pk=valeur).first()
            if responsable is None:
                return {}, "Responsable inconnu."
            champs["responsable"] = responsable
    return champs, None


@require_POST
@groupe_requis(settings.GROUPE_DIRECTION)
def valider(request, dossier_id: int):
    dossier = get_object_or_404(Dossier, pk=dossier_id)
    champs, erreur = _champs(request)
    if erreur:
        messages.error(request, erreur)
    elif dossier.valide:
        messages.warning(request, f"{dossier} est déjà validé.")
    else:
        valider_dossier(dossier, request.user, **champs)
        journaliser(request, "valider_dossier", f"dossier {dossier.pk} {dossier}")
        messages.success(request, f"Dossier {dossier} validé ; le recalcul est demandé.")
    return redirect("suivi:gestion_dossiers")


@require_POST
@groupe_requis(settings.GROUPE_DIRECTION)
def modifier(request, dossier_id: int):
    dossier = get_object_or_404(Dossier, pk=dossier_id)
    champs, erreur = _champs(request)
    statut = request.POST.get("statut")
    if statut:
        if statut not in (Dossier.Statut.ACTIF, Dossier.Statut.CLOS):
            erreur = erreur or "Statut inconnu."
        else:
            champs["statut"] = statut
    if erreur:
        messages.error(request, erreur)
    elif not champs:
        messages.warning(request, "Rien à modifier.")
    else:
        for nom, valeur in champs.items():
            setattr(dossier, nom, valeur)
        dossier.save()
        journaliser(request, "modifier_dossier", f"dossier {dossier.pk} {sorted(champs)}")
        messages.success(request, f"Dossier {dossier} mis à jour.")
    return redirect("suivi:gestion_dossiers")
