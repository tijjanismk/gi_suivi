"""Justificatifs d'une référence (chantier 3) et ses ouvrages, livrables et quantités
(chantier 4), ADR 0011. Consultation : direction et consultation seule ; actions : direction."""

from __future__ import annotations

import mimetypes

from django.conf import settings
from django.contrib import admin, messages
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from administratif.services import PartageIndisponibleError, chemin_absolu
from administratif.vues.registre import lire_date
from identite.decorateurs import consultation_requise, groupe_requis
from references import justificatifs as js
from references.models import Mission, PieceJustificative, Reclamation
from referentiel.models import Livrable, TypeOuvrage, TypeQuantite
from suivi.services import journaliser


@consultation_requise
def justificatifs(request, code: str):
    m = get_object_or_404(Mission, code=code)
    journaliser(request, "consulter:justificatifs", code)
    erreur, fichiers = "", []
    try:
        fichiers = js.fichiers(m)
    except (PartageIndisponibleError, OSError) as e:
        erreur = str(e)
    return render(
        request,
        "references/justificatifs.html",
        {
            **admin.site.each_context(request),
            "titre": f"Justificatifs de {m.code}",
            "m": m,
            "etat": js.etat_justificatifs(m),
            "fichiers": fichiers,
            "erreur_partage": erreur,
            "dossier": js.dossier_de(m),
            "types": PieceJustificative.Type.choices,
            "natures": PieceJustificative.Nature.choices,
            "lisibles": PieceJustificative.Lisible.choices,
            "coherentes": PieceJustificative.Coherente.choices,
            "etats_reclamation": Reclamation.Etat.choices,
            "peut_agir": request.user.direction,
        },
    )


def _retour(code: str):
    return redirect("references:justificatifs", code=code)


@require_POST
@groupe_requis(settings.GROUPE_DIRECTION)
def rattacher(request, code: str):
    m = get_object_or_404(Mission, code=code)
    try:
        memes = [x for x in js.fichiers(m) if x.empreinte == request.POST.get("empreinte")]
        f = next((x for x in memes if x.statut == "nouveau"), memes[0] if memes else None)
        if f is None:
            raise ValueError("fichier introuvable dans le dossier : rechargez la page")
        piece = js.rattacher(m, f, request.POST.get("type", ""), request.user)
    except (ValueError, PartageIndisponibleError) as e:
        messages.error(request, str(e))
        return _retour(code)
    journaliser(request, "reference:rattacher", f"{code} {piece.type} {piece.chemin}")
    messages.success(request, f"« {piece.nom_fichier} » rattaché comme {piece.get_type_display()}.")
    return _retour(code)


@require_POST
@groupe_requis(settings.GROUPE_DIRECTION)
def auditer(request, piece_id: int):
    piece = get_object_or_404(PieceJustificative, pk=piece_id)
    donnees = {**request.POST.dict(), "date_document": lire_date(request.POST.get("date_document"))}
    try:
        js.auditer(piece, donnees, request.user)
    except ValueError as e:
        messages.error(request, str(e))
    else:
        journaliser(request, "reference:auditer", f"{piece.mission.code} {piece.type}")
        messages.success(request, f"Audit de la {piece.get_type_display()} enregistré.")
    return _retour(piece.mission.code)


@require_POST
@groupe_requis(settings.GROUPE_DIRECTION)
def detacher(request, piece_id: int):
    piece = get_object_or_404(PieceJustificative, pk=piece_id)
    code, nom = piece.mission.code, piece.nom_fichier
    piece.delete()  # le lien seulement : le fichier reste sur le partage
    journaliser(request, "reference:detacher", f"{code} {nom}")
    messages.success(request, f"« {nom} » détaché ; le fichier reste dans le dossier.")
    return _retour(code)


@require_POST
@groupe_requis(settings.GROUPE_DIRECTION)
def reclamer(request, code: str):
    m = get_object_or_404(Mission, code=code)
    try:
        r = js.reclamer(
            m,
            request.POST.get("type", ""),
            request.POST.get("etat", ""),
            lire_date(request.POST.get("le")),
            request.POST.get("contact_client", ""),
            request.POST.get("note", ""),
            request.user,
        )
    except ValueError as e:
        messages.error(request, str(e))
    else:
        journaliser(request, "reference:reclamer", f"{code} {r.type} {r.etat}")
        messages.success(
            request, f"Réclamation notée : {r.get_type_display()}, {r.get_etat_display()}."
        )
    return _retour(code)


@consultation_requise
def fichier(request, piece_id: int):
    piece = get_object_or_404(PieceJustificative, pk=piece_id)
    try:
        chemin = chemin_absolu(piece.chemin)
    except (PartageIndisponibleError, ValueError) as e:
        raise Http404(str(e)) from e
    if not chemin.is_file():
        raise Http404("fichier introuvable sur le partage")
    journaliser(request, "consulter:fichier_justificatif", piece.chemin)
    type_mime = mimetypes.guess_type(chemin.name)[0] or "application/octet-stream"
    return FileResponse(chemin.open("rb"), content_type=type_mime, filename=chemin.name)


@groupe_requis(settings.GROUPE_DIRECTION)
def ouvrages(request, code: str):
    m = get_object_or_404(Mission, code=code)
    types_q = list(TypeQuantite.objects.all())
    if request.method == "POST":
        quantites = {
            t.pk: (request.POST.get(f"q-{t.pk}", ""), request.POST.get(f"s-{t.pk}", ""))
            for t in types_q
        }
        try:
            js.enregistrer_ouvrages(
                m,
                [int(x) for x in request.POST.getlist("types_ouvrage") if x.isdigit()],
                [int(x) for x in request.POST.getlist("livrables") if x.isdigit()],
                quantites,
            )
        except ValueError as e:
            messages.error(request, str(e))
        else:
            journaliser(request, "reference:ouvrages", code)
            messages.success(request, f"Ouvrages, livrables et quantités de {code} enregistrés.")
            return redirect("references:fiche", code=code)
    existantes = {q.type_id: q for q in m.quantites.all()}
    return render(
        request,
        "references/ouvrages.html",
        {
            **admin.site.each_context(request),
            "titre": f"Ouvrages et quantités de {m.code}",
            "m": m,
            "types_ouvrage": TypeOuvrage.objects.filter(actif=True),
            "choisis": set(m.types_ouvrage.values_list("pk", flat=True)),
            "livrables": Livrable.objects.all(),
            "livrables_choisis": set(m.livrables.values_list("pk", flat=True)),
            "quantites": [(t, existantes.get(t.pk)) for t in types_q],
        },
    )
