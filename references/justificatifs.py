"""Justificatifs, réclamations, ouvrages et quantités des références (ADR 0011).

Les fichiers sont lus dans REFERENCES/02_JUSTIFICATIFS/<code> du partage GIC, jamais écrits :
mêmes fonctions de lecture que les pièces administratives (ADR 0010).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Count, Q, QuerySet
from django.utils import timezone

from administratif.services import (
    PartageIndisponibleError,
    chemin_absolu,
    empreinte,
    nb_pages,
    relatif,
)
from moteur.suivi.classement import est_technique
from references.models import TYPES_ESSENTIELS, Mission, PieceJustificative, Quantite, Reclamation
from referentiel.models import TypeQuantite

DOSSIER = "REFERENCES\\02_JUSTIFICATIFS"
NOMS_NORMALISES = (
    "GARDE.PDF",
    "SIGNATURE.PDF",
    "ATTESTATION.PDF",
    "DEUXIEME-PAGE.PDF",
    "CONTRAT_COMPLET.PDF",
)
BONNE = Q(pieces__lisible__in=("oui", "moyen"), pieces__coherente="oui")


def dossier_de(mission: Mission) -> str:
    return f"{DOSSIER}\\{mission.code}"


def type_propose(nom: str) -> str:
    """D'après le nom normalisé du rangement : GARDE.pdf, SIGNATURE.pdf, ATTESTATION.pdf,
    DEUXIEME-PAGE.pdf (ADR 0015), CONTRAT_COMPLET.pdf ; un avenant ; sinon « autre »."""
    n = nom.upper()
    for mot, type_ in (  # « page de garde du contrat » est une garde : CONTRAT en dernier
        ("AVENANT", "avenant"),
        ("DEUXIEME", "deuxieme_page"),
        ("2E PAGE", "deuxieme_page"),
        ("2E-PAGE", "deuxieme_page"),
        ("GARDE", "garde"),
        ("SIGNATURE", "signature"),
        ("ATTESTATION", "attestation"),
        ("PV", "attestation"),
        ("CONTRAT", "contrat_complet"),
    ):
        if mot in n:
            return type_
    return "autre"


@dataclass
class Fichier:
    nom: str
    chemin: str
    empreinte: str
    taille: int
    nb_pages: int | None
    type_propose: str
    statut: str = "nouveau"  # nouveau | rattache | ailleurs | doublon
    piece: PieceJustificative | None = None


def fichiers(mission: Mission) -> list[Fichier]:
    """Les fichiers posés dans le dossier du code (pas ses sous-dossiers), avec leur statut :
    nouveau, déjà rattaché à cette référence, rattaché à une autre, ou doublon d'un autre."""
    dossier = chemin_absolu(dossier_de(mission))
    if not dossier.is_dir():
        raise PartageIndisponibleError(
            f"dossier introuvable sur le partage : {dossier_de(mission)}"
        )
    lus = [
        Fichier(
            nom=p.name,
            chemin=relatif(p),
            empreinte=empreinte(p),
            taille=p.stat().st_size,
            nb_pages=nb_pages(p),
            type_propose=type_propose(p.name),
        )
        for p in sorted(dossier.iterdir(), key=lambda x: x.name.lower())
        if p.is_file() and not est_technique(p.name)
    ]
    connues = {
        x.empreinte: x
        for x in PieceJustificative.objects.select_related("mission").filter(
            empreinte__in=[f.empreinte for f in lus]
        )
    }
    # entre fichiers identiques, le « nouveau » est celui au nom normalisé (GARDE.pdf…), sinon
    # le nom le plus court ; les autres sont des doublons
    premiers: dict[str, Fichier] = {}
    for f in sorted(lus, key=lambda x: (x.nom.upper() not in NOMS_NORMALISES, len(x.nom), x.nom)):
        premiers.setdefault(f.empreinte, f)
    for f in lus:
        if f.empreinte in connues:
            f.piece = connues[f.empreinte]
            f.statut = "rattache" if f.piece.mission_id == mission.pk else "ailleurs"
        elif premiers[f.empreinte] is not f:
            f.statut = "doublon"
    return lus


@transaction.atomic
def rattacher(mission: Mission, fichier: Fichier, type_: str, utilisateur) -> PieceJustificative:
    if fichier.statut != "nouveau":
        raise ValueError(f"« {fichier.nom} » ne peut pas être rattaché : {fichier.statut}")
    if type_ not in PieceJustificative.Type.values:
        raise ValueError("type de pièce inconnu")
    if type_ in TYPES_ESSENTIELS and mission.pieces.filter(type=type_).exists():
        libelle = PieceJustificative.Type(type_).label
        raise ValueError(f"cette référence a déjà une {libelle} : détachez-la d'abord")
    chemin = chemin_absolu(fichier.chemin)
    if not chemin.is_file() or empreinte(chemin) != fichier.empreinte:
        raise ValueError(f"« {fichier.nom} » a changé ou disparu : rechargez la page")
    return PieceJustificative.objects.create(
        mission=mission,
        type=type_,
        chemin=fichier.chemin,
        empreinte=fichier.empreinte,
        taille=fichier.taille,
        nb_pages=fichier.nb_pages,
        rattachee_par=utilisateur if getattr(utilisateur, "pk", None) else None,
    )


