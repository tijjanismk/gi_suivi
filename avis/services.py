"""Services du module avis (ADR 0013) : les références du bureau telles que le moteur les voit,
l'aperçu d'un critère, le filtre dit en clair, les pièces exigées. Les vues (et plus tard les
outils MCP) passent par ici ; le calcul reste dans `moteur/avis/`."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

from administratif.models import TypePiece
from avis.models import Avis, PieceExigee
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
