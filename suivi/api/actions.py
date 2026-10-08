"""A06 — actions de la direction (GI-Direction seulement, pas la consultation seule).

POST /api/dossiers/<id>/valider   {nom?, client?, responsable_id?}
PUT  /api/dossiers/<id>           {nom?, client?, responsable_id?, statut? (actif|clos)}
POST /api/aclasser/<id>/rattacher {dossier_id, type? (chemin|prefixe|mot_cle), motif?}
    <id> = un segment « à classer » du groupe ; une exception est créée, puis le recalcul
    rattache tous les segments concernés, passés et futurs.

Protégées par le jeton CSRF (l'identité Windows est envoyée d'office par le navigateur : sans
jeton, une page tierce pourrait agir au nom de la direction). Chaque action est journalisée.
"""

from __future__ import annotations

import json

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods, require_POST

from identite.decorateurs import groupe_requis
from suivi.models import Dossier, Employe, RegleException, Segment
from suivi.services import journaliser, recalculer, valider_dossier

CHAMPS_DOSSIER = {"nom", "client", "responsable_id"}
STATUTS_MODIFIABLES = {Dossier.Statut.ACTIF, Dossier.Statut.CLOS}


def _corps(request) -> tuple[dict | None, JsonResponse | None]:
    if not request.body:
        return {}, None
    try:
        data = json.loads(request.body)
    except ValueError:
        return None, JsonResponse({"erreur": "JSON invalide"}, status=400)
    if not isinstance(data, dict):
        return None, JsonResponse({"erreur": "objet JSON attendu"}, status=400)
    return data, None


def _champs_dossier(data: dict) -> tuple[dict, str | None]:
    champs = {}
    for cle in CHAMPS_DOSSIER & set(data):
        valeur = data[cle]
        if cle == "responsable_id":
            if valeur is None:
                champs["responsable"] = None
            elif not Employe.objects.filter(pk=valeur).exists():
                return {}, f"responsable_id {valeur} inconnu"
            else:
                champs["responsable"] = Employe.objects.get(pk=valeur)
        else:
            if not isinstance(valeur, str):
                return {}, f"{cle} doit être une chaîne"
            champs[cle] = valeur.strip()
    if "nom" in champs and not champs["nom"]:
        return {}, "nom vide"
    return champs, None


def _dossier_dict(d: Dossier) -> dict:
    return {
        "id": d.pk,
        "code": d.code,
        "nom": d.nom,
        "client": d.client,
        "statut": d.statut,
        "valide": d.valide,
        "valide_par": d.valide_par.login_windows if d.valide_par else None,
        "valide_le": d.valide_le.isoformat() if d.valide_le else None,
        "responsable_id": d.responsable_id,
    }


def _direction(vue):
    return groupe_requis(settings.GROUPE_DIRECTION)(vue)


@require_POST
@_direction
def valider(request, dossier_id: int):
    data, erreur = _corps(request)
    if erreur:
        return erreur
    dossier = get_object_or_404(Dossier, pk=dossier_id)
    champs, probleme = _champs_dossier(data)
    if probleme:
        return JsonResponse({"erreur": probleme}, status=400)
    if dossier.valide:
        return JsonResponse({"erreur": "dossier déjà validé"}, status=409)
    with transaction.atomic():
        valider_dossier(dossier, request.user, **champs)
        journaliser(request, "valider_dossier", f"dossier {dossier.pk} {dossier}")
    return JsonResponse(_dossier_dict(dossier))


@require_http_methods(["PUT"])
@_direction
def modifier(request, dossier_id: int):
    data, erreur = _corps(request)
    if erreur:
        return erreur
    dossier = get_object_or_404(Dossier, pk=dossier_id)
    champs, probleme = _champs_dossier(data)
    if probleme:
        return JsonResponse({"erreur": probleme}, status=400)
    if "statut" in data:
        if data["statut"] not in STATUTS_MODIFIABLES:
            return JsonResponse({"erreur": "statut : actif ou clos"}, status=400)
        champs["statut"] = data["statut"]
    if not champs:
        return JsonResponse({"erreur": "rien à modifier"}, status=400)
    with transaction.atomic():
        for nom, valeur in champs.items():
            setattr(dossier, nom, valeur)
        dossier.save()
        journaliser(request, "modifier_dossier", f"dossier {dossier.pk} {sorted(champs)}")
    return JsonResponse(_dossier_dict(dossier))


@require_POST
@_direction
def rattacher(request, segment_id: int):
    data, erreur = _corps(request)
    if erreur:
        return erreur
    segment = get_object_or_404(Segment.objects.select_related("employe"), pk=segment_id)
    if segment.statut_classement != Segment.StatutClassement.A_CLASSER:
        return JsonResponse({"erreur": "ce segment n'est pas à classer"}, status=400)
    dossier = get_object_or_404(Dossier, pk=data.get("dossier_id"))

    type_regle = data.get("type") or ("chemin" if segment.chemin else "mot_cle")
    if type_regle not in RegleException.Type.values:
        return JsonResponse({"erreur": "type : chemin, prefixe ou mot_cle"}, status=400)
    motif = (data.get("motif") or "").strip()
    if not motif:
        if type_regle == "chemin":
            motif = segment.chemin
        elif type_regle == "prefixe":
            motif = segment.chemin.rsplit("\\", 1)[0] if "\\" in segment.chemin else segment.chemin
        else:
            motif = (segment.fichier or segment.chemin).rsplit(".", 1)[0]
    if not motif:
        return JsonResponse({"erreur": "motif introuvable : précisez-le"}, status=400)

    with transaction.atomic():
        regle, creee = RegleException.objects.get_or_create(
            motif=motif, type=type_regle, defaults={"dossier": dossier, "cree_par": request.user}
        )
        if not creee and regle.dossier_id != dossier.pk:
            regle.dossier = dossier
            regle.save(update_fields=["dossier"])
        resultat = recalculer()
        journaliser(
            request,
            "rattacher",
            f"segment {segment.pk} → dossier {dossier.pk} par {type_regle} « {motif} »",
        )
    return JsonResponse(
        {
            "exception_id": regle.pk,
            "type": type_regle,
            "motif": motif,
            "dossier": _dossier_dict(dossier),
            "segments_reclasses": resultat["modifies"],
        }
    )
