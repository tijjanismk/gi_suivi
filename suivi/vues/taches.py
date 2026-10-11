"""F01 — tâches confiées sur un dossier. La direction crée et suit ; la consultation seule voit
sans agir ; chaque personne voit les siennes dans « Mon activité du jour » et peut les passer
« en cours » ou « faite ». Formulaires classiques (POST + redirection), journal d'accès."""

from __future__ import annotations

from datetime import date

from django.conf import settings
from django.contrib import admin, messages
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from identite.decorateurs import consultation_requise, groupe_requis
from suivi.models import Dossier, Employe, Tache
from suivi.services import employe_de, journaliser
from suivi.taches import preparer

FILTRES_ETAT = {
    "ouvertes": ("Ouvertes", list(Tache.OUVERTES)),
    "faites": ("Faites", [Tache.Etat.FAITE]),
    "toutes": ("Toutes", None),
}


@consultation_requise
def taches(request):
    journaliser(request, "consulter:taches")
    filtre = request.GET.get("etat", "ouvertes")
    if filtre not in FILTRES_ETAT:
        filtre = "ouvertes"
    qs = Tache.objects.select_related("dossier", "personne").exclude(etat=Tache.Etat.ANNULEE)
    etats = FILTRES_ETAT[filtre][1]
    if etats:
        qs = qs.filter(etat__in=etats)
    personne_id = request.GET.get("personne") or ""
    if personne_id.isdigit():
        qs = qs.filter(personne_id=int(personne_id))
    liste = preparer(qs.order_by("etat", "echeance", "creee_le"))
    return render(
        request,
        "suivi/taches.html",
        {
            **admin.site.each_context(request),
            "titre": "Tâches",
            "taches": liste,
            "en_retard": sum(1 for t in liste if t.retard),
            "filtre": filtre,
            "filtres": [(cle, libelle) for cle, (libelle, _) in FILTRES_ETAT.items()],
            "personne_id": personne_id,
            "employes": Employe.objects.filter(actif=True).order_by("nom_affiche", "login"),
            "dossiers": Dossier.objects.exclude(statut=Dossier.Statut.CLOS).order_by("code", "nom"),
            "etats": Tache.Etat.choices,
            "peut_agir": request.user.direction,
        },
    )


def _date(valeur: str) -> tuple[date | None, str | None]:
    valeur = (valeur or "").strip()
    if not valeur:
        return None, None
    try:
        return date.fromisoformat(valeur), None
    except ValueError:
        return None, "Échéance illisible (format attendu : AAAA-MM-JJ)."


@require_POST
@groupe_requis(settings.GROUPE_DIRECTION)
def creer(request):
    titre = request.POST.get("titre", "").strip()
    dossier = Dossier.objects.filter(pk=request.POST.get("dossier") or 0).first()
    personne = Employe.objects.filter(pk=request.POST.get("personne") or 0, actif=True).first()
    echeance, erreur = _date(request.POST.get("echeance"))
    if not titre:
        erreur = "Le titre ne peut pas être vide."
    elif dossier is None:
        erreur = "Choisissez un dossier."
    elif personne is None:
        erreur = "Choisissez la personne à qui confier la tâche."
    if erreur:
        messages.error(request, erreur)
        return redirect("suivi:taches")
    t = Tache.objects.create(
        titre=titre[:200],
        description=request.POST.get("description", "").strip(),
        dossier=dossier,
        personne=personne,
        fichiers=request.POST.get("fichiers", "").strip(),
        echeance=echeance,
        creee_par=request.user,
    )
    journaliser(request, "creer_tache", f"tâche {t.pk} → {personne} ({dossier})")
    messages.success(request, f"Tâche « {t.titre} » confiée à {personne}.")
    return redirect("suivi:taches")


def _changer_etat(t: Tache, etat: str) -> None:
    t.etat = etat
    t.faite_le = timezone.now() if etat == Tache.Etat.FAITE else None
    t.save(update_fields=["etat", "faite_le", "modifiee_le"])


@require_POST
@groupe_requis(settings.GROUPE_DIRECTION)
def modifier(request, tache_id: int):
    t = get_object_or_404(Tache, pk=tache_id)
    etat = request.POST.get("etat", "")
    if etat not in Tache.Etat.values:
        messages.error(request, "État inconnu.")
        return redirect("suivi:taches")
    champs = []
    if "echeance" in request.POST:
        echeance, erreur = _date(request.POST.get("echeance"))
        if erreur:
            messages.error(request, erreur)
            return redirect("suivi:taches")
        t.echeance = echeance
        champs.append("echeance")
    if etat != t.etat:
        _changer_etat(t, etat)
    if champs:
        t.save(update_fields=[*champs, "modifiee_le"])
    journaliser(request, "modifier_tache", f"tâche {t.pk} état={t.etat}")
    messages.success(request, f"Tâche « {t.titre} » : {t.get_etat_display()}.")
    return redirect("suivi:taches")


@require_POST
def ma_tache(request, tache_id: int):
    """La personne à qui la tâche est confiée la passe « en cours » ou « faite »."""
    t = get_object_or_404(Tache, pk=tache_id)
    moi = employe_de(request.user)
    if moi is None or t.personne_id != moi.pk:
        return HttpResponseForbidden("Cette tâche ne vous est pas confiée.")
    etat = request.POST.get("etat", "")
    if etat not in (Tache.Etat.EN_COURS, Tache.Etat.FAITE) or t.etat == Tache.Etat.ANNULEE:
        return HttpResponseForbidden("Changement non autorisé.")
    _changer_etat(t, etat)
    journaliser(request, "ma_tache", f"tâche {t.pk} état={etat}")
    return redirect("moi")
