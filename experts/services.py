"""Orchestration du vivier (ADR 0012) : alertes d'une fiche, import du registre du chantier 5."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from experts.models import Expert
from moteur.experts import controles

CATEGORIES = {
    "ingenieur": "ingenieur",
    "ingenieurs": "ingenieur",
    "technicien-superieur": "technicien_superieur",
    "techniciens-superieurs": "technicien_superieur",
    "technicien": "technicien",
    "techniciens": "technicien",
}


def alertes(expert: Expert) -> list[controles.Alerte]:
    periodes = [
        controles.Periode(a.pk, f"{a.mission.code} ({a.poste})", a.du, a.au, a.plein_temps)
        for a in expert.affectations.select_related("mission")
    ]
    return controles.alertes(periodes, timezone.localdate())


def annees(expert: Expert) -> int | None:
    return controles.annees_experience(expert.debut_carriere, timezone.localdate())


@dataclass
class Rapport:
    crees: list[str] = field(default_factory=list)
    mis_a_jour: list[str] = field(default_factory=list)
    erreurs: list[str] = field(default_factory=list)

    @property
    def resume(self) -> str:
        return (
            f"{len(self.crees)} créé(s), {len(self.mis_a_jour)} mis à jour, "
            f"{len(self.erreurs)} erreur(s)"
        )


def separer_nom(texte: str) -> tuple[str, str]:
    """« TRAORÉ Awa Mariam » (dossier du chantier 5) → (« TRAORÉ », « Awa Mariam ») : le nom
    est la suite de mots en majuscules du début."""
    mots = texte.split()
    nom = [m for m in _tant_que(mots, lambda m: m.isupper() or not any(c.isalpha() for c in m))]
    if not nom:
        nom = mots[:1]
    return " ".join(nom), " ".join(mots[len(nom) :])


def _tant_que(mots, condition):
    for m in mots:
        if not condition(m):
            return
        yield m


def lire_csv(contenu: str) -> list[dict[str, str]]:
    """Registre `EXPERTS\\_registre\\experts.csv` : séparateur « ; » ou « , », en-têtes sans
    accents ni majuscules. Une colonne `dossier` (« NOM Prénom »), ou `nom` et `prenoms`."""
    contenu = contenu.lstrip("﻿")
    premiere = contenu.splitlines()[0] if contenu.strip() else ""
    if not premiere:
        raise ValueError("fichier vide")
    separateur = ";" if premiere.count(";") >= premiere.count(",") else ","
    lecteur = csv.DictReader(io.StringIO(contenu), delimiter=separateur)
    lecteur.fieldnames = [slugify(n).replace("-", "_") for n in lecteur.fieldnames or []]
    if "dossier" not in lecteur.fieldnames and "nom" not in lecteur.fieldnames:
        raise ValueError("colonne « dossier » ou « nom » attendue")
    return [{k: (v or "").strip() for k, v in ligne.items() if k} for ligne in lecteur]


@transaction.atomic
def importer(lignes: list[dict[str, str]], simuler: bool = False) -> Rapport:
    """Crée ou met à jour les experts du registre (nom et prénoms). Actif = non : ancien, non
    disponible. Les affectations ne viennent pas du registre : elles se saisissent avec leur
    preuve. En simulation, rien n'est gardé."""
    rapport = Rapport()
    for n, ligne in enumerate(lignes, start=2):
        if ligne.get("nom"):
            nom, prenoms = ligne["nom"], ligne.get("prenoms", "")
        else:
            nom, prenoms = separer_nom(ligne.get("dossier", ""))
        if not nom:
            rapport.erreurs.append(f"ligne {n} : nom vide")
            continue
        actif = ligne.get("actif", "oui").lower() not in ("non", "n", "0", "false")
        valeurs = {
            "specialite": ligne.get("specialite", "")[:200],
            "categorie": CATEGORIES.get(slugify(ligne.get("categorie", "")), ""),
            "dossier": (f"EXPERTS\\{ligne['dossier']}" if ligne.get("dossier") else "")[:300],
        }
        if not actif:
            valeurs.update(statut=Expert.Statut.ANCIEN, disponible=False)
        expert = Expert.objects.filter(nom__iexact=nom, prenoms__iexact=prenoms).first()
        if expert is None:
            Expert.objects.create(nom=nom[:100], prenoms=prenoms[:150], **valeurs)
            rapport.crees.append(f"{nom} {prenoms}".strip())
        else:
            for cle, valeur in valeurs.items():
                if valeur or cle in ("statut", "disponible"):
                    setattr(expert, cle, valeur)
            expert.save()
            rapport.mis_a_jour.append(str(expert))
    if simuler:
        transaction.set_rollback(True)
    return rapport
