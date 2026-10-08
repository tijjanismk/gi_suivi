"""Passage entre l'ORM et le moteur : le moteur ne voit que des dataclasses (CONTEXT.md, r. 1)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from django.db import transaction
from django.utils import timezone

from moteur.suivi import indicateurs
from moteur.suivi import types as m
from moteur.suivi.classement import classer_observation, normaliser_chemin
from suivi.models import (
    DemandeRecalcul,
    Dossier,
    Employe,
    Parametre,
    Racine,
    RegleException,
    Segment,
)

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


# -- ma journée (A04) ----------------------------------------------------------------------


def employe_de(utilisateur) -> Employe | None:
    """L'employé derrière un utilisateur : lié à la première ingestion, sinon par le login."""
    return (
        Employe.objects.filter(utilisateur=utilisateur).first()
        or Employe.objects.filter(login__iexact=utilisateur.login_windows).first()
    )


@dataclass(frozen=True)
class _Part:
    debut: datetime
    fin: datetime
    etat: str


def activite_du_jour(employe: Employe | None, jour: date | None = None) -> dict:
    """Ce que voit la personne elle-même (règle de transparence) : ses heures du jour, par
    dossier et par application, arrivée/départ. Une personne ne voit que ses segments."""
    jour = jour or timezone.localdate()
    debut = timezone.make_aware(datetime.combine(jour, time.min))
    resultat: dict = {
        "jour": jour.isoformat(),
        "employe": str(employe) if employe else None,
        "total_s": 0,
        "total_hm": "0 h 00",
        "arrivee": None,
        "depart": None,
        "amplitude_s": 0,
        "occupation_pct": None,
        "prevu_pct": None,
        "par_dossier": [],
        "a_classer_s": 0,
        "sans_fichier_s": 0,
        "par_application": [],
    }
    if employe is None:
        return resultat
    segments = list(
        Segment.objects.filter(
            employe=employe, debut__gte=debut, debut__lt=debut + timedelta(days=1)
        )
        .select_related("dossier")
        .order_by("debut")
    )
    actifs = [s for s in segments if s.etat == Segment.Etat.ACTIF]

    (j,) = indicateurs.journees(
        [_Part(timezone.localtime(s.debut), timezone.localtime(s.fin), s.etat) for s in segments],
        jour,
        jour,
        float(employe.heures_prevues_semaine),
    )
    resultat.update(
        total_s=j.effectif_s,
        total_hm=f"{j.effectif_s // 3600} h {j.effectif_s % 3600 // 60:02d}",
        arrivee=j.arrivee.strftime("%H:%M") if j.arrivee else None,
        depart=j.depart.strftime("%H:%M") if j.depart else None,
        amplitude_s=j.amplitude_s,
        occupation_pct=str(j.occupation_pct) if j.occupation_pct is not None else None,
        prevu_pct=str(j.prevu_pct) if j.prevu_pct is not None else None,
    )

    par_dossier: dict[int, dict] = {}
    par_app: dict[str, int] = {}
    for s in actifs:
        d = int(s.duree_s)
        par_app[s.application] = par_app.get(s.application, 0) + d
        if s.dossier_id:
            entree = par_dossier.setdefault(
                s.dossier_id, {"code": s.dossier.code, "nom": s.dossier.nom, "duree_s": 0}
            )
            entree["duree_s"] += d
        elif s.fichier or s.chemin:
            resultat["a_classer_s"] += d
        else:
            resultat["sans_fichier_s"] += d
    resultat["par_dossier"] = sorted(par_dossier.values(), key=lambda x: -x["duree_s"])
    resultat["par_application"] = [
        {"application": a, "duree_s": d} for a, d in sorted(par_app.items(), key=lambda x: -x[1])
    ]
    return resultat


def racines_pour_agent() -> dict:
    """Ce que l'agent lit au démarrage, en plus du registre : racines telles que saisies dans
    l'admin (pas normalisées), correspondances lettre → UNC, seuils."""
    return {
        "racines": [
            {"chemin": r.chemin, "profondeur": r.profondeur, "motif_code": r.motif_code}
            for r in Racine.objects.filter(active=True)
        ],
        "correspondance_lecteurs": correspondance_lecteurs(),
        "seuil_inactivite_s": parametre("seuil_inactivite_s", 300),
        "intervalle_s": parametre("intervalle_s", 5),
    }


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
