"""POST /api/segments — réception des lots envoyés par les agents de poste (A01).

Contrat (docs/suivi-transposition-python.md, 4.2) : corps JSON
{lot_id, poste, utilisateur, version_agent, sid?, segments: [{debut, fin, duree_s, etat,
application, fichier, chemin}]}. Réponse 200 {recu, deja_recu, segments}.

- Idempotent : un lot_id déjà reçu rend 200 sans rien insérer (l'agent le marque acquitté).
- L'identité vient d'IIS (middleware) ; le lot doit la désigner, sinon 403 : un agent ne peut
  pas envoyer les heures d'un autre.
- Un lot vide est accepté : il tient le poste « vivant » (dernier_envoi).
- Classement à la réception par le moteur ; un dossier inconnu reste « à classer » jusqu'à A02
  (création des dossiers détectés et recalcul).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from identite.models import normaliser_login
from moteur.suivi.classement import classer_observation
from moteur.suivi.types import Observation
from suivi.models import Dossier, Employe, Poste, Segment
from suivi.services import correspondance_lecteurs, exceptions_moteur, racines_moteur

MAX_SEGMENTS_PAR_LOT = 5000
ETATS = {Segment.Etat.ACTIF.value, Segment.Etat.INACTIF.value}


@dataclass(frozen=True)
class SegmentRecu:
    debut: datetime
    fin: datetime
    etat: str
    application: str
    fichier: str
    chemin: str


@dataclass(frozen=True)
class Lot:
    lot_id: uuid.UUID
    poste: str
    utilisateur: str
    version_agent: str
    sid: str | None
    segments: list[SegmentRecu]


def _texte(valeur, maxi: int, nom: str, erreurs: list[str], obligatoire: bool = False) -> str:
    if valeur is None:
        if obligatoire:
            erreurs.append(f"{nom} manquant")
        return ""
    if not isinstance(valeur, str):
        erreurs.append(f"{nom} doit être une chaîne")
        return ""
    v = valeur.strip()
    if obligatoire and not v:
        erreurs.append(f"{nom} vide")
    return v[:maxi]


def _instant(valeur, nom: str, erreurs: list[str]) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(valeur))
    except (TypeError, ValueError):
        erreurs.append(f"{nom} : date invalide")
        return None
    return dt if timezone.is_aware(dt) else timezone.make_aware(dt)


def valider_lot(data) -> tuple[Lot | None, list[str]]:
    erreurs: list[str] = []
    if not isinstance(data, dict):
        return None, ["le corps doit être un objet JSON"]
    try:
        lot_id = uuid.UUID(str(data.get("lot_id")))
    except (TypeError, ValueError):
        erreurs.append("lot_id : UUID attendu")
        lot_id = None
    poste = _texte(data.get("poste"), 100, "poste", erreurs, obligatoire=True)
    utilisateur = _texte(data.get("utilisateur"), 150, "utilisateur", erreurs, obligatoire=True)
    version = _texte(data.get("version_agent"), 20, "version_agent", erreurs)
    sid = _texte(data.get("sid"), 100, "sid", erreurs) or None

    bruts = data.get("segments", [])
    if not isinstance(bruts, list):
        erreurs.append("segments : liste attendue")
        bruts = []
    if len(bruts) > MAX_SEGMENTS_PAR_LOT:
        erreurs.append(f"segments : {len(bruts)} > {MAX_SEGMENTS_PAR_LOT}")
        bruts = []

    segments: list[SegmentRecu] = []
    for i, s in enumerate(bruts):
        if not isinstance(s, dict):
            erreurs.append(f"segments[{i}] : objet attendu")
            continue
        e: list[str] = []
        debut = _instant(s.get("debut"), "debut", e)
        fin = _instant(s.get("fin"), "fin", e)
        etat = str(s.get("etat", "")).upper()
        if etat not in ETATS:
            e.append(f"etat « {s.get('etat')} » inconnu")
        application = _texte(s.get("application"), 200, "application", e, obligatoire=True)
        fichier = _texte(s.get("fichier"), 400, "fichier", e)
        chemin = _texte(s.get("chemin"), 1000, "chemin", e)
        if debut and fin and fin < debut:
            e.append("fin avant debut")
        if e:
            erreurs.append(f"segments[{i}] : " + " ; ".join(e))
            continue
        segments.append(SegmentRecu(debut, fin, etat, application, fichier, chemin))

    if erreurs or lot_id is None:
        return None, erreurs
    return Lot(lot_id, poste, utilisateur, version, sid, segments), []


def _meme_personne(lot: Lot, login_identite: str) -> bool:
    """« a.traore » ou « GICONSEILS\\a.traore » dans le lot doit désigner l'identité Kerberos."""
    identite = normaliser_login(login_identite)
    declare = normaliser_login(lot.utilisateur)
    return declare == identite or declare == identite.rsplit("\\", 1)[-1]


