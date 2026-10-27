"""Justificatifs d'un expert (chantier 5, ADR 0012) : les fichiers de son dossier
EXPERTS\\<NOM Prénom> sur le partage — CV, diplômes, attestations. Lus, jamais écrits (règle 4),
avec les fonctions de lecture des pièces administratives (ADR 0010)."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from administratif.services import PartageIndisponibleError, chemin_absolu, relatif
from experts.models import Diplome, Expert
from moteur.suivi.classement import est_technique

TYPES = (("cv", "CV"), ("diplome", "diplôme"), ("attestation", "attestation"), ("autre", "autre"))
_ORDRE = {t: i for i, (t, _) in enumerate(TYPES)}
_LIBELLES = dict(TYPES)
_DIPLOME = (
    "diplom", "bachelor", "master", "licence", "bts", "dut", "bt2", "brevet", "baccalaureat",
    "ingenieur d'etat", "attestation de reussite", "attestation de succes", "releve de notes",
)  # fmt: skip


def _simple(texte: str) -> str:
    sans_accents = unicodedata.normalize("NFD", texte.lower())
    return "".join(c for c in sans_accents if unicodedata.category(c) != "Mn")


def type_de(nom: str) -> str:
    """D'après le nom du fichier : CV, diplôme, attestation (de travail, de disponibilité), autre.
    Une « attestation de réussite » est un diplôme."""
    n = _simple(Path(nom).stem).replace("_", " ").replace("-", " ")
    if re.search(r"\bc ?v\b", n) or "curriculum" in n:  # « CV », « C_V »
        return "cv"
    if any(m in n for m in _DIPLOME):
        return "diplome"
    if "attestation" in n or "certificat" in n or "disponibilite" in n:
        return "attestation"
    return "autre"


@dataclass
class FichierExpert:
    nom: str
    chemin: str  # relatif au partage
    dans_dossier: str  # relatif au dossier de l'expert : ce qu'on passe pour l'ouvrir
    type: str
    taille: int
    diplome: Diplome | None = None

    @property
    def libelle_type(self) -> str:
        return _LIBELLES[self.type]

    @property
    def sous_dossier(self) -> str:
        return self.dans_dossier.rpartition("\\")[0]


def dossier(expert: Expert) -> Path | None:
    """Le dossier de l'expert sur ce système ; None s'il n'en a pas. PartageIndisponibleError si
    le partage n'est pas configuré ou si le dossier n'existe pas."""
    if not expert.dossier:
        return None
    d = chemin_absolu(expert.dossier)
    if not d.is_dir():
        raise PartageIndisponibleError(f"dossier introuvable sur le partage : {expert.dossier}")
    return d


def fichiers(expert: Expert) -> list[FichierExpert]:
    """Les fichiers du dossier et de ses sous-dossiers, CV d'abord, puis diplômes, attestations,
    autres ; chacun avec le diplôme enregistré qui le cite comme justificatif."""
    d = dossier(expert)
    if d is None:
        return []
    diplomes = {x.justificatif.lower(): x for x in expert.diplomes.exclude(justificatif="")}
    lus = []
    for p in d.rglob("*"):
        if not p.is_file() or est_technique(p.name):
            continue
        chemin = relatif(p)
        lus.append(
            FichierExpert(
                nom=p.name,
                chemin=chemin,
                dans_dossier="\\".join(p.relative_to(d).parts),
                type=type_de(p.name),
                taille=p.stat().st_size,
                diplome=diplomes.get(chemin.lower()),
            )
        )
    return sorted(lus, key=lambda f: (_ORDRE[f.type], f.dans_dossier.lower()))


def chemin_du_fichier(expert: Expert, dans_dossier: str) -> Path:
    """Le fichier `dans_dossier` du dossier de l'expert, pour l'ouvrir. ValueError si le chemin
    sort du dossier (`..`, lecteur) ; PartageIndisponibleError si le fichier n'existe pas."""
    d = dossier(expert)
    if d is None or not dans_dossier:
        raise PartageIndisponibleError("pas de dossier pour cet expert")
    p = chemin_absolu(f"{expert.dossier}\\{dans_dossier}")  # refuse « .. » et « C: »
    if not p.is_file() or est_technique(p.name):
        raise PartageIndisponibleError(f"fichier introuvable : {dans_dossier}")
    return p
