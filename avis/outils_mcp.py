"""Outils MCP du module avis (`docs/outils-mcp.md`, ADR 0016) : ce que Claude Desktop voit de
l'application. Chaque fonction est un outil : sa documentation, en français et avec des exemples,
est ce que Claude lit. Elles appellent les services, comme les écrans ; aucun calcul ici. Lecture
libre, écriture bornée : seulement une proposition d'avis, un critère en brouillon ou un terme
proposé (ADR 0019), jamais un avis ni un terme validés (règle 3). Les réponses sont compactes ;
`detail_mission` donne tout.

Montées telles quelles sous `/mcp/` par `config/serveur_mcp.py` (ADR 0016), qui vérifie l'identité
et les droits et pose `par` d'après le ticket Kerberos ; Claude Desktop y arrive par le pont du
poste (`agent/pont-mcp.py`).
"""

from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError

from avis import services
from avis.models import Avis
from experts.models import Affectation
from moteur.avis.experts import Besoin
from moteur.avis.filtres import FiltreInvalideError, lire_filtre
from references.models import Mission
from referentiel import services as referentiel_services
from referentiel.models import Bailleur, Categorie, Client, Domaine, TypeOuvrage, TypeQuantite

LIMITE = 20
LEVIERS = 3


def _nombre(valeur: Decimal | None) -> str | None:
    return None if valeur is None else f"{valeur.normalize():f}"


def _avis(avis_id: int) -> Avis | None:
    return Avis.objects.filter(pk=avis_id).first()


def rechercher_missions(texte: str = "", limite: int = LIMITE, **filtre) -> dict:
    """Recherche des références du bureau. Paramètres : les clés du filtre d'un critère
    (natures, domaines, categories, types_ouvrage, familles_ouvrage, roles, annee_min,
    annee_max, pays, clients, bailleurs, quantites_min, mots_cles, pieces_completes_requises),
    toutes facultatives, plus `texte` (mots de l'intitulé) et `limite` (20 par défaut).
    Exemple : « études de micro-barrages ou seuils depuis 2010 avec les trois pièces » →
    {"natures": ["ETU", "ETC"], "types_ouvrage": ["micro-barrage", "seuil-epandage"],
    "annee_min": 2010, "pieces_completes_requises": true}."""
    try:
        total, candidates = services.rechercher(filtre, texte, max(1, min(int(limite), 100)))
    except FiltreInvalideError as e:
        return {"erreur": f"filtre : {e}"}
    ids = [c.reference.ident for c in candidates]
    libelles = dict(Mission.objects.filter(pk__in=ids).values_list("pk", "intitule_court"))
    return {
        "total": total,
        "missions": [
            {
                "code": c.reference.code,
                "intitule_court": libelles.get(c.reference.ident) or c.reference.intitule[:120],
                "annee": c.reference.annee,
                "nature": c.reference.nature,
                "domaines": sorted(c.reference.domaines),
                "clients": sorted(c.reference.clients),
                "preuve": c.preuve.value,
                "quantites": {k: _nombre(v) for k, v in c.reference.quantites.items()},
            }
            for c in candidates
        ],
    }


def detail_mission(code: str) -> dict:
    """Tout sur une référence : champs du contrat, domaines, ouvrages, quantités, pièces avec leur
    chemin sur le partage et leur audit, experts affectés. Paramètre : `code` (GIC-AEP-CTR-015)."""
    liees = ("domaine", "client", "bailleur", "categorie", "absorbee_par")
    m = Mission.objects.select_related(*liees).filter(code=(code or "").strip().upper()).first()
    if m is None:
        return {"erreur": f"référence inconnue : {code}"}
    affectations = Affectation.objects.filter(mission=m).select_related("expert")
    return {
        "code": m.code,
        "intitule": m.intitule,
        "domaine": m.domaine.code,
        "domaines_secondaires": list(m.domaines_secondaires.values_list("code", flat=True)),
        "nature": m.nature,
        "categorie": m.categorie.libelle if m.categorie else None,
        "client": m.client.nom if m.client else None,
        "bailleur": m.bailleur.nom if m.bailleur else None,
        "pays": m.pays,
        "annee": m.annee,
        "montant": _nombre(m.montant),
        "devise": m.devise,
        "role": m.role,
        "absorbee_par": m.absorbee_par.code if m.absorbee_par else None,
        "verification": m.statut_verification,
        "types_ouvrage": list(m.types_ouvrage.values_list("cle", flat=True)),
        "quantites": {q.type.cle: _nombre(q.valeur) for q in m.quantites.select_related("type")},
        "pieces": [
            {
                "type": p.type,
                "nature": p.nature_exacte,
                "chemin": p.chemin,
                "lisible": p.lisible,
                "coherente": p.coherente,
            }
            for p in m.pieces.all()
        ],
        "experts": [
            {"expert": str(a.expert), "poste": a.poste, "preuve": a.preuve} for a in affectations
        ],
    }


