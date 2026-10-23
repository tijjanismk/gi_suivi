"""Écrans des références (ADR 0008) : la liste, la fiche d'une référence et l'arbitrage des
doublons. Consultation : direction et consultation seule ; décisions : direction seulement."""

from __future__ import annotations

from django.conf import settings
from django.contrib import admin, messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from identite.decorateurs import consultation_requise, groupe_requis
from moteur.references.doublons import code_le_plus_ancien
from references import justificatifs as js
from references import services
from references.models import DecisionDoublon, Mission
from referentiel.models import Domaine, TypeOuvrage
from suivi.services import journaliser

PAR_PAGE = 100
PAIRES_AFFICHEES = 30


@consultation_requise
def liste(request):
    journaliser(request, "consulter:references")
    qs = Mission.objects.select_related("domaine", "client", "absorbee_par").prefetch_related(
        "domaines_secondaires"
    )
    texte = request.GET.get("q", "").strip()
    if texte:
        qs = qs.filter(
            Q(code__icontains=texte)
            | Q(intitule__icontains=texte)
            | Q(intitule_court__icontains=texte)
            | Q(client__nom__icontains=texte)
            | Q(client__sigle__icontains=texte)
        )
    domaine = request.GET.get("domaine", "")
    if domaine:
        qs = qs.filter(Q(domaine__code=domaine) | Q(domaines_secondaires__code=domaine)).distinct()
    nature = request.GET.get("nature", "")
    if nature in services.NATURES:
        qs = qs.filter(nature=nature)
    verification = request.GET.get("verification", "")
    if verification in Mission.Verification.values:
        qs = qs.filter(statut_verification=verification)
    qs = js.avec_nb_bonnes(qs)
    pieces = request.GET.get("pieces", "")
    if pieces == "completes":
        qs = qs.filter(nb_bonnes=3)
    elif pieces == "incompletes":
        qs = qs.filter(nb_bonnes__lt=3)
    ouvrage = request.GET.get("ouvrage", "")
    if ouvrage:
        qs = qs.filter(types_ouvrage__cle=ouvrage)
    avec_absorbees = request.GET.get("absorbees") == "1"
    if not avec_absorbees:
        qs = qs.filter(absorbee_par=None)
    page = Paginator(qs.order_by("code"), PAR_PAGE).get_page(request.GET.get("page"))
    filtres = request.GET.copy()
    filtres.pop("page", None)
    return render(
        request,
        "references/liste.html",
        {
            **admin.site.each_context(request),
            "titre": "Références du bureau",
            "page": page,
            "total": page.paginator.count,
            "domaines": Domaine.objects.all(),
            "natures": Mission.Nature.choices,
            "verifications": Mission.Verification.choices,
            "q": texte,
            "domaine": domaine,
            "nature": nature,
            "verification": verification,
            "pieces": pieces,
            "ouvrage": ouvrage,
            "types_ouvrage": TypeOuvrage.objects.filter(actif=True),
            "avec_absorbees": avec_absorbees,
            "requete": filtres.urlencode(),
            "nb_absorbees": Mission.objects.exclude(absorbee_par=None).count(),
            "peut_agir": request.user.direction,
        },
    )


@consultation_requise
def fiche(request, code: str):
    m = get_object_or_404(
        Mission.objects.select_related(
            "domaine", "client", "bailleur", "categorie", "absorbee_par"
        ),
        code=code,
    )
    journaliser(request, "consulter:reference", code)
    decisions = DecisionDoublon.objects.filter(Q(mission_a=m) | Q(mission_b=m)).select_related(
        "mission_a", "mission_b", "gardee", "par"
    )
    return render(
        request,
        "references/fiche.html",
        {
            **admin.site.each_context(request),
            "titre": m.code,
            "m": m,
            "secondaires": m.domaines_secondaires.all(),
            "absorbees": m.absorbees.order_by("code"),
            "decisions": decisions,
            "etat": js.etat_justificatifs(m),
            "ouvrages": m.types_ouvrage.all(),
            "livrables": m.livrables.all(),
            "quantites": m.quantites.select_related("type"),
            "affectations": m.affectations.select_related("expert"),
            "experts": _experts_mobilisables(),
            "peut_agir": request.user.direction,
        },
    )


def _experts_mobilisables():
    from experts.models import Expert  # experts dépend de references : import à l'appel

    return (
        Expert.objects.filter(disponible=True).exclude(statut="ancien").order_by("nom", "prenoms")
    )


@consultation_requise
def doublons(request):
    journaliser(request, "consulter:doublons_references")
    paires = services.paires_a_arbitrer()
    affichees = [
        {
            "p": p,
            "proposee": code_le_plus_ancien(p.a.code, p.b.code),
            "raisons": " ; ".join(p.raisons),
        }
        for p in paires[:PAIRES_AFFICHEES]
    ]
    missions = Mission.objects.select_related("client", "domaine").in_bulk(
        [x["p"].a.ident for x in affichees] + [x["p"].b.ident for x in affichees]
    )
    for x in affichees:
        x["a"], x["b"] = missions[x["p"].a.ident], missions[x["p"].b.ident]
    return render(
        request,
        "references/doublons.html",
        {
            **admin.site.each_context(request),
            "titre": "Doublons à arbitrer",
            "paires": affichees,
            "total": len(paires),
            "tranchees": DecisionDoublon.objects.count(),
            "peut_agir": request.user.direction,
        },
    )


@require_POST
@groupe_requis(settings.GROUPE_DIRECTION)
def trancher(request):
    a = get_object_or_404(Mission, pk=request.POST.get("a"))
    b = get_object_or_404(Mission, pk=request.POST.get("b"))
    choix = request.POST.get("choix", "")
    gardee = {"garder_a": a, "garder_b": b}.get(choix)
    if choix not in ("garder_a", "garder_b", "differents"):
        messages.error(request, "Décision inconnue.")
        return redirect("references:doublons")
    try:
        services.trancher(
            a,
            b,
            meme_contrat=gardee is not None,
            gardee=gardee,
            utilisateur=request.user,
            raisons=request.POST.get("raisons", ""),
            note=request.POST.get("note", ""),
        )
    except ValueError as e:
        messages.error(request, str(e))
        return redirect("references:doublons")
    if gardee:
        absorbee = b if gardee == a else a
        journaliser(request, "reference:doublon", f"{absorbee.code} absorbée par {gardee.code}")
        messages.success(request, f"{absorbee.code} est absorbée par {gardee.code}.")
    else:
        journaliser(request, "reference:differents", f"{a.code} / {b.code}")
        messages.success(
            request, f"{a.code} et {b.code} : contrats différents, la paire ne reviendra plus."
        )
    return redirect("references:doublons")
