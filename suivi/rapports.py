"""Rapports de la direction (A05) : agrégations sur les segments ACTIF d'une période.

Les indicateurs par personne et par jour (heures effectives, % prévu, arrivée/départ, amplitude,
occupation) viennent de `moteur.suivi.indicateurs` ; ce module ne fait que lire la base et
assembler. Tout est en heure locale du bureau (TIME_ZONE).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from django.db.models import Count, Max, Q, Sum
from django.utils import timezone

from moteur.suivi import indicateurs
from suivi.models import Dossier, Employe, Poste, Segment
from suivi.services import parametre

DUREE_MAX_PERIODE_J = 366


@dataclass(frozen=True)
class Periode:
    debut: date
    fin: date  # inclus

    @property
    def jours(self) -> int:
        return (self.fin - self.debut).days + 1


def periode_depuis(params, defaut_jours: int = 7) -> Periode:
    """`debut`/`fin` au format AAAA-MM-JJ ; par défaut les 7 derniers jours, fin incluse.
    ValueError si la période est invalide (l'appelant rend 400)."""
    aujourd_hui = timezone.localdate()
    try:
        fin = date.fromisoformat(params["fin"]) if params.get("fin") else aujourd_hui
        debut = (
            date.fromisoformat(params["debut"])
            if params.get("debut")
            else fin - timedelta(days=defaut_jours - 1)
        )
    except ValueError as e:
        raise ValueError("debut et fin doivent être des dates AAAA-MM-JJ") from e
    if fin < debut:
        raise ValueError("fin avant debut")
    p = Periode(debut, fin)
    if p.jours > DUREE_MAX_PERIODE_J:
        raise ValueError(f"période trop longue ({p.jours} jours, maximum {DUREE_MAX_PERIODE_J})")
    return p


def _bornes(p: Periode) -> tuple[datetime, datetime]:
    debut = timezone.make_aware(datetime.combine(p.debut, time.min))
    return debut, debut + timedelta(days=p.jours)


def _segments(p: Periode, **filtres):
    debut, fin = _bornes(p)
    return Segment.objects.filter(debut__gte=debut, debut__lt=fin, **filtres)


def _actifs(p: Periode, **filtres):
    return _segments(p, etat=Segment.Etat.ACTIF, **filtres)


def jours_feries() -> frozenset[date]:
    bruts = parametre("jours_feries", []) or []
    res = set()
    for j in bruts:
        try:
            res.add(date.fromisoformat(str(j)))
        except ValueError:
            continue
    return frozenset(res)


@dataclass(frozen=True)
class _Part:
    debut: datetime
    fin: datetime
    etat: str


def _parts(segments) -> list[_Part]:
    return [_Part(timezone.localtime(s.debut), timezone.localtime(s.fin), s.etat) for s in segments]


def _journee_dict(j: indicateurs.Journee) -> dict:
    return {
        "jour": j.jour.isoformat(),
        "effectif_s": j.effectif_s,
        "prevu_s": j.prevu_s,
        "prevu_pct": str(j.prevu_pct) if j.prevu_pct is not None else None,
        "arrivee": j.arrivee.strftime("%H:%M") if j.arrivee else None,
        "depart": j.depart.strftime("%H:%M") if j.depart else None,
        "amplitude_s": j.amplitude_s,
        "occupation_pct": str(j.occupation_pct) if j.occupation_pct is not None else None,
    }


# -- synthèse ------------------------------------------------------------------------------


def synthese(p: Periode) -> dict:
    """Quatre indicateurs globaux + une ligne par employé actif, avec ses journées."""
    feries = jours_feries()
    segments_par_employe: dict[int, list] = defaultdict(list)
    for s in _segments(p).select_related("employe").order_by("debut"):
        segments_par_employe[s.employe_id].append(s)
    employes = Employe.objects.filter(actif=True).order_by("nom_affiche", "login")

    lignes = []
    total_effectif = total_prevu = 0
    for e in employes:
        syn = indicateurs.synthese(
            _parts(segments_par_employe.get(e.pk, [])),
            p.debut,
            p.fin,
            float(e.heures_prevues_semaine),
            feries,
        )
        total_effectif += syn.effectif_s
        total_prevu += syn.prevu_s
        lignes.append(
            {
                "employe_id": e.pk,
                "employe": str(e),
                "effectif_s": syn.effectif_s,
                "prevu_s": syn.prevu_s,
                "prevu_pct": str(syn.prevu_pct) if syn.prevu_pct is not None else None,
                "jours_travailles": syn.jours_travailles,
                "journees": [_journee_dict(j) for j in syn.journees],
            }
        )
    a_classer = _actifs(p, statut_classement=Segment.StatutClassement.A_CLASSER).aggregate(
        s=Sum("duree_s")
    )["s"]
    return {
        "periode": {"debut": p.debut.isoformat(), "fin": p.fin.isoformat(), "jours": p.jours},
        "effectif_s": total_effectif,
        "prevu_s": total_prevu,
        "prevu_pct": str(indicateurs.pourcentage(total_effectif, total_prevu))
        if total_prevu
        else None,
        "employes_actifs": sum(1 for ligne in lignes if ligne["effectif_s"] > 0),
        "a_classer_s": int(a_classer or 0),
        "employes": lignes,
    }


# -- dossiers ------------------------------------------------------------------------------


def dossiers(p: Periode) -> dict:
    """Temps par dossier, puis par (dossier, employé) ; à part : à classer, brouillons,
    sans fichier."""
    lignes = (
        _actifs(p, dossier__isnull=False)
        .values(
            "dossier_id",
            "dossier__code",
            "dossier__nom",
            "dossier__statut",
            "employe_id",
            "employe__nom_affiche",
            "employe__login",
        )
        .annotate(duree_s=Sum("duree_s"))
        .order_by("dossier__code", "dossier__nom")
    )
    par_dossier: dict[int, dict] = {}
    for ligne in lignes:
        d = par_dossier.setdefault(
            ligne["dossier_id"],
            {
                "dossier_id": ligne["dossier_id"],
                "code": ligne["dossier__code"],
                "nom": ligne["dossier__nom"],
                "statut": ligne["dossier__statut"],
                "duree_s": 0,
                "par_employe": [],
            },
        )
        duree = int(ligne["duree_s"])
        d["duree_s"] += duree
        d["par_employe"].append(
            {
                "employe_id": ligne["employe_id"],
                "employe": ligne["employe__nom_affiche"] or ligne["employe__login"],
                "duree_s": duree,
            }
        )
    hors = _actifs(p, dossier__isnull=True).values("statut_classement").annotate(s=Sum("duree_s"))
    hors_dossier = {h["statut_classement"]: int(h["s"] or 0) for h in hors}
    return {
        "periode": {"debut": p.debut.isoformat(), "fin": p.fin.isoformat()},
        "dossiers": sorted(par_dossier.values(), key=lambda d: -d["duree_s"]),
        "a_classer_s": hors_dossier.get("a_classer", 0),
        "brouillon_s": hors_dossier.get("brouillon", 0),
        "sans_fichier_s": hors_dossier.get("application", 0),
    }


def liste_dossiers(p: Periode) -> list[dict]:
    """Tous les dossiers (détectés compris), leur temps sur la période, leur dernière activité."""
    debut, fin = _bornes(p)
    sur_periode = Q(segments__debut__gte=debut, segments__debut__lt=fin, segments__etat="ACTIF")
    qs = (
        Dossier.objects.select_related("racine", "responsable")
        .annotate(
            duree_s=Sum("segments__duree_s", filter=sur_periode),
            derniere_activite=Max("segments__fin"),
        )
        .order_by("statut", "code", "nom")
    )
    return [
        {
            "id": d.pk,
            "code": d.code,
            "nom": d.nom,
            "client": d.client,
            "statut": d.statut,
            "valide": d.valide,
            "racine": d.racine.chemin if d.racine else None,
            "responsable": str(d.responsable) if d.responsable else None,
            "duree_s": int(d.duree_s or 0),
            "derniere_activite": timezone.localtime(d.derniere_activite).isoformat()
            if d.derniere_activite
            else None,
        }
        for d in qs
    ]


# -- une personne --------------------------------------------------------------------------


def activite_employe(employe: Employe, p: Periode, jour: date | None = None) -> dict:
    """Journées de la période (indicateurs), fichiers les plus travaillés, et la chronologie
    d'un jour (par défaut le dernier de la période) colorée par dossier."""
    segments = list(_segments(p, employe=employe).select_related("dossier").order_by("debut"))
    js = indicateurs.journees(
        _parts(segments), p.debut, p.fin, float(employe.heures_prevues_semaine), jours_feries()
    )
    fichiers: dict[tuple, dict] = {}
    for s in segments:
        if s.etat != Segment.Etat.ACTIF or not (s.fichier or s.chemin):
            continue
        cle = (s.chemin or s.fichier).lower()
        f = fichiers.setdefault(
            cle,
            {
                "fichier": s.fichier or s.chemin.rsplit("\\", 1)[-1],
                "chemin": s.chemin,
                "dossier": s.dossier.code or s.dossier.nom if s.dossier else None,
                "statut": s.statut_classement,
                "duree_s": 0,
            },
        )
        f["duree_s"] += int(s.duree_s)
    jour = jour or p.fin
    chronologie = [
        {
            "debut": timezone.localtime(s.debut).strftime("%H:%M"),
            "fin": timezone.localtime(s.fin).strftime("%H:%M"),
            "duree_s": int(s.duree_s),
            "etat": s.etat,
            "application": s.application,
            "fichier": s.fichier,
            "dossier": (s.dossier.code or s.dossier.nom) if s.dossier else None,
            "statut": s.statut_classement,
        }
        for s in segments
        if timezone.localtime(s.debut).date() == jour
    ]
    return {
        "employe": {"id": employe.pk, "nom": str(employe), "login": employe.login},
        "periode": {"debut": p.debut.isoformat(), "fin": p.fin.isoformat()},
        "journees": [_journee_dict(j) for j in js],
        "fichiers": sorted(fichiers.values(), key=lambda f: -f["duree_s"])[:50],
        "jour": jour.isoformat(),
        "chronologie": chronologie,
    }


# -- à classer -----------------------------------------------------------------------------


def a_classer(p: Periode) -> dict:
    """File groupée par (fichier, chemin, employé) ; brouillons comptés à part."""
    groupes = (
        _actifs(p, statut_classement=Segment.StatutClassement.A_CLASSER)
        .values("fichier", "chemin", "employe_id", "employe__nom_affiche", "employe__login")
        .annotate(duree_s=Sum("duree_s"), segments=Count("id"), dernier=Max("fin"))
        .order_by("-duree_s")
    )
    brouillons = _actifs(p, statut_classement=Segment.StatutClassement.BROUILLON).aggregate(
        s=Sum("duree_s"), n=Count("id")
    )
    return {
        "periode": {"debut": p.debut.isoformat(), "fin": p.fin.isoformat()},
        "groupes": [
            {
                "fichier": g["fichier"],
                "chemin": g["chemin"],
                "employe_id": g["employe_id"],
                "employe": g["employe__nom_affiche"] or g["employe__login"],
                "duree_s": int(g["duree_s"]),
                "segments": g["segments"],
                "dernier": timezone.localtime(g["dernier"]).isoformat(),
            }
            for g in groupes
        ],
        "brouillons": {"duree_s": int(brouillons["s"] or 0), "segments": brouillons["n"]},
    }


# -- postes --------------------------------------------------------------------------------


def _heures_ouvrees_depuis(instant: datetime, maintenant: datetime) -> float:
    """Heures écoulées en ne comptant pas les samedis et dimanches."""
    heures = 0.0
    courant = instant
    while courant < maintenant:
        suivant = min(
            maintenant,
            (courant + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0),
        )
        if courant.weekday() < 5:
            heures += (suivant - courant).total_seconds() / 3600
        courant = suivant
    return heures


def etat_postes(maintenant: datetime | None = None) -> list[dict]:
    """Rouge : muet depuis plus de 24 h ouvrées (ou jamais vu envoyer) ; orange : trop de
    démarrages dans la semaine (seuil `seuil_demarrages_semaine`, défaut 10)."""
    maintenant = timezone.localtime(maintenant or timezone.now())
    seuil_demarrages = int(parametre("seuil_demarrages_semaine", 10) or 10)
    res = []
    for poste in Poste.objects.order_by("nom"):
        if poste.dernier_envoi is None:
            muet_h, alerte = None, "rouge"
        else:
            muet_h = _heures_ouvrees_depuis(timezone.localtime(poste.dernier_envoi), maintenant)
            alerte = (
                "rouge"
                if muet_h > 24
                else ("orange" if poste.demarrages_semaine > seuil_demarrages else None)
            )
        res.append(
            {
                "id": poste.pk,
                "nom": poste.nom,
                "version_agent": poste.version_agent,
                "dernier_envoi": timezone.localtime(poste.dernier_envoi).isoformat()
                if poste.dernier_envoi
                else None,
                "muet_depuis_h_ouvrees": round(muet_h, 1) if muet_h is not None else None,
                "demarrages_semaine": poste.demarrages_semaine,
                "alerte": alerte,
            }
        )
    return res
