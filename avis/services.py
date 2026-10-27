"""Services du module avis (ADR 0013) : les références du bureau telles que le moteur les voit,
l'aperçu d'un critère, le filtre dit en clair, les pièces exigées. Les vues (et plus tard les
outils MCP) passent par ici ; le calcul reste dans `moteur/avis/`."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from urllib.parse import urlencode

from django.db import transaction
from django.utils import timezone

from administratif.models import TypePiece
from administratif.services import LigneControle, controle_a_la_date
from avis.models import Avis, Critere, PieceExigee, Selection
from moteur.avis import notation
from moteur.avis.filtres import PIECES_PAR_DEFAUT, Piece, Preuve, Reference, lire_filtre
from moteur.avis.selection import selectionner
from references.models import Mission

CODES_EN_APERCU = 10
NATURES = {"ETU": "études", "CTR": "contrôle", "ETC": "études et contrôle"}
ROLES = {"seul": "seul", "chef_de_file": "chef de file", "membre": "membre d'un groupement"}


def _noms(organisme) -> frozenset[str]:
    if organisme is None:
        return frozenset()
    return frozenset(t for t in (organisme.nom, organisme.sigle) if t)


def _reference(m: Mission) -> Reference:
    ouvrages = list(m.types_ouvrage.all())
    return Reference(
        ident=m.pk,
        code=m.code,
        intitule=f"{m.intitule} {m.intitule_court}",
        nature=m.nature,
        domaines=frozenset({m.domaine.code, *(d.code for d in m.domaines_secondaires.all())}),
        role=m.role,
        annee=m.annee,
        pays=m.pays,
        clients=_noms(m.client),
        bailleurs=_noms(m.bailleur),
        categorie=m.categorie.cle if m.categorie else "",
        types_ouvrage=frozenset(t.cle for t in ouvrages),
        familles_ouvrage=frozenset(t.famille for t in ouvrages if t.famille),
        quantites={q.type.cle: q.valeur for q in m.quantites.all()},
        # « à auditer » comme sur l'écran des justificatifs : lisibilité ou cohérence non lue
        pieces=tuple(
            Piece(p.type, p.nature_exacte, bool(p.lisible and p.coherente), p.bonne)
            for p in m.pieces.all()
        ),
        absorbee=m.absorbee_par_id is not None,
    )


def references_du_bureau() -> list[Reference]:
    """Toutes les références, avec leurs domaines, pièces, quantités et types d'ouvrage."""
    missions = Mission.objects.select_related("domaine", "client", "bailleur", "categorie")
    missions = missions.prefetch_related(
        "domaines_secondaires", "pieces", "quantites__type", "types_ouvrage"
    )
    return [_reference(m) for m in missions]


@dataclass(frozen=True)
class Apercu:
    """Ce qu'un filtre retient, sans rien enregistrer."""

    total: int
    prouvees: int
    a_auditer: int
    manquantes: int
    codes: tuple[str, ...]  # les premières, dans l'ordre du classement


def apercu(filtre: dict, references: list[Reference] | None = None) -> Apercu:
    """Les références qu'un filtre retient. Lève `FiltreInvalideError` si le filtre ne se lit
    pas. `references` : la liste déjà lue, pour éviter de la relire à chaque critère."""
    if references is None:
        references = references_du_bureau()
    candidates = selectionner(lire_filtre(filtre), references)
    compte = Counter(c.preuve for c in candidates)
    return Apercu(
        total=len(candidates),
        prouvees=compte[Preuve.PROUVEE],
        a_auditer=compte[Preuve.A_AUDITER],
        manquantes=compte[Preuve.MANQUANTE],
        codes=tuple(c.reference.code for c in candidates[:CODES_EN_APERCU]),
    )


def _liste(valeurs: Iterable[str], noms: dict[str, str] | None = None) -> str:
    return ", ".join(noms.get(v, v) if noms else v for v in valeurs)