ESSENTIELS = {"GARDE.PDF": "garde", "SIGNATURE.PDF": "signature", "ATTESTATION.PDF": "attestation"}


@dataclass
class RapportRattachement:
    rattachees: list[str] = field(default_factory=list)
    deja: list[str] = field(default_factory=list)
    incompletes: list[str] = field(default_factory=list)
    erreurs: list[str] = field(default_factory=list)

    @property
    def resume(self) -> str:
        return (
            f"{len(self.rattachees)} pièce(s) rattachée(s), {len(self.deja)} déjà rattachée(s), "
            f"{len(self.incompletes)} référence(s) incomplète(s) laissée(s), "
            f"{len(self.erreurs)} erreur(s)"
        )


def _empechement(f: Fichier) -> str:
    if f.statut == "ailleurs":
        return f"déjà rattaché à {f.piece.mission.code}"
    if f.statut == "rattache":
        return f"déjà rattaché comme {f.piece.get_type_display()}"
    return "identique à un autre fichier du dossier"


@transaction.atomic
def rattacher_dossiers(
    simuler: bool = False, utilisateur=None, partielles: bool = False
) -> RapportRattachement:
    """Rattache en une fois GARDE.pdf, SIGNATURE.pdf et ATTESTATION.pdf des dossiers
    REFERENCES/02_JUSTIFICATIFS/<code>, pour les seules références dont les trois pièces sont là
    (posées ou déjà rattachées) ; les autres attendent, sauf avec `partielles` : leurs pièces
    présentes sont rattachées aussi, les manquantes restent à réclamer. Rien n'est audité :
    l'audit reste un regard à l'écran. Une référence absorbée ne reçoit rien (un doublon ne se
    rattache pas). En simulation, rien n'est gardé."""
    racine = chemin_absolu(DOSSIER)
    if not racine.is_dir():
        raise PartageIndisponibleError(f"dossier introuvable sur le partage : {DOSSIER}")
    rapport = RapportRattachement()
    missions = Mission.objects.select_related("absorbee_par").in_bulk(field_name="code")
    for dossier in sorted(p for p in racine.iterdir() if p.is_dir()):
        code = dossier.name
        m = missions.get(code)
        if m is None:
            rapport.erreurs.append(f"{code} : référence inconnue")
            continue
        if m.absorbee_par_id:
            rapport.erreurs.append(
                f"{code} : absorbée par {m.absorbee_par.code}, ses pièces vont dans son dossier"
            )
            continue
        poses = {f.nom.upper(): f for f in fichiers(m) if f.nom.upper() in ESSENTIELS}
        deja = set(m.pieces.filter(type__in=TYPES_ESSENTIELS).values_list("type", flat=True))
        a_faire, manquent = [], []
        for nom, type_ in ESSENTIELS.items():
            if type_ in deja:
                continue
            f = poses.get(nom)
            if f is not None and f.statut != "nouveau":
                rapport.erreurs.append(f"{code} : « {f.nom} » {_empechement(f)}")
                f = None
            if f is None:
                manquent.append(type_)
            else:
                a_faire.append((f, type_))
        if manquent:
            rapport.incompletes.append(f"{code} : manque {', '.join(manquent)}")
            if not partielles:
                continue
        try:
            with transaction.atomic():  # une référence entière ou rien
                for f, type_ in a_faire:
                    rattacher(m, f, type_, utilisateur)
        except ValueError as e:
            rapport.erreurs.append(f"{code} : {e}")
            continue
        rapport.deja += [f"{code} : {t}" for t in TYPES_ESSENTIELS if t in deja]
        rapport.rattachees += [f"{code} : {t}" for _, t in a_faire]
    if simuler:
        transaction.set_rollback(True)
    return rapport


def auditer(piece: PieceJustificative, donnees: dict, utilisateur) -> PieceJustificative:
    """Les quatre questions du chantier 3 : présente (rattachée), lisible, de la bonne nature,
    cohérente avec les deux autres."""
    for champ, choix in (
        ("nature_exacte", PieceJustificative.Nature.values),
        ("lisible", PieceJustificative.Lisible.values),
        ("coherente", PieceJustificative.Coherente.values),
    ):
        valeur = donnees.get(champ, "")
        if valeur and valeur not in choix:
            raise ValueError(f"{champ} : « {valeur} » inconnu")
        setattr(piece, champ, valeur)
    piece.date_document = donnees.get("date_document") or None
    piece.observations = (donnees.get("observations") or "").strip()[:500]
    piece.auditee_par = utilisateur if getattr(utilisateur, "pk", None) else None
    piece.auditee_le = timezone.now()
    piece.save()
    return piece


