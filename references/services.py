"""Orchestration des références (ADR 0008) : paires suspectes, décision sur un doublon, import
de la liste maîtresse (chantier 2). La détection est dans `moteur.references.doublons`.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils.text import slugify

from moteur.references import doublons
from references.models import DecisionDoublon, Mission
from referentiel.models import Categorie, Client, Domaine

NATURES = {n.value for n in Mission.Nature}
_CODE = re.compile(r"^(?:GIC-)?([A-Z]{3})-(ETU|CTR|ETC)-\d+$")


# -- doublons ---------------------------------------------------------------------------------
def fiche(m: Mission) -> doublons.Fiche:
    return doublons.Fiche(
        ident=m.pk,
        code=m.code,
        intitule=m.intitule,
        client=m.client.nom if m.client else "",
        annee=m.annee,
        montant=m.montant,
        numero_contrat=m.numero_contrat,
        nature=m.nature,
    )


def paires_a_arbitrer() -> list[doublons.Paire]:
    """Les paires suspectes entre références non absorbées, hors paires déjà tranchées."""
    missions = Mission.objects.filter(absorbee_par=None).select_related("client")
    tranchees = frozenset(DecisionDoublon.objects.values_list("mission_a_id", "mission_b_id"))
    return doublons.paires_suspectes((fiche(m) for m in missions), tranchees)


@transaction.atomic
def trancher(
    a: Mission,
    b: Mission,
    meme_contrat: bool,
    gardee: Mission | None,
    utilisateur,
    raisons: str = "",
    note: str = "",
) -> DecisionDoublon:
    """Enregistre la décision. Même contrat : l'autre fiche est absorbée par `gardee` (jamais
    supprimée), ses domaines passent en domaines secondaires du code gardé, la nature devient
    ETC si l'une était une étude et l'autre un contrôle, et les fiches qu'elle absorbait
    rejoignent le code gardé."""
    a, b = sorted((a, b), key=lambda m: m.pk)
    if DecisionDoublon.objects.filter(mission_a=a, mission_b=b).exists():
        raise ValueError(f"la paire {a.code} / {b.code} est déjà tranchée")
    if a.absorbee_par_id or b.absorbee_par_id:
        raise ValueError("l'une des deux références est déjà absorbée par une autre")
    if meme_contrat:
        if gardee is None or gardee.pk not in (a.pk, b.pk):
            raise ValueError("choisissez le code à garder parmi les deux")
        absorbee = b if gardee.pk == a.pk else a
        gardee.nature = doublons.nature_fusionnee(gardee.nature, absorbee.nature)
        gardee.save(update_fields=["nature", "modifie_le"])
        secondaires = {
            absorbee.domaine_id,
            *absorbee.domaines_secondaires.values_list("pk", flat=True),
        }
        secondaires.discard(gardee.domaine_id)
        gardee.domaines_secondaires.add(*secondaires)
        Mission.objects.filter(absorbee_par=absorbee).update(absorbee_par=gardee)
        absorbee.absorbee_par = gardee
        absorbee.save(update_fields=["absorbee_par", "modifie_le"])
    return DecisionDoublon.objects.create(
        mission_a=a,
        mission_b=b,
        meme_contrat=meme_contrat,
        gardee=gardee if meme_contrat else None,
        raisons=raisons[:300],
        note=note.strip()[:300],
        par=utilisateur if getattr(utilisateur, "pk", None) else None,
    )


# -- import de la liste maîtresse (chantier 2) ------------------------------------------------
COLONNES = (
    "code",
    "statut_code",
    "absorbe_par",
    "intitule_court",
    "client",
    "annee",
    "nature",
    "categorie",
    "montant",
    "source_word",
    "numero_source",
    "observations",
)
OBLIGATOIRES = ("code", "intitule_court")


@dataclass
class Rapport:
    creees: list[str] = field(default_factory=list)
    mises_a_jour: list[str] = field(default_factory=list)
    absorbees: list[str] = field(default_factory=list)
    erreurs: list[str] = field(default_factory=list)

    @property
    def resume(self) -> str:
        return (
            f"{len(self.creees)} créée(s), {len(self.mises_a_jour)} mise(s) à jour, "
            f"{len(self.absorbees)} absorbée(s), {len(self.erreurs)} erreur(s)"
        )


def lire_csv(contenu: str) -> list[dict[str, str]]:
    """CSV de l'onglet Missions, séparé par « ; » (Excel en français) ou « , ». En-têtes en
    minuscules, sans espaces autour ; ValueError si une colonne obligatoire manque."""
    contenu = contenu.lstrip("﻿")
    premiere = contenu.splitlines()[0] if contenu.strip() else ""
    separateur = ";" if premiere.count(";") >= premiere.count(",") else ","
    lecteur = csv.DictReader(io.StringIO(contenu), delimiter=separateur)
    if not lecteur.fieldnames:
        raise ValueError("fichier vide")
    lecteur.fieldnames = [slugify(n).replace("-", "_") for n in lecteur.fieldnames]
    manquantes = [c for c in OBLIGATOIRES if c not in lecteur.fieldnames]
    if manquantes:
        raise ValueError(f"colonnes manquantes : {', '.join(manquantes)}")
    return [{k: (v or "").strip() for k, v in ligne.items() if k} for ligne in lecteur]


_DEVISES = re.compile(r"\b(?:f\s*cfa|fcfa|cfa|xof|eur|euros?|f)\b|€", re.IGNORECASE)


def _montant(texte: str) -> Decimal | None:
    """« 45 000 000 », « 45000000,50 », « 45 000 000 FCFA » → Decimal ; vide → None.
    ValueError si le texte contient autre chose qu'un nombre et une devise."""
    t = _DEVISES.sub("", texte.replace("\u202f", " ").replace("\xa0", " ")).strip()
    if not t:
        return None
    if re.search(r"[^\d\s,.]", t):
        raise ValueError(f"montant illisible : {texte}")
    t = re.sub(r"\s", "", t)
    if "," in t and "." in t:
        t = t.replace(".", "").replace(",", ".")
    elif "," in t:
        t = t.replace(",", ".")
    try:
        return Decimal(t)
    except InvalidOperation as e:
        raise ValueError(f"montant illisible : {texte}") from e