def filtre_en_clair(filtre: dict) -> list[str]:
    """Le filtre d'un critère, une condition par élément, pour la fiche de l'avis."""
    f = filtre or {}
    morceaux = []
    if f.get("natures"):
        morceaux.append(_liste(f["natures"], NATURES))
    if f.get("domaines"):
        morceaux.append("domaines " + _liste(f["domaines"]))
    if f.get("roles"):
        morceaux.append("rôle " + _liste(f["roles"], ROLES))
    if f.get("types_ouvrage") or f.get("familles_ouvrage"):
        ouvrages = [*f.get("types_ouvrage", []), *f.get("familles_ouvrage", [])]
        morceaux.append("ouvrages : " + _liste(ouvrages))
    if f.get("annee_min") and f.get("annee_max"):
        morceaux.append(f"de {f['annee_min']} à {f['annee_max']}")
    elif f.get("annee_min"):
        morceaux.append(f"depuis {f['annee_min']}")
    elif f.get("annee_max"):
        morceaux.append(f"jusqu'en {f['annee_max']}")
    for cle, libelle in (("pays", "pays"), ("clients", "clients"), ("bailleurs", "bailleurs")):
        if f.get(cle):
            morceaux.append(f"{libelle} : {_liste(f[cle])}")
    for cle, minimum in (f.get("quantites_min") or {}).items():
        morceaux.append(f"{cle} ≥ {minimum}")
    if f.get("mots_cles"):
        morceaux.append("mots-clés : " + _liste(f["mots_cles"]))
    if f.get("pieces_completes_requises") is False:
        morceaux.append("sans justificatif exigé")
    elif f.get("pieces_requises"):
        exigees = [
            e.replace("deuxieme_page", "2e page du contrat").replace("|", " ou ").replace("_", " ")
            for e in f["pieces_requises"]
        ]
        morceaux.append("prouvée par : " + _liste(exigees))
    else:
        morceaux.append("prouvée par : " + _liste(sorted(v)[0] for v in PIECES_PAR_DEFAUT))
    return morceaux


def regler_pieces(avis: Avis, codes: Iterable[str]) -> tuple[int, int]:
    """Les pièces exigées de l'avis deviennent exactement celles cochées. Une pièce ajoutée est
    « demandée par l'avis » ; une pièce reprise par défaut garde son origine. Rend (ajoutées,
    retirées)."""
    voulues = set(TypePiece.objects.filter(code__in=list(codes)).values_list("pk", flat=True))
    actuelles = set(avis.pieces_exigees.values_list("type_id", flat=True))
    PieceExigee.objects.bulk_create(
        PieceExigee(avis=avis, type_id=t, origine=PieceExigee.Origine.AVIS)
        for t in voulues - actuelles
    )
    retirees, _ = avis.pieces_exigees.filter(type_id__in=actuelles - voulues).delete()
    return len(voulues - actuelles), retirees


# -- simulation (AV04) --------------------------------------------------------------------------
def critere_moteur(c: Critere) -> notation.Critere:
    """Un critère enregistré, tel que le moteur le calcule."""
    return notation.Critere(
        code=c.code,
        mode=c.mode,
        plafond=c.plafond,
        points_par_mission=c.points_par_mission,
        nb_min_missions=c.nb_min_missions,
        annees_seuil=c.annees_seuil,
        points_socle=c.points_socle,
        points_par_annee=c.points_par_annee,
        note_manuelle=c.note_manuelle,
        filtre=lire_filtre(c.filtre),
    )


def choix_de(avis: Avis) -> dict[str, dict[int, bool]]:
    """Les références forcées (vrai) ou exclues (faux) par une personne, par code de critère."""
    choix: dict[str, dict[int, bool]] = {}
    humains = Selection.objects.filter(critere__avis=avis, retenue_par__isnull=False)
    for s in humains.select_related("critere"):
        choix.setdefault(s.critere.code, {})[s.mission_id] = s.retenue
    return choix