def reclamer(mission: Mission, type_: str, etat: str, le, contact: str, note: str, utilisateur):
    if type_ not in PieceJustificative.Type.values or etat not in Reclamation.Etat.values:
        raise ValueError("pièce ou état de réclamation inconnu")
    return Reclamation.objects.create(
        mission=mission,
        type=type_,
        etat=etat,
        le=le or timezone.localdate(),
        contact_client=contact.strip()[:200],
        note=note.strip()[:300],
        par=utilisateur if getattr(utilisateur, "pk", None) else None,
    )


@dataclass
class Emplacement:
    """Une des trois pièces qui rendent une référence complète."""

    type: str
    libelle: str
    piece: PieceJustificative | None
    reclamation: Reclamation | None = None

    @property
    def etat(self) -> str:
        if self.piece is None:
            return "manquante"
        if not self.piece.lisible or not self.piece.coherente:
            return "a_auditer"
        return "bonne" if self.piece.bonne else "faible"


@dataclass
class EtatJustificatifs:
    emplacements: list[Emplacement]
    autres: list[PieceJustificative] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return all(e.etat == "bonne" for e in self.emplacements)

    @property
    def nb_bonnes(self) -> int:
        return sum(1 for e in self.emplacements if e.etat == "bonne")

    @property
    def nb_rattachees(self) -> int:
        return sum(1 for e in self.emplacements if e.piece is not None)

    @property
    def nb_a_auditer(self) -> int:
        return sum(1 for e in self.emplacements if e.etat == "a_auditer")


def etat_justificatifs(mission: Mission) -> EtatJustificatifs:
    pieces = list(mission.pieces.select_related("auditee_par").order_by("type", "pk"))
    reclamations: dict[str, Reclamation] = {}
    for r in mission.reclamations.order_by("le", "pk"):
        reclamations[r.type] = r  # la plus récente l'emporte
    emplacements = [
        Emplacement(
            t,
            PieceJustificative.Type(t).label,
            next((p for p in pieces if p.type == t), None),
            reclamations.get(t),
        )
        for t in TYPES_ESSENTIELS
    ]
    return EtatJustificatifs(emplacements, [p for p in pieces if p.type not in TYPES_ESSENTIELS])


def avec_compteurs(qs: QuerySet[Mission]) -> QuerySet[Mission]:
    """Annote chaque référence du nombre de ses pièces essentielles (0 à 3) : rattachées,
    à auditer (lisibilité ou cohérence pas encore dites) et bonnes."""
    essentielles = Q(pieces__type__in=TYPES_ESSENTIELS)
    return qs.annotate(
        nb_bonnes=Count("pieces", filter=BONNE & essentielles, distinct=True),
        nb_rattachees=Count("pieces", filter=essentielles, distinct=True),
        nb_a_auditer=Count(
            "pieces",
            filter=essentielles & (Q(pieces__lisible="") | Q(pieces__coherente="")),
            distinct=True,
        ),
    )


# -- ouvrages, livrables, quantités -----------------------------------------------------------
def lire_quantite(texte: str) -> Decimal | None:
    t = (texte or "").replace(" ", "").replace("\xa0", "").replace(" ", "").replace(",", ".")
    if not t:
        return None
    try:
        valeur = Decimal(t)
    except InvalidOperation as e:
        raise ValueError(f"quantité illisible : {texte}") from e
    if valeur < 0:
        raise ValueError(f"quantité négative : {texte}")
    return valeur


@transaction.atomic
def enregistrer_ouvrages(
    mission: Mission,
    types_ouvrage: list[int],
    livrables: list[int],
    quantites: dict[int, tuple[str, str]],
) -> None:
    """Remplace les ouvrages et livrables de la référence ; une quantité vide est retirée.
    ValueError (rien n'est gardé) si une quantité est illisible."""
    mission.types_ouvrage.set(types_ouvrage)
    mission.livrables.set(livrables)
    for type_q in TypeQuantite.objects.filter(pk__in=quantites):
        texte, source = quantites[type_q.pk]
        valeur = lire_quantite(texte)
        if valeur is None:
            Quantite.objects.filter(mission=mission, type=type_q).delete()
        else:
            Quantite.objects.update_or_create(
                mission=mission,
                type=type_q,
                defaults={"valeur": valeur, "source": source.strip()[:200]},
            )
