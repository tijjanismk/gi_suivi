"""Orchestration des pièces administratives (ADR 0010) : lecture des dossiers du partage,
registre, dépôt d'une version, retrait, demandes de renouvellement. Les calculs d'échéance sont
dans `moteur.administratif.echeances` ; ici, on lit la base et le partage, sans rien écrire sur
le partage (règle 4 : l'application ne renomme, ne déplace ni ne supprime aucun fichier).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from administratif.models import DemandeRenouvellement, PieceAdministrative, TypePiece
from moteur.administratif import echeances
from moteur.suivi.classement import est_technique

_SEP = re.compile(r"[\\/]+")


class PartageIndisponibleError(Exception):
    """Le partage GIC n'est pas configuré ou pas joignable depuis le serveur."""


# -- partage ----------------------------------------------------------------------------------
def racine_partage() -> Path:
    racine = (settings.PARTAGE_GIC or "").strip()
    if not racine:
        raise PartageIndisponibleError("le partage GIC n'est pas configuré (PARTAGE_GIC)")
    return Path(racine)


def chemin_absolu(relatif: str) -> Path:
    """`ADMINISTRATIF\\PIECES\\X\\a.pdf` → chemin sur ce système. Refuse de sortir du partage."""
    racine = racine_partage()
    morceaux = [m for m in _SEP.split(relatif) if m]
    if any(m in (".", "..") or ":" in m for m in morceaux):
        raise ValueError(f"chemin refusé : {relatif}")
    return racine.joinpath(*morceaux)


def relatif(chemin: Path) -> str:
    """Chemin sur ce système → forme stockée en base, relative au partage, en `\\`."""
    return "\\".join(chemin.relative_to(racine_partage()).parts)


def empreinte(chemin: Path) -> str:
    h = hashlib.sha256()
    with chemin.open("rb") as f:
        for bloc in iter(lambda: f.read(1 << 20), b""):
            h.update(bloc)
    return h.hexdigest()


_PAGE = re.compile(rb"/Type\s*/Page(?![a-zA-Z])")


def nb_pages(chemin: Path) -> int | None:
    """Pages d'un PDF, par simple comptage des objets « /Type /Page » : exact pour les PDF
    de scanner, None quand on ne sait pas (fichier non PDF ou pages compressées)."""
    if chemin.suffix.lower() != ".pdf":
        return None
    try:
        n = len(_PAGE.findall(chemin.read_bytes()))
    except OSError:
        return None
    return n or None


@dataclass
class FichierDuDossier:
    """Un fichier posé dans le dossier d'un type, tel que l'écran de dépôt le présente."""

    nom: str
    chemin: str  # relatif au partage
    empreinte: str
    taille: int
    modifie_le: date
    nb_pages: int | None = None
    statut: str = "nouveau"  # nouveau | doublon | deja_enregistre (copie) | enregistre (lui-même)
    meme_que: str = ""  # nom du fichier identique (doublon) ou version déjà enregistrée
    version: PieceAdministrative | None = None

    @property
    def enregistrable(self) -> bool:
        return self.statut == "nouveau"


def fichiers_du_dossier(type_piece: TypePiece) -> list[FichierDuDossier]:
    """Les fichiers posés directement dans le dossier du type (pas ses sous-dossiers, où l'on
    range les anciennes versions), du plus récent au plus ancien. Chacun est nouveau, doublon
    d'un autre fichier du dossier, ou déjà enregistré (même contenu qu'une version en base)."""
    dossier = chemin_absolu(type_piece.dossier)
    if not dossier.is_dir():
        raise PartageIndisponibleError(f"dossier introuvable sur le partage : {type_piece.dossier}")
    fichiers = sorted(
        (p for p in dossier.iterdir() if p.is_file() and not est_technique(p.name)),
        key=lambda p: (-p.stat().st_mtime, p.name.lower()),
    )
    lus: list[FichierDuDossier] = []
    for p in fichiers:
        st = p.stat()
        lus.append(
            FichierDuDossier(
                nom=p.name,
                chemin=relatif(p),
                empreinte=empreinte(p),
                taille=st.st_size,
                modifie_le=date.fromtimestamp(st.st_mtime),
                nb_pages=nb_pages(p),
            )
        )
    connues = {
        v.empreinte: v
        for v in PieceAdministrative.objects.select_related("type").filter(
            empreinte__in=[f.empreinte for f in lus]
        )
    }
    premier: dict[str, FichierDuDossier] = {}
    for f in reversed(lus):  # le plus ancien des fichiers identiques reste le « nouveau »
        if f.empreinte in connues:
            f.version = connues[f.empreinte]
            # le fichier même d'une version, ou une copie de ce fichier posée à côté
            f.statut = "enregistre" if f.version.chemin == f.chemin else "deja_enregistre"
            f.meme_que = str(f.version)
        elif f.empreinte in premier:
            f.statut, f.meme_que = "doublon", premier[f.empreinte].nom
        else:
            premier[f.empreinte] = f
    return lus


