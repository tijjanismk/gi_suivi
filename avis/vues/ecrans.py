"""Écrans des avis (ADR 0013, AV03) : la liste, la fiche (barème, pièces exigées, fichiers) et la
saisie d'un avis et de ses critères. Consultation : direction, consultation seule et
responsables des offres ; saisie : direction et responsables des offres (`GI-Offres`)."""

from __future__ import annotations

import mimetypes

from django.conf import settings
from django.contrib import admin, messages
from django.db.models import Count, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from administratif.models import TypePiece
from administratif.services import PartageIndisponibleError, chemin_absolu
from avis import services
from avis.formulaires import FormulaireAvis, FormulaireCritere
from avis.models import Avis, Critere
from identite.decorateurs import groupe_requis
from moteur.avis.filtres import FiltreInvalideError
from suivi.services import journaliser

SAISIE = (settings.GROUPE_DIRECTION, settings.GROUPE_OFFRES)
CONSULTATION = (*SAISIE, settings.GROUPE_DIRECTION_LECTURE)
FICHIERS = {"avis": ("Avis", "fichier_avis_chemin"), "tdr": ("TDR", "fichier_tdr_chemin")}
LARGES = {"objet", "observations", "lieu_depot", "fichier_avis_chemin", "fichier_tdr_chemin"}
ECHEANCES = (("a_venir", "à venir"), ("passes", "passés"))


def _peut_saisir(request) -> bool:
    return request.user.dans_groupe(*SAISIE)


@groupe_requis(*CONSULTATION)
def liste(request):
    journaliser(request, "consulter:avis")
    choisis = {k: request.GET.get(k, "").strip() for k in ("q", "type", "statut", "echeance")}
    aujourdhui = timezone.localdate()
    qs = Avis.objects.select_related("maitre_ouvrage", "bailleur")
    qs = qs.annotate(nb_criteres=Count("criteres"))
    if choisis["q"]:
        q = choisis["q"]
        qs = qs.filter(
            Q(reference__icontains=q)
            | Q(objet__icontains=q)
            | Q(maitre_ouvrage__nom__icontains=q)
            | Q(maitre_ouvrage__sigle__icontains=q)
            | Q(bailleur__nom__icontains=q)
            | Q(bailleur__sigle__icontains=q)
        )
    if choisis["type"] in Avis.Type.values:
        qs = qs.filter(type=choisis["type"])
    if choisis["statut"] in Avis.Statut.values:
        qs = qs.filter(statut=choisis["statut"])
    if choisis["echeance"] == "a_venir":
        qs = qs.filter(date_limite__gte=aujourdhui).order_by("date_limite", "pk")
    elif choisis["echeance"] == "passes":
        qs = qs.filter(date_limite__lt=aujourdhui)
    lignes = [(a, (a.date_limite - aujourdhui).days) for a in qs]
    return render(
        request,
        "avis/liste.html",
        {
            **admin.site.each_context(request),
            "titre": "Avis de marchés",
            "lignes": lignes,
            "total": len(lignes),
            "types": Avis.Type.choices,
            "statuts": Avis.Statut.choices,
            "echeances": ECHEANCES,
            **choisis,
            "filtre_actif": any(choisis.values()),
            "peut_saisir": _peut_saisir(request),
        },
    )


def _fichier(a: Avis, quoi: str) -> dict:
    libelle, champ = FICHIERS[quoi]
    chemin = getattr(a, champ)
    existe = None  # inconnu : partage non configuré ou injoignable
    if chemin:
        try:
            existe = chemin_absolu(chemin).is_file()
        except (PartageIndisponibleError, ValueError, OSError):
            existe = None
    return {"quoi": quoi, "libelle": libelle, "chemin": chemin, "existe": existe}


@groupe_requis(*CONSULTATION)
def fiche(request, avis_id: int):
    a = get_object_or_404(
        Avis.objects.select_related("maitre_ouvrage", "bailleur", "cree_par"), pk=avis_id
    )
    journaliser(request, "consulter:avis", str(a.pk))
    criteres = list(a.criteres.all())
    calcules = [c for c in criteres if c.mode != Critere.Mode.MANUEL]
    references = services.references_du_bureau() if calcules else []
    lignes = []
    for c in criteres:
        apercu, erreur = None, ""
        if c in calcules:
            try:
                apercu = services.apercu(c.filtre, references)
            except FiltreInvalideError as e:
                erreur = str(e)
        lignes.append(
            {
                "c": c,
                "filtre": services.filtre_en_clair(c.filtre),
                "apercu": apercu,
                "erreur": erreur,
            }
        )
    exigees = {p.type_id: p for p in a.pieces_exigees.all()}
    types = TypePiece.objects.filter(Q(actif=True) | Q(pk__in=list(exigees)))
    return render(
        request,
        "avis/fiche.html",
        {
            **admin.site.each_context(request),
            "titre": f"{a.type} {a.reference}",
            "a": a,
            "jours": (a.date_limite - timezone.localdate()).days,
            "criteres": lignes,
            "pieces": [(t, exigees.get(t.pk)) for t in types],
            "fichiers": [_fichier(a, quoi) for quoi in FICHIERS],
            "peut_saisir": _peut_saisir(request),
        },
    )