def _client(nom: str) -> Client | None:
    if not nom:
        return None
    existant = (
        Client.objects.filter(nom__iexact=nom).first()
        or Client.objects.filter(sigle__iexact=nom).first()
    )
    return existant or Client.objects.create(nom=nom[:200])


def _categorie(libelle: str, domaine: Domaine) -> Categorie | None:
    if not libelle:
        return None
    cle = slugify(libelle)[:80] or None
    if cle is None:
        return None
    return Categorie.objects.get_or_create(
        cle=cle, defaults={"libelle": libelle[:150], "domaine": domaine}
    )[0]


@transaction.atomic
def importer(lignes: list[dict[str, str]], simuler: bool = False) -> Rapport:
    """Importe la liste maîtresse. Idempotent par code ; un code existant n'est jamais changé ;
    une mission créée est « importée » (sa vérification reste humaine, règle 3) ; une mission
    déjà vérifiée garde ce statut. `absorbe_par` est résolu après toutes les lignes.
    En simulation, rien n'est gardé."""
    rapport = Rapport()
    domaines = {d.code: d for d in Domaine.objects.all()}
    absorptions: list[tuple[int, str, str]] = []
    for n, ligne in enumerate(lignes, start=2):  # ligne 1 = en-têtes
        code = ligne.get("code", "").upper()
        m = _CODE.match(code)
        if not m:
            rapport.erreurs.append(f"ligne {n} : code « {code} » invalide (GIC-HYD-ETU-043)")
            continue
        domaine = domaines.get(m.group(1))
        if domaine is None:
            rapport.erreurs.append(f"ligne {n} : domaine « {m.group(1)} » inconnu")
            continue
        nature = (ligne.get("nature") or m.group(2)).upper()
        if nature not in NATURES:
            rapport.erreurs.append(f"ligne {n} : nature « {nature} » inconnue (ETU, CTR, ETC)")
            continue
        try:
            montant = _montant(ligne.get("montant", ""))
            annee = int(ligne["annee"]) if ligne.get("annee") else None
        except ValueError as e:
            rapport.erreurs.append(f"ligne {n} : {e}")
            continue
        valeurs = {
            "domaine": domaine,
            "nature": nature,
            "intitule": ligne["intitule_court"],
            "intitule_court": ligne["intitule_court"][:300],
            "client": _client(ligne.get("client", "")),
            "categorie": _categorie(ligne.get("categorie", ""), domaine),
            "annee": annee,
            "montant": montant,
            "statut_code": "nouveau"
            if ligne.get("statut_code", "").lower() == "nouveau"
            else "existant",
            "source_word": ligne.get("source_word", "")[:300],
            "numero_source": ligne.get("numero_source", "")[:50],
            "observations": ligne.get("observations", ""),
        }
        mission = Mission.objects.filter(code=code).first()
        if mission is None:
            mission = Mission.objects.create(code=code, **valeurs)
            rapport.creees.append(code)
        elif mission.statut_verification == Mission.Verification.VERIFIEE:
            rapport.erreurs.append(f"ligne {n} : {code} déjà vérifiée, laissée telle quelle")
        else:
            if mission.intitule != mission.intitule_court:
                del valeurs["intitule"]  # un intitulé complet saisi à la main est gardé
            for cle, valeur in valeurs.items():
                setattr(mission, cle, valeur)
            mission.save()
            rapport.mises_a_jour.append(code)
        statut = ligne.get("statut_code", "").lower()
        if ligne.get("absorbe_par") or statut.startswith("absorb"):
            absorptions.append((n, code, ligne.get("absorbe_par", "").upper()))
    for n, code, par in absorptions:
        gardee = Mission.objects.filter(code=par).first() if par else None
        if gardee is None or gardee.code == code:
            rapport.erreurs.append(f"ligne {n} : {code} absorbée par « {par} », introuvable")
            continue
        Mission.objects.filter(code=code).update(absorbee_par=gardee)
        rapport.absorbees.append(f"{code} → {gardee.code}")
    if simuler:
        transaction.set_rollback(True)
    return rapport