def lister_referentiel(table: str, filtre_texte: str = "") -> dict:
    """Le vocabulaire de la base, avant de proposer un filtre. `table` : domaines, categories,
    types_ouvrage, types_quantite, clients ou bailleurs ; `filtre_texte` : un mot du libellé."""
    sources = {
        "domaines": (Domaine.objects.all(), lambda d: {"code": d.code, "libelle": d.libelle}),
        "categories": (
            Categorie.objects.select_related("domaine"),
            lambda c: {"cle": c.cle, "libelle": c.libelle, "domaine": c.domaine.code},
        ),
        "types_ouvrage": (
            TypeOuvrage.objects.filter(actif=True),
            lambda o: {"cle": o.cle, "libelle": o.libelle, "famille": o.famille},
        ),
        "types_quantite": (
            TypeQuantite.objects.all(),
            lambda q: {"cle": q.cle, "libelle": q.libelle, "unite": q.unite},
        ),
        "clients": (Client.objects.all(), lambda c: {"nom": c.nom, "sigle": c.sigle}),
        "bailleurs": (Bailleur.objects.all(), lambda b: {"nom": b.nom, "sigle": b.sigle}),
    }
    if table not in sources:
        return {"erreur": f"table inconnue : {table} ; tables : {', '.join(sources)}"}
    qs, forme = sources[table]
    if filtre_texte:
        champ = "nom" if table in ("clients", "bailleurs") else "libelle"
        qs = qs.filter(**{f"{champ}__icontains": filtre_texte})
    return {table: [forme(x) for x in qs[:200]]}


def simuler_avis(avis_id: int) -> dict:
    """La note simulée d'un avis : par critère, les points sûrs et possibles, le plafond, les
    références retenues et les alertes ; puis la note, le seuil, le verdict (eligible,
    incertain, non_eligible) et les trois pièces qui rapportent le plus de points."""
    a = _avis(avis_id)
    if a is None:
        return {"erreur": f"avis inconnu : {avis_id}"}
    try:
        r = services.calculer(a)
    except FiltreInvalideError as e:
        return {"erreur": f"un filtre du barème ne se lit plus : {e}"}
    return {
        "avis": f"{a.type} {a.reference}",
        "criteres": [
            {
                "code": rc.critere.code,
                "note_sure": _nombre(rc.note_sure),
                "note_possible": _nombre(rc.note_possible),
                "plafond": _nombre(rc.critere.plafond),
                "retenues": [
                    {"code": x.reference.code, "preuve": x.preuve.value} for x in rc.retenues
                ],
                "eligibles": len(rc.candidates),
                "alertes": rc.alertes,
            }
            for rc in r.criteres
        ],
        "note_sure": _nombre(r.note_sure),
        "note_possible": _nombre(r.note_possible),
        "seuil": _nombre(r.seuil),
        "verdict": r.verdict.value if r.verdict else None,
        "leviers": [
            {"critere": p.critere, "code": p.code, "points": _nombre(p.points)}
            for p in r.en_jeu[:LEVIERS]
        ],
    }


def pieces_manquantes(avis_id: int) -> dict:
    """Les pièces absentes ou pas encore auditées des références d'un avis, classées par points
    en jeu : pour chacune, le critère, la référence, ce qui manque et où le ranger."""
    a = _avis(avis_id)
    if a is None:
        return {"erreur": f"avis inconnu : {avis_id}"}
    try:
        r = services.calculer(a)
    except FiltreInvalideError as e:
        return {"erreur": f"un filtre du barème ne se lit plus : {e}"}
    return {
        "pieces": [
            {
                "critere": p.critere,
                "code": p.code,
                "points": _nombre(p.points),
                "manques": [{"piece": m.exigence, "etat": m.etat.value} for m in p.manques],
                "dossier": f"REFERENCES\\02_JUSTIFICATIFS\\{p.code}",
            }
            for p in r.en_jeu
        ]
    }


def rechercher_experts(
    poste: str = "",
    niveau_min: str = "",
    annees_experience_min: int = 0,
    nb_references_min: int = 0,
    specialites: str = "",
    filtre_references: dict | None = None,
    disponibles_seulement: bool = True,
    limite: int = 10,
) -> dict:
    """Les experts du vivier comparés à un profil des TDR : `niveau_min` (bac+2 … bac+8),
    `annees_experience_min`, `nb_references_min` (missions de ses affectations qui passent
    `filtre_references`, même format que le filtre d'un critère), `specialites` (mots séparés
    par des virgules ; un seul suffit). Pour chacun : ce qui manque au profil."""
    try:
        besoin = Besoin(
            poste=poste,
            niveau_min=niveau_min,
            annees_min=int(annees_experience_min),
            nb_references_min=int(nb_references_min),
            specialites=tuple(s.strip() for s in specialites.split(",") if s.strip()),
            filtre=lire_filtre(filtre_references or {}),
        )
    except FiltreInvalideError as e:
        return {"erreur": f"filtre des références : {e}"}
    classement = services.rechercher_experts(besoin, disponibles_seulement)
    return {
        "experts": [
            {
                "expert_id": x.profil.ident,
                "nom": x.profil.nom,
                "niveau": x.profil.niveau,
                "annees_experience": x.annees,
                "annees_estimees": x.annees_estimees,
                "references": x.references,
                "ecarts": list(x.ecarts),
                "a_verifier": x.profil.a_verifier,
            }
            for x in classement[: max(1, min(int(limite), 50))]
        ]
    }