def calculer(avis: Avis, references: list[Reference] | None = None) -> notation.Resultat:
    """La note de l'avis, sans rien enregistrer. Lève `FiltreInvalideError` si un filtre ne se
    lit plus. L'ancienneté se compte jusqu'à l'année de la date limite."""
    if references is None:
        references = references_du_bureau()
    criteres = [critere_moteur(c) for c in avis.criteres.all()]
    return notation.noter(
        criteres, references, avis.date_limite.year, avis.seuil_eligibilite, choix_de(avis)
    )


def _points(rc: notation.ResultatCritere, candidate) -> Decimal:
    """Ce qu'une référence retenue apporte : les points par référence (mode par mission)."""
    c = rc.critere
    if c.mode == notation.Mode.PAR_MISSION and candidate in rc.retenues:
        return c.points_par_mission
    return Decimal(0)


@transaction.atomic
def enregistrer_simulation(avis: Avis, resultat: notation.Resultat) -> None:
    """La sélection devient celle du calcul ; les choix d'une personne restent (ADR 0013 § 2)."""
    criteres = {c.code: c for c in avis.criteres.all()}
    en_jeu = {(p.critere, p.code): p.points for p in resultat.en_jeu}
    for rc in resultat.criteres:
        c = criteres[rc.critere.code]
        humains = {s.mission_id: s for s in c.selections.filter(retenue_par__isnull=False)}
        c.selections.filter(retenue_par__isnull=True).delete()
        retenues = {x.reference.ident for x in rc.retenues}
        for rang, x in enumerate(rc.candidates, start=1):
            valeurs = {
                "rang": rang,
                "preuve": x.preuve.value,
                "points": _points(rc, x),
                "points_en_jeu": en_jeu.get((c.code, x.reference.code), Decimal(0)),
            }
            if x.reference.ident in humains:
                Selection.objects.filter(pk=humains[x.reference.ident].pk).update(**valeurs)
            else:
                Selection.objects.create(
                    critere=c,
                    mission_id=x.reference.ident,
                    retenue=x.reference.ident in retenues,
                    **valeurs,
                )
    avis.note_sure = resultat.note_sure
    avis.note_possible = resultat.note_possible
    avis.simulee_le = timezone.now()
    avis.save(update_fields=["note_sure", "note_possible", "simulee_le", "modifie_le"])


def choisir(critere: Critere, mission: Mission, decision: str, motif: str, par) -> None:
    """Forcer ou exclure une référence pour un critère, avec un motif ; « annuler » rend la main
    au calcul. Le choix vaut pour les simulations suivantes."""
    if decision == "annuler":
        Selection.objects.filter(critere=critere, mission=mission).delete()
        return
    if decision not in ("forcer", "exclure"):
        raise ValueError(f"décision inconnue : {decision}")
    s, _ = Selection.objects.get_or_create(
        critere=critere, mission=mission, defaults={"preuve": Selection.Preuve.MANQUANTE}
    )
    s.retenue = decision == "forcer"
    s.retenue_par = par
    s.retenue_le = timezone.now()
    s.motif = motif
    s.save()


# -- pièces exigées à la date limite (AV05) ------------------------------------------------------
def controle_pieces(avis: Avis) -> list[LigneControle]:
    """Chaque pièce exigée par l'avis, la version qu'on joindrait et son état à la date limite de
    dépôt, jamais à la date du jour (ADR 0010 § 6) : le calcul d'`administratif`."""
    codes = list(avis.pieces_exigees.values_list("type__code", flat=True))
    return controle_a_la_date(avis.date_limite, seulement=codes)


def lien_controle(avis: Avis) -> str:
    """Les paramètres de l'écran « Contrôle avant un dépôt » pour cet avis : la date limite et
    les pièces demandées en plus des pièces par défaut."""
    en_plus = avis.pieces_exigees.filter(type__exigee_par_defaut=False)
    parametres = [("date", avis.date_limite.isoformat()), ("avis", avis.reference)]
    parametres += [("avec", code) for code in en_plus.values_list("type__code", flat=True)]
    return urlencode(parametres)
