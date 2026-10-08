"""Passage entre l'ORM et le moteur : le moteur ne voit que des dataclasses (CONTEXT.md, r. 1)."""

from __future__ import annotations

from collections.abc import Iterable

from django.db import transaction
from django.utils import timezone

from moteur.suivi import types as m
from moteur.suivi.classement import classer_observation, normaliser_chemin
from suivi.models import DemandeRecalcul, Dossier, Parametre, Racine, RegleException, Segment

CORRESPONDANCE_LECTEURS = "correspondance_lecteurs"


def racines_moteur() -> list[m.Racine]:
    return [
        m.Racine(r.chemin, r.profondeur, r.motif_code) for r in Racine.objects.filter(active=True)
    ]


def exceptions_moteur() -> list[m.RegleException]:
    return [
        m.RegleException(e.motif, e.type, e.dossier.chemin_windows, e.dossier.code or None)
        for e in RegleException.objects.select_related("dossier")
    ]


def parametre(cle: str, defaut=None):
    p = Parametre.objects.filter(cle=cle).first()
    return p.valeur if p is not None else defaut


def correspondance_lecteurs() -> dict[str, str]:
    return {k.upper(): v for k, v in (parametre(CORRESPONDANCE_LECTEURS, {}) or {}).items()}


def classer(observations: Iterable[m.Observation]) -> list[tuple[str, Dossier | None]]:
    """Classe des observations et rend, pour chacune, (statut, dossier).

    Un chemin conforme à la convention sous une racine, mais dont le dossier n'existe pas encore,
    crée ce dossier à l'état « détecté » (A02) : la direction le valide ensuite (nom, client,
    responsable). Les segments y sont rattachés dès maintenant, pour que le temps ne soit pas
    perdu en attendant. À appeler dans la transaction de l'appelant.
    """
    racines_db = {normaliser_chemin(r.chemin): r for r in Racine.objects.filter(active=True)}
    racines = [m.Racine(r.chemin, r.profondeur, r.motif_code) for r in racines_db.values()]
    lecteurs, exceptions = correspondance_lecteurs(), exceptions_moteur()
    classements = [classer_observation(o, racines, lecteurs, exceptions) for o in observations]

    chemins = {c.dossier_chemin for c in classements if c.statut == "dossier"}
    connus = {d.chemin_windows: d for d in Dossier.objects.filter(chemin_windows__in=chemins)}
    for c in classements:
        if c.statut == "dossier" and c.dossier_chemin not in connus:
            connus[c.dossier_chemin] = Dossier.objects.create(
                code=c.code or "",
                # nom normalisé (minuscules, sans accents) : la direction le corrige à la validation
                nom=c.dossier_nom or c.dossier_chemin.rsplit("\\", 1)[-1],
                chemin_windows=c.dossier_chemin,
                racine=racines_db.get(normaliser_chemin(c.racine)) if c.racine else None,
                statut=Dossier.Statut.DETECTE,
            )
    return [
        (c.statut, connus.get(c.dossier_chemin) if c.statut == "dossier" else None)
        for c in classements
    ]


# -- recalcul (A03) ------------------------------------------------------------------------


def demander_recalcul(motif: str) -> DemandeRecalcul:
    return DemandeRecalcul.objects.create(motif=motif[:300])


@transaction.atomic
def recalculer() -> dict[str, int]:
    """Reclasse les segments « à classer » et « rattachés » avec les racines, dossiers et
    exceptions d'aujourd'hui, puis marque les demandes en attente comme traitées.

    Seuls `statut_classement` et `dossier` bougent : debut, fin, fichier, chemin restent ce que
    l'agent a envoyé. Brouillons, segments d'application et ignorés ne changent jamais.
    """
    segments = list(
        Segment.objects.filter(
            statut_classement__in=[
                Segment.StatutClassement.A_CLASSER,
                Segment.StatutClassement.DOSSIER,
            ]
        ).order_by("pk")
    )
    resultats = classer(
        m.Observation(s.debut, s.application, s.fichier or None, s.chemin or None, 0.0)
        for s in segments
    )
    modifies: list[Segment] = []
    for s, (statut, dossier) in zip(segments, resultats, strict=True):
        if s.statut_classement != statut or s.dossier_id != (dossier.pk if dossier else None):
            s.statut_classement, s.dossier = statut, dossier
            modifies.append(s)
    Segment.objects.bulk_update(modifies, ["statut_classement", "dossier"], batch_size=500)
    demandes = DemandeRecalcul.objects.filter(traitee_le=None).update(traitee_le=timezone.now())
    return {"examines": len(segments), "modifies": len(modifies), "demandes": demandes}


def valider_dossier(dossier: Dossier, utilisateur, **champs) -> Dossier:
    """La direction confirme un dossier détecté (et peut corriger nom, client, responsable).
    Le dossier devient actif ; un recalcul est demandé."""
    for nom, valeur in champs.items():
        setattr(dossier, nom, valeur)
    dossier.valide = True
    dossier.valide_par = utilisateur
    dossier.valide_le = timezone.now()
    dossier.statut = Dossier.Statut.ACTIF
    dossier.save()
    demander_recalcul(f"dossier validé : {dossier}")
    return dossier