def retrouver_deplaces(type_piece: TypePiece) -> int:
    """Les versions dont le fichier a été déplacé à la main dans le dossier du type (vers
    `_perimees\\`, par exemple) : retrouvées par leur empreinte, chemin mis à jour en base.
    Rend le nombre de chemins corrigés."""
    perdues = [
        v for v in PieceAdministrative.objects.filter(type=type_piece) if not _existe(v.chemin)
    ]
    if not perdues:
        return 0
    dossier = chemin_absolu(type_piece.dossier)
    par_taille: dict[int, list[PieceAdministrative]] = {}
    for v in perdues:
        par_taille.setdefault(v.taille or -1, []).append(v)
    corriges = 0
    for p in dossier.rglob("*"):
        if not p.is_file():
            continue
        candidates = par_taille.get(p.stat().st_size, [])
        if not candidates:
            continue
        e = empreinte(p)
        for v in candidates:
            if v.empreinte == e:
                v.chemin = relatif(p)
                v.save(update_fields=["chemin"])
                candidates.remove(v)
                corriges += 1
                break
    return corriges


def _existe(chemin_relatif: str) -> bool:
    try:
        return chemin_absolu(chemin_relatif).is_file()
    except (PartageIndisponibleError, ValueError):
        return False


# -- registre ---------------------------------------------------------------------------------
@dataclass
class LigneRegistre:
    type: TypePiece
    version: PieceAdministrative | None
    etat: echeances.EtatPiece
    demande: DemandeRenouvellement | None = None
    versions: list[PieceAdministrative] = field(default_factory=list)

    @property
    def exigee(self) -> bool:
        return self.type.exigee_par_defaut

    @property
    def alerte(self) -> bool:
        """Ce qui demande une action : expirée ou à renouveler, ou manquante si exigée."""
        if self.etat.etat == echeances.Etat.MANQUANTE:
            return self.exigee
        return self.etat.etat in (echeances.Etat.EXPIREE, echeances.Etat.A_RENOUVELER)

    @property
    def cle_etat(self) -> str:
        """Pour l'affichage : une manquante non exigée n'est pas une alerte."""
        if self.etat.etat == echeances.Etat.MANQUANTE and not self.exigee:
            return "non_requise"
        return self.etat.etat.value

    @property
    def libelle_etat(self) -> str:
        return libelle_etat(self.cle_etat, self.etat.jours)


LIBELLES = {
    "valide": "valide",
    "permanente": "permanente",
    "manquante": "manquante",
    "non_requise": "non requise",
}


def libelle_etat(cle: str, jours: int | None) -> str:
    if cle == "a_renouveler":
        return "expire aujourd'hui" if jours == 0 else f"expire dans {jours} j"
    if cle == "expiree":
        return f"expirée depuis {-jours} j" if jours else "expirée"
    if cle == "valide" and jours is not None:
        return f"valide · {jours} j"
    return LIBELLES.get(cle, cle)


def version_en_cours(versions: list[PieceAdministrative]) -> PieceAdministrative | None:
    """La plus récente par date d'émission parmi les non retirées (ADR 0010, § 2)."""
    actives = [v for v in versions if not v.retiree]
    return max(actives, key=lambda v: (v.date_emission, v.pk), default=None)


def registre(date_reference: date | None = None, types=None) -> list[LigneRegistre]:
    """Une ligne par type actif : version en cours, état à `date_reference` (aujourd'hui par
    défaut), demande de renouvellement ouverte."""
    date_reference = date_reference or timezone.localdate()
    types = list(types if types is not None else TypePiece.objects.filter(actif=True))
    versions: dict[int, list[PieceAdministrative]] = {t.pk: [] for t in types}
    for v in PieceAdministrative.objects.filter(type__in=types).select_related("deposee_par"):
        versions[v.type_id].append(v)
    demandes = {
        d.type_id: d
        for d in DemandeRenouvellement.objects.filter(type__in=types, close_le=None).order_by(
            "demandee_le", "pk"
        )
    }  # la plus récente ouverte l'emporte
    lignes = []
    for t in types:
        v = version_en_cours(versions[t.pk])
        e = echeances.etat(v.pour_moteur() if v else None, date_reference, t.rappel_jours)
        historique = sorted(versions[t.pk], key=lambda x: (x.date_emission, x.pk), reverse=True)
        lignes.append(LigneRegistre(t, v, e, demandes.get(t.pk), historique))
    return lignes


