"""Écrans 1 et 2 des maquettes du 21/10 (AD03) : registre des pièces et fiche d'une pièce, plus
les actions de la fiche (noter une demande, retirer une version) et la lecture du fichier.

Consultation : direction et compte de consultation seule. Actions : direction seulement.
"""

from __future__ import annotations

import mimetypes
from datetime import date

from django.conf import settings
from django.contrib import admin, messages
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from administratif import services
from administratif.models import DemandeRenouvellement, PieceAdministrative, TypePiece
from identite.decorateurs import consultation_requise, groupe_requis
from moteur.administratif.echeances import GRAVITE
from suivi.services import journaliser

FILTRES = (("toutes", "Toutes"), ("a_traiter", "À traiter"), ("valides", "Valides"))


def pastille(request) -> int | None:
    """Pastille du menu : pièces à traiter (direction et consultation)."""
    u = getattr(request, "user", None)
    if not (getattr(u, "direction", False) or getattr(u, "lecture_seule", False)):
        return None
    return services.a_traiter() or None


def lire_date(valeur: str | None) -> date | None:
    try:
        return date.fromisoformat(valeur) if valeur else None
    except ValueError:
        return None


@consultation_requise
def registre(request):
    journaliser(request, "consulter:pieces")
    lignes = services.registre()
    filtre = request.GET.get("vue", "toutes")
    if filtre not in dict(FILTRES):
        filtre = "toutes"
    nombres = services.compteurs(lignes)
    nb = {"toutes": len(lignes), "a_traiter": nombres["a_traiter"], "valides": nombres["valides"]}
    if filtre == "a_traiter":
        lignes = [x for x in lignes if x.alerte]
    elif filtre == "valides":
        lignes = [x for x in lignes if x.cle_etat in ("valide", "permanente")]
    # alertes d'abord, puis valides et permanentes, les pièces non requises à la fin
    lignes.sort(
        key=lambda x: (
            not x.alerte,
            x.cle_etat == "non_requise",
            GRAVITE[x.etat.etat],
            x.type.ordre,
        )
    )
    return render(
        request,
        "administratif/registre.html",
        {
            **admin.site.each_context(request),
            "titre": "Pièces administratives",
            "lignes": lignes,
            "nombres": nombres,
            "filtre": filtre,
            "filtres": [(cle, libelle, nb[cle]) for cle, libelle in FILTRES],
            "aujourd_hui": timezone.localdate(),
            "peut_agir": request.user.direction,
            "partage": settings.PARTAGE_GIC,
        },
    )


@consultation_requise
def fiche(request, code: str):
    type_piece = get_object_or_404(TypePiece, code=code)
    journaliser(request, "consulter:piece", code)
    alerte_partage = ""
    try:
        if services.retrouver_deplaces(type_piece):
            messages.info(request, "Un fichier déplacé dans le dossier a été retrouvé.")
    except (services.PartageIndisponibleError, OSError) as e:
        alerte_partage = str(e)
    ligne = services.registre(types=[type_piece])[0]
    return render(
        request,
        "administratif/fiche.html",
        {
            **admin.site.each_context(request),
            "titre": type_piece.libelle,
            "t": type_piece,
            "ligne": ligne,
            "demandes": DemandeRenouvellement.objects.filter(type=type_piece)[:10],
            "aujourd_hui": timezone.localdate(),
            "peut_agir": request.user.direction,
            "alerte_partage": alerte_partage,
        },
    )


@consultation_requise
def fichier(request, version_id: int):
    """Le PDF d'une version, lu sur le partage et rendu au navigateur (lecture seule)."""
    version = get_object_or_404(PieceAdministrative, pk=version_id)
    try:
        chemin = services.chemin_absolu(version.chemin)
    except (services.PartageIndisponibleError, ValueError) as e:
        raise Http404(str(e)) from e
    if not chemin.is_file():
        raise Http404("fichier introuvable sur le partage")
    journaliser(request, "consulter:fichier_piece", version.chemin)
    type_mime = mimetypes.guess_type(chemin.name)[0] or "application/octet-stream"
    return FileResponse(chemin.open("rb"), content_type=type_mime, filename=chemin.name)


@require_POST
@groupe_requis(settings.GROUPE_DIRECTION)
def noter_demande(request, code: str):
    type_piece = get_object_or_404(TypePiece, code=code)
    demandee_le = lire_date(request.POST.get("demandee_le")) or timezone.localdate()
    try:
        d = services.noter_demande(
            type_piece,
            demandee_le,
            request.POST.get("aupres_de", ""),
            lire_date(request.POST.get("relance_prevue_le")),
            request.POST.get("note", ""),
            request.user,
        )
    except ValueError as e:
        messages.error(request, str(e))
    else:
        journaliser(request, "piece:demande", f"{code} demandée le {d.demandee_le}")
        messages.success(request, f"Demande du {d.demandee_le:%d/%m/%Y} notée.")
    return redirect("administratif:fiche", code=code)


@require_POST
@groupe_requis(settings.GROUPE_DIRECTION)
def retirer(request, version_id: int):
    version = get_object_or_404(PieceAdministrative, pk=version_id)
    try:
        services.retirer_version(version, request.POST.get("motif", ""))
    except ValueError as e:
        messages.error(request, str(e))
    else:
        journaliser(request, "piece:retirer", f"{version.pk} {version.chemin}")
        messages.success(request, f"Version du {version.date_emission:%d/%m/%Y} retirée.")
    return redirect("administratif:fiche", code=version.type.code)