def _employe(lot: Lot, utilisateur) -> Employe:
    login = utilisateur.login_windows
    employe = None
    if lot.sid:
        employe = Employe.objects.filter(sid_ad=lot.sid).first()
    if employe is None:
        employe = Employe.objects.filter(login__iexact=login).first()
    if employe is None:
        employe = Employe(login=login, nom_affiche=login.rsplit("\\", 1)[-1])
    champs: list[str] = []
    if lot.sid and employe.sid_ad != lot.sid:
        employe.sid_ad, champs = lot.sid, [*champs, "sid_ad"]
    if employe.login != login:
        employe.login, champs = login, [*champs, "login"]
    if employe.utilisateur_id is None:
        employe.utilisateur, champs = utilisateur, [*champs, "utilisateur"]
    if employe.pk is None:
        employe.save()
    elif champs:
        employe.save(update_fields=champs)
    return employe


def _poste(lot: Lot) -> Poste:
    poste, _ = Poste.objects.get_or_create(nom=lot.poste)
    poste.version_agent = lot.version_agent or poste.version_agent
    poste.dernier_envoi = timezone.now()
    poste.save(update_fields=["version_agent", "dernier_envoi"])
    return poste


def _classer(segments: list[SegmentRecu]) -> list[tuple[str, Dossier | None]]:
    racines, lecteurs, exceptions = racines_moteur(), correspondance_lecteurs(), exceptions_moteur()
    classements = [
        classer_observation(
            Observation(s.debut, s.application, s.fichier or None, s.chemin or None, 0.0),
            racines,
            lecteurs,
            exceptions,
        )
        for s in segments
    ]
    chemins = {c.dossier_chemin for c in classements if c.statut == "dossier"}
    connus = {d.chemin_windows: d for d in Dossier.objects.filter(chemin_windows__in=chemins)}
    resultat: list[tuple[str, Dossier | None]] = []
    for c in classements:
        dossier = connus.get(c.dossier_chemin) if c.statut == "dossier" else None
        # Dossier jamais vu : « à classer » jusqu'à ce que A02 le crée comme détecté
        statut = (
            c.statut if (c.statut != "dossier" or dossier) else Segment.StatutClassement.A_CLASSER
        )
        resultat.append((statut, dossier))
    return resultat


@csrf_exempt
@require_POST
def recevoir_segments(request: HttpRequest) -> JsonResponse:
    try:
        data = json.loads(request.body or b"")
    except ValueError:
        return JsonResponse({"erreurs": ["JSON invalide"]}, status=400)
    lot, erreurs = valider_lot(data)
    if lot is None:
        return JsonResponse({"erreurs": erreurs}, status=400)
    if not _meme_personne(lot, request.user.login_windows):
        return JsonResponse(
            {"erreur": "le lot ne correspond pas à l'identité de la requête"}, status=403
        )

    with transaction.atomic():
        if Segment.objects.filter(lot_id=lot.lot_id).exists():
            return JsonResponse({"recu": True, "deja_recu": True, "segments": 0})
        employe = _employe(lot, request.user)
        poste = _poste(lot)
        classements = _classer(lot.segments)
        Segment.objects.bulk_create(
            [
                Segment(
                    employe=employe,
                    poste=poste,
                    dossier=dossier,
                    debut=s.debut,
                    fin=s.fin,
                    duree_s=Decimal(str(round((s.fin - s.debut).total_seconds(), 1))),
                    etat=s.etat,
                    application=s.application,
                    fichier=s.fichier,
                    chemin=s.chemin,
                    statut_classement=statut,
                    lot_id=lot.lot_id,
                )
                for s, (statut, dossier) in zip(lot.segments, classements, strict=True)
            ],
            batch_size=500,
        )
    return JsonResponse({"recu": True, "deja_recu": False, "segments": len(lot.segments)})