@groupe_requis(*CONSULTATION)
def fichier(request, avis_id: int, quoi: str):
    """Ouvre le fichier de l'avis ou des TDR, lu sur le partage (jamais écrit, règle 4)."""
    a = get_object_or_404(Avis, pk=avis_id)
    if quoi not in FICHIERS or not getattr(a, FICHIERS[quoi][1]):
        raise Http404("pas de fichier")
    try:
        chemin = chemin_absolu(getattr(a, FICHIERS[quoi][1]))
    except (PartageIndisponibleError, ValueError) as x:
        raise Http404(str(x)) from x
    if not chemin.is_file():
        raise Http404(f"{chemin.name} introuvable sur le partage")
    journaliser(request, "consulter:fichier_avis", f"{a.pk} {chemin.name}")
    type_mime = mimetypes.guess_type(chemin.name)[0] or "application/octet-stream"
    return FileResponse(chemin.open("rb"), content_type=type_mime, filename=chemin.name)


@groupe_requis(*SAISIE)
def modifier(request, avis_id: int | None = None):
    a = get_object_or_404(Avis, pk=avis_id) if avis_id else None
    formulaire = FormulaireAvis(request.POST or None, instance=a)
    if request.method == "POST" and formulaire.is_valid():
        nouveau = a is None
        a = formulaire.save(commit=False)
        if nouveau:
            a.cree_par = request.user
        a.save()
        journaliser(request, "avis:creer" if nouveau else "avis:modifier", str(a.pk))
        suite = " Pièces exigées par défaut reprises ; saisissez le barème." if nouveau else ""
        messages.success(request, f"{a} enregistré.{suite}")
        return redirect("avis:fiche", avis_id=a.pk)
    return render(
        request,
        "avis/formulaire.html",
        {
            **admin.site.each_context(request),
            "titre": "Nouvel avis" if a is None else f"Modifier {a}",
            "a": a,
            "formulaire": formulaire,
            "larges": LARGES,
        },
    )


@groupe_requis(*SAISIE)
def critere(request, avis_id: int, critere_id: int | None = None):
    """Saisie d'un critère. « Aperçu » montre les références retenues sans rien enregistrer."""
    a = get_object_or_404(Avis, pk=avis_id)
    if critere_id:
        c = get_object_or_404(Critere, pk=critere_id, avis=a)
    else:
        c = Critere(avis=a, ordre=a.criteres.count() + 1)
    formulaire = FormulaireCritere(request.POST or None, instance=c)
    apercu = None
    if request.method == "POST" and formulaire.is_valid():
        if request.POST.get("action") == "apercu":
            apercu = services.apercu(formulaire.instance.filtre)
        else:
            c = formulaire.save()
            journaliser(request, "avis:critere", f"{a.pk} {c.code}")
            messages.success(request, f"Critère {c.code} enregistré.")
            return redirect("avis:fiche", avis_id=a.pk)
    return render(
        request,
        "avis/critere.html",
        {
            **admin.site.each_context(request),
            "titre": f"Critère {c.code}" if c.pk else "Nouveau critère",
            "a": a,
            "c": c,
            "formulaire": formulaire,
            "apercu": apercu,
        },
    )


@require_POST
@groupe_requis(*SAISIE)
def retirer_critere(request, avis_id: int, critere_id: int):
    c = get_object_or_404(Critere, pk=critere_id, avis_id=avis_id)
    journaliser(request, "avis:retirer_critere", f"{avis_id} {c.code}")
    c.delete()
    messages.success(request, f"Critère {c.code} retiré du barème.")
    return redirect("avis:fiche", avis_id=avis_id)


@require_POST
@groupe_requis(*SAISIE)
def pieces(request, avis_id: int):
    a = get_object_or_404(Avis, pk=avis_id)
    ajoutees, retirees = services.regler_pieces(a, request.POST.getlist("pieces"))
    journaliser(request, "avis:pieces", f"{a.pk} +{ajoutees} -{retirees}")
    bilan = f"{ajoutees} ajoutée(s), {retirees} retirée(s)"
    messages.success(request, f"Pièces exigées enregistrées ({bilan}).")
    return redirect("avis:fiche", avis_id=a.pk)