def proposer_filtre_critere(texte_critere: str, avis_id: int | None = None) -> dict:
    """Ne calcule rien : rend le vocabulaire de la base (domaines, catégories, types d'ouvrages
    avec familles et termes validés par pays, types de quantités, natures, rôles), chaque entrée
    marquée `evoque` quand elle partage un mot avec le texte du bailleur, pour que Claude
    construise le filtre et l'explique. L'humain le valide à l'écran. C'est la réponse au problème
    « recharge de nappe » ≠ « micro-barrage »."""
    vocabulaire = services.vocabulaire_pour(texte_critere)
    vocabulaire["texte_critere"] = texte_critere
    if avis_id is not None and _avis(avis_id) is None:
        vocabulaire["avertissement"] = f"avis inconnu : {avis_id}"
    return vocabulaire


def proposer_terme(
    type_ouvrage: str,
    terme: str,
    pays: str = "",
    source_url: str = "",
    nb_avis: int | None = None,
    portee: str = "partout",
    par: str = "",
) -> dict:
    """Propose un nom local d'un type d'ouvrage, à valider par une personne (jamais validé ici).
    Exemple : type_ouvrage="aes", terme="AEPS", pays="Burkina Faso", source_url=l'avis où il est
    lu. `type_ouvrage` : une clé de `lister_referentiel("types_ouvrage")` ; `pays` : un pays du
    bureau (Mali, Niger, Burkina Faso, Guinée, Mauritanie, Sénégal, Togo, Gabon, Cameroun), vide
    pour tous ; `portee` : « partout » ou « references » (seulement les intitulés des références du
    bureau, pour un sigle qui veut dire autre chose dans les avis, comme PPM). Écrire le terme tel
    qu'il est dans l'avis : accents, tiret, sigle en capitales."""
    try:
        t, cree = referentiel_services.proposer(
            type_ouvrage,
            terme,
            origine="claude",
            pays=pays,
            portee=portee,
            source_url=source_url,
            nb_avis=nb_avis,
            par=par or "Claude Desktop",
        )
    except ValueError as e:
        return {"erreur": str(e)}
    reponse = {
        "terme_id": t.pk,
        "statut": t.get_statut_display(),
        "adresse": f"/admin/referentiel/terme/{t.pk}/change/",
    }
    if not cree:
        reponse["avertissement"] = "ce terme existait déjà pour ce type et ce pays : rien changé"
    return reponse


def creer_proposition(
    champs: dict, source_url: str = "", fichier_chemin: str = "", par: str = ""
) -> dict:
    """Crée une proposition d'avis à valider (jamais un avis). `champs` : reference, objet, type
    (AMI, DP, AO), date_limite (28/10/2026), maitre_ouvrage, bailleur, pays, lieu_depot,
    methode_selection… tels que lus dans l'avis. Rend l'identifiant et l'adresse de l'écran de
    validation."""
    try:
        p = services.creer_proposition("claude", champs, source_url, fichier_chemin, par)
    except ValueError as e:
        return {"erreur": str(e)}
    return {"proposition_id": p.pk, "adresse": f"/avis/propositions/{p.pk}"}


def enregistrer_brouillon_critere(avis_id: int, critere: dict) -> dict:
    """Prépare un critère du barème, marqué brouillon : il ne compte pas dans la note avant qu'une
    personne l'ouvre et l'enregistre. `critere` : code, libelle, mode (par_mission, anciennete,
    forfait, manuel), points_par_mission, plafond, nb_min_missions, annees_seuil, points_socle,
    points_par_annee, filtre (format de `docs/schema-donnees.md`)."""
    a = _avis(avis_id)
    if a is None:
        return {"erreur": f"avis inconnu : {avis_id}"}
    try:
        c = services.enregistrer_brouillon(a, critere or {})
    except ValidationError as e:
        return {"erreur": "; ".join(f"{k} : {' '.join(v)}" for k, v in e.message_dict.items())}
    return {"critere_id": c.pk, "adresse": f"/avis/{a.pk}/critere/{c.pk}", "brouillon": True}


OUTILS = (
    rechercher_missions,
    detail_mission,
    lister_referentiel,
    simuler_avis,
    pieces_manquantes,
    rechercher_experts,
    proposer_filtre_critere,
    proposer_terme,
    creer_proposition,
    enregistrer_brouillon_critere,
)