def compteurs(lignes: list[LigneRegistre]) -> dict[str, int]:
    etats = echeances.Etat
    return {
        "valides": sum(1 for x in lignes if x.etat.etat in (etats.VALIDE, etats.PERMANENTE)),
        "a_renouveler": sum(1 for x in lignes if x.etat.etat == etats.A_RENOUVELER),
        "expirees": sum(1 for x in lignes if x.etat.etat == etats.EXPIREE),
        "manquantes": sum(1 for x in lignes if x.etat.etat == etats.MANQUANTE and x.exigee),
        "a_traiter": sum(1 for x in lignes if x.alerte),
    }


def a_traiter() -> int:
    """Pour la pastille du menu et l'accueil : pièces expirées, à renouveler, ou manquantes
    alors qu'elles sont exigées."""
    return compteurs(registre())["a_traiter"]


# -- contrôle à une date (ADR 0010, § 6 ; AD07, étape 1) -------------------------------------
@dataclass
class LigneControle:
    """Une pièce demandée, la version qu'on joindrait et son état à la date limite de dépôt."""

    type: TypePiece
    version: PieceAdministrative | None
    etat: echeances.EtatPiece
    ajoutee: bool  # demandée en plus par l'avis (non exigée par défaut)
    demande: DemandeRenouvellement | None = None

    @property
    def cle_etat(self) -> str:
        return self.etat.etat.value

    @property
    def a_regler(self) -> bool:
        return self.etat.etat in (echeances.Etat.EXPIREE, echeances.Etat.MANQUANTE)

    @property
    def libelle_etat(self) -> str:
        e, j = self.etat.etat, self.etat.jours
        if e == echeances.Etat.EXPIREE:
            return f"périmée {-j} j avant le dépôt"
        if e == echeances.Etat.VALIDE:
            return "valide le jour du dépôt, pas au-delà" if j == 0 else f"valide · {j} j de marge"
        return LIBELLES.get(e.value, e.value)


def controle_a_la_date(date_limite: date, codes_en_plus: list[str] = ()) -> list[LigneControle]:
    """Les pièces exigées par défaut, plus celles que l'avis demande en plus, à `date_limite` :
    pour chacune, la version la plus récente déjà émise à cette date (hors versions retirées)
    et son état ce jour-là. Les pièces à régler d'abord (moteur.controle)."""
    types = {
        t.code: t
        for t in TypePiece.objects.filter(actif=True).order_by("ordre", "libelle")
        if t.exigee_par_defaut or t.code in codes_en_plus
    }
    versions: dict[str, list[PieceAdministrative]] = {code: [] for code in types}
    for v in PieceAdministrative.objects.filter(type__code__in=types, retiree=False):
        versions[v.type.code].append(v)
    par_pk = {v.pk: v for vs in versions.values() for v in vs}
    demandes = {
        d.type.code: d
        for d in DemandeRenouvellement.objects.filter(
            type__code__in=types, close_le=None
        ).select_related("type")
    }
    lignes = echeances.controle(
        list(types),
        {code: [v.pour_moteur() for v in vs] for code, vs in versions.items()},
        date_limite,
    )
    return [
        LigneControle(
            types[x.code],
            par_pk.get(x.version.ident) if x.version else None,
            x.etat,
            not types[x.code].exigee_par_defaut,
            demandes.get(x.code),
        )
        for x in lignes
    ]


def expirations_d_ici(date_limite: date, lignes: list[LigneControle]) -> list[LigneRegistre]:
    """Les versions valides aujourd'hui qui expirent avant la date limite : ce qu'il faut
    renouveler à temps, dans l'ordre des échéances."""
    aujourd_hui = timezone.localdate()
    en_cours = {x.type.pk: x for x in registre(aujourd_hui, types=[x.type for x in lignes])}
    resultat = [
        en_cours[x.type.pk]
        for x in lignes
        if en_cours[x.type.pk].version
        and en_cours[x.type.pk].version.valide_jusqu_au
        and aujourd_hui <= en_cours[x.type.pk].version.valide_jusqu_au < date_limite
    ]
    return sorted(resultat, key=lambda x: x.version.valide_jusqu_au)


