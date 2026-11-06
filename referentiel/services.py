"""Termes des types d'ouvrages par pays (ADR 0019) : ce que l'administration, la commande
d'import et les outils MCP appellent. Un terme venu d'une machine entre proposé ; une personne
le valide ou le rejette (règle 3 de `CONTEXT.md`). La comparaison des textes reste dans
`moteur/`."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone
from django.utils.text import slugify

from moteur.references.doublons import normaliser
from referentiel.models import PAYS_BUREAU, Terme, TypeOuvrage

_PAYS = {normaliser(p): p for p in PAYS_BUREAU}


def pays_du_bureau(texte: str) -> str:
    """« guinee », « Guinée » → « Guinée » ; vide → vide (tous les pays) ; ValueError sinon."""
    if not (texte or "").strip():
        return ""
    pays = _PAYS.get(normaliser(texte))
    if pays is None:
        raise ValueError(f"pays hors de la liste du bureau : {texte} ({', '.join(PAYS_BUREAU)})")
    return pays


def termes_valides(
    type_ouvrage: TypeOuvrage | None = None, *, pays: str | None = None, pour_avis: bool = False
) -> QuerySet[Terme]:
    """Les termes qui servent. `pays` : None pour tous, sinon les termes sans pays et ceux de ce
    pays. `pour_avis` : seulement ceux de portée « partout » (PPM, réservé aux références du
    bureau, ne sert pas à lire un avis)."""
    qs = Terme.objects.filter(statut=Terme.Statut.VALIDE)
    if type_ouvrage is not None:
        qs = qs.filter(type_ouvrage=type_ouvrage)
    if pays is not None:
        qs = qs.filter(Q(pays="") | Q(pays=pays))
    if pour_avis:
        qs = qs.filter(portee=Terme.Portee.PARTOUT)
    return qs


def _type(type_ouvrage: TypeOuvrage | str) -> TypeOuvrage:
    if isinstance(type_ouvrage, TypeOuvrage):
        return type_ouvrage
    try:
        return TypeOuvrage.objects.get(cle=(type_ouvrage or "").strip(), actif=True)
    except TypeOuvrage.DoesNotExist as e:
        raise ValueError(f"type d'ouvrage inconnu : {type_ouvrage}") from e


def proposer(
    type_ouvrage: TypeOuvrage | str,
    terme: str,
    *,
    origine: str,
    pays: str = "",
    portee: str = Terme.Portee.PARTOUT,
    source_url: str = "",
    nb_avis: int | None = None,
    par: str = "",
) -> tuple[Terme, bool]:
    """Un terme proposé, à valider. S'il existe déjà pour ce type et ce pays, il est rendu tel
    quel (rien n'est changé) avec `False`."""
    terme = (terme or "").strip()
    if not terme:
        raise ValueError("terme vide")
    if portee not in Terme.Portee.values:
        raise ValueError(f"portée inconnue : {portee} ({', '.join(Terme.Portee.values)})")
    if origine not in Terme.Origine.values:
        raise ValueError(f"origine inconnue : {origine}")
    o, pays = _type(type_ouvrage), pays_du_bureau(pays)
    existant = Terme.objects.filter(type_ouvrage=o, cle=normaliser(terme), pays=pays).first()
    if existant is not None:
        return existant, False
    t = Terme.objects.create(
        type_ouvrage=o,
        terme=terme[:120],
        pays=pays,
        portee=portee,
        origine=origine,
        source_url=(source_url or "")[:500] if (source_url or "").startswith("http") else "",
        nb_avis=nb_avis,
        propose_par=(par or "")[:150],
    )
    return t, True


def valider(t: Terme, par) -> None:
    t.statut = Terme.Statut.VALIDE
    t.decide_par = par
    t.decide_le = timezone.now()
    t.save()


def rejeter(t: Terme, motif: str, par) -> None:
    if not (motif or "").strip():
        raise ValueError("indiquez le motif du rejet")
    t.statut = Terme.Statut.REJETE
    t.motif = motif.strip()[:500]
    t.decide_par = par
    t.decide_le = timezone.now()
    t.save()


# -- import des décisions du porteur (synonymes-a-valider.csv, collecte du 06/11/2026) ----------
OBLIGATOIRES = ("type_ouvrage", "synonyme")


def lire_csv(contenu: str) -> list[dict[str, str]]:
    """Le fichier de la collecte, séparé par « ; » (Excel en français) ou « , ». En-têtes
    ramenés en minuscules sans accents (« decision (oui / non / autre type) » →
    `decision_oui_non_autre_type`) ; ValueError si une colonne obligatoire manque."""
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
    if not any(n.startswith("decision") for n in lecteur.fieldnames):
        raise ValueError("colonne « decision » manquante")
    return [{k: (v or "").strip() for k, v in ligne.items() if k} for ligne in lecteur]


@dataclass
class Rapport:
    valides: int = 0
    rejetes: int = 0
    deja: int = 0
    sans_decision: int = 0
    types_a_creer: list[str] = field(default_factory=list)
    conflits: list[str] = field(default_factory=list)
    erreurs: list[str] = field(default_factory=list)

    @property
    def resume(self) -> str:
        return (
            f"{self.valides} validé(s), {self.rejetes} rejeté(s), {self.deja} déjà là, "
            f"{self.sans_decision} sans décision, {len(self.types_a_creer)} type(s) à créer, "
            f"{len(self.conflits)} conflit(s), {len(self.erreurs)} erreur(s)"
        )


def _entier(texte: str) -> int | None:
    try:
        return int(texte)
    except (TypeError, ValueError):
        return None


def _decision(ligne: dict[str, str]) -> str:
    for k, v in ligne.items():
        if k.startswith("decision"):
            return v
    return ""


def importer_decisions(
    lignes: list[dict[str, str]], par, *, source: str = "", simuler: bool = False
) -> Rapport:
    """Chaque ligne décidée par le porteur devient un terme : « oui » validé sous le type de la
    ligne, une clé de type (`aep`) validé sous ce type, « non » rejeté. Colonnes facultatives :
    `pays_propose` (un ou plusieurs pays séparés par des virgules ; vide = tous), `portee_proposee`
    (partout / references), `exemple` (un lien d'avis), `nb_avis` et `nb_avis_api_bm`. Un type
    « nouveau: … » n'est jamais créé ici : il est signalé. Un terme déjà décidé autrement n'est pas
    changé : il est signalé en conflit."""
    rapport = Rapport()
    with transaction.atomic():
        for n, ligne in enumerate(lignes, start=2):
            terme, type_ligne = ligne.get("synonyme", ""), ligne.get("type_ouvrage", "")
            brute = _decision(ligne).strip()
            decision = normaliser(brute)
            if not decision:
                rapport.sans_decision += 1
                continue
            if decision == "non":
                statut, cle_type = Terme.Statut.REJETE, type_ligne
            elif decision == "oui":
                statut, cle_type = Terme.Statut.VALIDE, type_ligne
            else:  # une autre clé de type : « aep », « autre type : bas-fond »
                statut, cle_type = Terme.Statut.VALIDE, brute.split(":")[-1].strip().lower()
            if cle_type.lower().startswith("nouveau"):
                if statut == Terme.Statut.VALIDE:
                    rapport.types_a_creer.append(f"ligne {n} : {terme} → {cle_type}")
                continue
            try:
                o = _type(cle_type)
                pays = [pays_du_bureau(p) for p in ligne.get("pays_propose", "").split(",")]
            except ValueError as e:
                rapport.erreurs.append(f"ligne {n} : {terme} : {e}")
                continue
            portee = ligne.get("portee_proposee") or Terme.Portee.PARTOUT
            comptes = [_entier(ligne.get(c, "")) for c in ("nb_avis", "nb_avis_api_bm")]
            nb = max((x for x in comptes if x is not None), default=None)
            for p in sorted(set(pays)):
                try:
                    t, cree = proposer(
                        o,
                        terme,
                        origine=Terme.Origine.COLLECTE,
                        pays=p,
                        portee=portee,
                        source_url=ligne.get("exemple", ""),
                        nb_avis=nb,
                        par=source,
                    )
                except ValueError as e:
                    rapport.erreurs.append(f"ligne {n} : {terme} : {e}")
                    continue
                if not cree and t.statut != Terme.Statut.PROPOSE:
                    if t.statut == statut:
                        rapport.deja += 1
                    else:
                        rapport.conflits.append(
                            f"ligne {n} : {t} ({o.cle}) déjà {t.get_statut_display()}"
                        )
                    continue
                if statut == Terme.Statut.VALIDE:
                    valider(t, par)
                    rapport.valides += 1
                else:
                    rejeter(t, f"refusé dans {source or 'le fichier de la collecte'}", par)
                    rapport.rejetes += 1
        if simuler:
            transaction.set_rollback(True)
    return rapport
