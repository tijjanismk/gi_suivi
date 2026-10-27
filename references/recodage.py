"""Recodage de références avant la production (ADR 0014 § 3).

Le seul endroit où un code change (règle 2 de `CONTEXT.md`) : une table « ancien → nouveau »
validée par le porteur, appliquée ici à la base et, à part, au partage par
`scripts\\exploitation\\Recoder-Missions.ps1` (l'application ne touche pas au partage, règle 4).
Pour chaque ligne : le code, le domaine principal et les domaines secondaires de la référence,
et le chemin de ses pièces rattachées. Rejouable : une ligne déjà faite est passée.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

from django.conf import settings
from django.db import transaction
from django.db.models import Q

from moteur.references.codes import decomposer
from references.models import Mission, PieceJustificative
from referentiel.models import Domaine
from suivi.models import JournalAcces

COLONNES = ("Ancien", "Nouveau", "Domaine", "Secondaires")
DOSSIER = "REFERENCES\\02_JUSTIFICATIFS\\"
RETIRES = ("AQA", "VRD")  # domaines supprimés dès qu'ils ne servent plus (ADR 0014 § 1)


class RecodageRefuseError(Exception):
    """Recodage interdit : en production, un code ne change plus (ADR 0008 § 6)."""


@dataclass(frozen=True)
class Ligne:
    ancien: str
    nouveau: str
    domaine: str
    secondaires: tuple[str, ...] = ()


@dataclass
class Rapport:
    faits: list[str] = field(default_factory=list)
    passes: list[str] = field(default_factory=list)
    erreurs: list[str] = field(default_factory=list)
    retires: list[str] = field(default_factory=list)

    @property
    def resume(self) -> str:
        return (
            f"{len(self.faits)} recodée(s), {len(self.passes)} déjà faite(s), "
            f"{len(self.erreurs)} erreur(s)"
        )


def lire_table(texte: str) -> list[Ligne]:
    """La table CSV « ; » (UTF-8, BOM toléré) : Ancien, Nouveau, Domaine, Secondaires."""
    lecteur = csv.DictReader(io.StringIO(texte.lstrip("﻿")), delimiter=";")
    manquantes = [c for c in COLONNES if c not in (lecteur.fieldnames or [])]
    if manquantes:
        raise ValueError(f"colonnes manquantes : {', '.join(manquantes)}")
    lignes = []
    for d in lecteur:
        secondaires = tuple(s.strip().upper() for s in d["Secondaires"].split(",") if s.strip())
        lignes.append(
            Ligne(
                d["Ancien"].strip().upper(),
                d["Nouveau"].strip().upper(),
                d["Domaine"].strip().upper(),
                secondaires,
            )
        )
    return lignes


def _erreur(ligne: Ligne, mission: Mission) -> str:
    """Ce qui empêche le recodage d'une ligne, ou une chaîne vide."""
    nouveau = decomposer(ligne.nouveau)
    if nouveau is None:
        return f"{ligne.nouveau} : code mal formé"
    if nouveau[0] != ligne.domaine:
        return f"{ligne.nouveau} : le code ne commence pas par le domaine {ligne.domaine}"
    if nouveau[1] != mission.nature:
        return f"{ligne.nouveau} : nature {nouveau[1]}, la référence est {mission.nature}"
    if Mission.objects.filter(code=ligne.nouveau).exists():
        return f"{ligne.nouveau} existe déjà"
    connus = set(Domaine.objects.values_list("code", flat=True))
    inconnus = sorted({ligne.domaine, *ligne.secondaires} - connus)
    if inconnus:
        return f"{ligne.ancien} : domaine inconnu {', '.join(inconnus)}"
    return ""


def _nouveau_chemin(chemin: str, ancien: str, nouveau: str) -> str:
    prefixe = f"{DOSSIER}{ancien}\\"
    if not chemin.startswith(prefixe):
        return chemin
    return f"{DOSSIER}{nouveau}\\" + chemin[len(prefixe) :]


@transaction.atomic
def recoder(lignes: list[Ligne], simuler: bool = False, par: str = "") -> Rapport:
    if settings.ENVIRONNEMENT == "prod":
        raise RecodageRefuseError("en production, un code ne change plus (ADR 0008 § 6)")
    rapport = Rapport()
    recodees = set()
    for ligne in lignes:
        m = Mission.objects.filter(code=ligne.ancien).first()
        if m is None:
            if Mission.objects.filter(code=ligne.nouveau).exists():
                rapport.passes.append(f"{ligne.ancien} : déjà {ligne.nouveau}")
            else:
                rapport.erreurs.append(f"{ligne.ancien} : référence introuvable")
            continue
        erreur = _erreur(ligne, m)
        if erreur:
            rapport.erreurs.append(erreur)
            continue
        recodees.add(m.pk)
        pieces = list(m.pieces.all())
        rapport.faits.append(f"{ligne.ancien} -> {ligne.nouveau} ({len(pieces)} pièce(s))")
        if simuler:
            continue
        domaine = Domaine.objects.get(code=ligne.domaine)
        # update() et non save() : Mission.save refuse tout changement de code (ADR 0008 § 2)
        Mission.objects.filter(pk=m.pk).update(code=ligne.nouveau, domaine=domaine)
        secondaires = Domaine.objects.filter(code__in=ligne.secondaires).exclude(pk=domaine.pk)
        m.domaines_secondaires.add(*secondaires)
        for p in pieces:
            chemin = _nouveau_chemin(p.chemin, ligne.ancien, ligne.nouveau)
            PieceJustificative.objects.filter(pk=p.pk).update(chemin=chemin)
        JournalAcces.objects.create(
            login=par[:150],
            action="reference:recodage",
            cible=f"{ligne.ancien} -> {ligne.nouveau}",
        )
    for d in Domaine.objects.filter(code__in=RETIRES):
        utilisees = Mission.objects.filter(Q(domaine=d) | Q(domaines_secondaires=d))
        if simuler:
            utilisees = utilisees.exclude(pk__in=recodees)
        if utilisees.exists() or d.experts.exists() or d.categories.exists():
            continue
        rapport.retires.append(d.code)
        if not simuler:
            d.delete()
    return rapport