# -- actions ----------------------------------------------------------------------------------
@transaction.atomic
def enregistrer_version(
    type_piece: TypePiece,
    fichier: FichierDuDossier,
    date_emission: date,
    valide_jusqu_au: date | None,
    numero: str,
    utilisateur,
) -> PieceAdministrative:
    """Enregistre un fichier « nouveau » du dossier comme nouvelle version. Le contenu est relu
    au moment d'enregistrer : un fichier changé entre-temps, ou devenu doublon, est refusé
    (ValueError). Clôt les demandes de renouvellement faites avant l'émission."""
    if not fichier.enregistrable:
        raise ValueError(f"« {fichier.nom} » ne peut pas être enregistré : {fichier.statut}")
    chemin = chemin_absolu(fichier.chemin)
    if not chemin.is_file() or empreinte(chemin) != fichier.empreinte:
        raise ValueError(f"« {fichier.nom} » a changé ou disparu : rechargez la page")
    if PieceAdministrative.objects.filter(empreinte=fichier.empreinte).exists():
        raise ValueError(f"« {fichier.nom} » est déjà enregistré")
    if valide_jusqu_au is not None and valide_jusqu_au < date_emission:
        raise ValueError("la fin de validité précède la date d'émission")
    if type_piece.regle_validite != TypePiece.Regle.PERMANENTE and valide_jusqu_au is None:
        raise ValueError("indiquez jusqu'à quand la pièce est valide")
    version = PieceAdministrative.objects.create(
        type=type_piece,
        chemin=fichier.chemin,
        empreinte=fichier.empreinte,
        taille=fichier.taille,
        nb_pages=fichier.nb_pages,
        numero=numero.strip(),
        date_emission=date_emission,
        valide_jusqu_au=valide_jusqu_au,
        deposee_par=utilisateur if getattr(utilisateur, "pk", None) else None,
    )
    DemandeRenouvellement.objects.filter(
        type=type_piece, close_le=None, demandee_le__lte=date_emission
    ).update(close_le=timezone.localdate())
    return version


MOTIF_NOUVEAU_SCAN = "remplacée par un nouveau scan du même document"


@transaction.atomic
def enregistrer_nouveau_scan(
    type_piece: TypePiece, fichier: FichierDuDossier, utilisateur
) -> PieceAdministrative:
    """Un meilleur scan du MÊME document que la version en cours (initiative du porteur,
    22/10/2026, séance de rescan) : nouvelle ligne avec les mêmes dates et le même numéro, qui
    devient la version en cours ; l'ancien scan est retiré avec un motif. Rien n'est effacé et
    l'historique distingue un rescan d'un renouvellement. Les demandes restent ouvertes."""
    courante = version_en_cours(list(PieceAdministrative.objects.filter(type=type_piece)))
    if courante is None:
        raise ValueError("aucune version en cours à remplacer : déposez une version normale")
    if not fichier.enregistrable:
        raise ValueError(f"« {fichier.nom} » ne peut pas être enregistré : {fichier.statut}")
    chemin = chemin_absolu(fichier.chemin)
    if not chemin.is_file() or empreinte(chemin) != fichier.empreinte:
        raise ValueError(f"« {fichier.nom} » a changé ou disparu : rechargez la page")
    version = PieceAdministrative.objects.create(
        type=type_piece,
        chemin=fichier.chemin,
        empreinte=fichier.empreinte,
        taille=fichier.taille,
        nb_pages=fichier.nb_pages,
        numero=courante.numero,
        date_emission=courante.date_emission,
        valide_jusqu_au=courante.valide_jusqu_au,
        deposee_par=utilisateur if getattr(utilisateur, "pk", None) else None,
    )
    retirer_version(courante, f"{MOTIF_NOUVEAU_SCAN} ({version.nom_fichier})")
    return version


def retirer_version(version: PieceAdministrative, motif: str) -> PieceAdministrative:
    motif = motif.strip()
    if not motif:
        raise ValueError("indiquez pourquoi la version est retirée")
    version.retiree, version.motif_retrait = True, motif[:300]
    version.save(update_fields=["retiree", "motif_retrait"])
    return version


def noter_demande(
    type_piece: TypePiece,
    demandee_le: date,
    aupres_de: str,
    relance_prevue_le: date | None,
    note: str,
    utilisateur,
) -> DemandeRenouvellement:
    if relance_prevue_le is not None and relance_prevue_le < demandee_le:
        raise ValueError("la relance précède la demande")
    return DemandeRenouvellement.objects.create(
        type=type_piece,
        demandee_le=demandee_le,
        aupres_de=aupres_de.strip()[:200] or type_piece.organisme[:200],
        relance_prevue_le=relance_prevue_le,
        note=note.strip()[:300],
        par=utilisateur if getattr(utilisateur, "pk", None) else None,
    )
