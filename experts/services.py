"""Orchestration du vivier (ADR 0012) : alertes d'une fiche, import du registre du chantier 5."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from experts.models import Diplome, Expert
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


@dataclass
class RapportDiplomes:
    crees: list[str] = field(default_factory=list)
    deja: list[str] = field(default_factory=list)
    erreurs: list[str] = field(default_factory=list)

    @property
    def resume(self) -> str:
        return (
            f"{len(self.crees)} diplôme(s) créé(s), {len(self.deja)} déjà enregistré(s), "
            f"{len(self.erreurs)} erreur(s)"
        )


@transaction.atomic
def importer_diplomes(lignes: list[dict[str, str]], simuler: bool = False) -> RapportDiplomes:
    """Diplômes lus sur les scans des dossiers (chantier 5) : colonnes `dossier` (« NOM Prénom »),
    `fichier` (le scan dans ce dossier, qui devient le justificatif), `intitule`, `etablissement`,
    `pays`, `annee`, `niveau`. L'expert doit déjà être au vivier. Un diplôme déjà enregistré avec
    le même justificatif (ou, sans fichier, le même intitulé et la même année) est sauté. En
    simulation, rien n'est gardé."""
    rapport = RapportDiplomes()
    for n, ligne in enumerate(lignes, start=2):
        dossier, fichier = ligne.get("dossier", ""), ligne.get("fichier", "")
        intitule, annee = ligne.get("intitule", "")[:250], ligne.get("annee", "")
        niveau = ligne.get("niveau", "")
        expert = Expert.objects.filter(dossier__iexact=f"EXPERTS\\{dossier}").first()
        if expert is None:
            rapport.erreurs.append(f"ligne {n} : expert inconnu au vivier ({dossier})")
            continue
        if not intitule or (annee and not annee.isdigit()) or niveau not in ("", *Diplome.Niveau):
            rapport.erreurs.append(f"ligne {n} ({dossier}) : intitulé, année ou niveau illisible")
            continue
        justificatif = f"EXPERTS\\{dossier}\\{fichier}"[:500] if fichier else ""
        if justificatif:
            memes = expert.diplomes.filter(justificatif=justificatif)
        else:
            memes = expert.diplomes.filter(intitule=intitule, annee=int(annee) if annee else None)
        if memes.exists():
            rapport.deja.append(f"{dossier} : {intitule}")
            continue
        Diplome.objects.create(
            expert=expert,
            intitule=intitule,
            etablissement=ligne.get("etablissement", "")[:200],
            pays=ligne.get("pays", "")[:80],
            annee=int(annee) if annee else None,
            niveau=niveau,
            justificatif=justificatif,
        )
        rapport.crees.append(f"{dossier} : {intitule}")
    if simuler:
        transaction.set_rollback(True)
    return rapport