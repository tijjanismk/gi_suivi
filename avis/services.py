"""Services du module avis (ADR 0013) : les références du bureau telles que le moteur les voit,
l'aperçu d'un critère, le filtre dit en clair, les pièces exigées. Les vues (et plus tard les
outils MCP) passent par ici ; le calcul reste dans `moteur/avis/`."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlencode

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from administratif.models import TypePiece
from administratif.services import (
    LigneControle,
    PartageIndisponibleError,
    chemin_absolu,
    controle_a_la_date,
)
from avis.models import Avis, BesoinExpert, Critere, PieceExigee, Proposition, Selection
from experts.models import Expert
from moteur.avis import experts as experts_moteur
from moteur.avis import notation
from moteur.avis import sommaire as sommaire_moteur
from moteur.avis.filtres import (
    PIECES_PAR_DEFAUT,
    Piece,
    Preuve,
    Reference,
    correspond,
    lire_filtre,
)
from moteur.avis.selection import selectionner
from moteur.references.doublons import mots
from references.models import Mission
from referentiel.models import (
    Bailleur,
    Categorie,
    Client,
    Domaine,
    Terme,
    TypeOuvrage,
    TypeQuantite,
)

CODES_EN_APERCU = 10
EXPERTS_PROPOSES = 15  # dans la liste où l'on choisit l'expert retenu
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
    criteres = [critere_moteur(c) for c in avis.criteres.filter(brouillon=False)]
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
    criteres = {c.code: c for c in avis.criteres.filter(brouillon=False)}
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


# -- experts demandés (AV06) ----------------------------------------------------------------------
def profils_du_vivier(references: list[Reference]) -> list[experts_moteur.Profil]:
    """Les experts mobilisables (pas les anciens), avec leur plus haut diplôme et les missions de
    leurs affectations, telles que le moteur les voit."""
    par_pk = {r.ident: r for r in references}
    vivier = Expert.objects.exclude(statut=Expert.Statut.ANCIEN)
    profils = []
    for e in vivier.prefetch_related("diplomes", "affectations"):
        diplomes = list(e.diplomes.all())
        niveau = max((d.niveau for d in diplomes), key=experts_moteur.rang_niveau, default="")
        profils.append(
            experts_moteur.Profil(
                ident=e.pk,
                nom=f"{e.nom} {e.prenoms}".strip(),
                textes=" ".join([e.specialite, e.fonction, *(d.intitule for d in diplomes)]),
                niveau=niveau,
                debut_carriere=e.debut_carriere,
                annee_diplome=min((d.annee for d in diplomes if d.annee), default=None),
                disponible=e.disponible,
                a_verifier=bool(e.a_verifier.strip()),
                references=tuple(
                    par_pk[a.mission_id] for a in e.affectations.all() if a.mission_id in par_pk
                ),
            )
        )
    return profils


def besoin_moteur(b: BesoinExpert) -> experts_moteur.Besoin:
    return experts_moteur.Besoin(
        poste=b.poste,
        niveau_min=b.niveau_min,
        annees_min=b.annees_experience_min,
        nb_references_min=b.nb_references_min,
        specialites=tuple(s.strip() for s in b.specialites.split(",") if s.strip()),
        filtre=lire_filtre(b.filtre_references),
    )


def experts_pour(avis: Avis, references: list[Reference] | None = None) -> list[dict]:
    """Pour chaque poste demandé : les experts du vivier classés et l'expert retenu, comparés au
    profil l'année de la date limite."""
    besoins = list(avis.besoins.select_related("expert_retenu"))
    if not besoins:
        return []
    if references is None:
        references = references_du_bureau()
    profils = profils_du_vivier(references)
    annee = avis.date_limite.year
    lignes = []
    for b in besoins:
        classement = experts_moteur.classer(besoin_moteur(b), profils, annee)
        retenu = next((x for x in classement if x.profil.ident == b.expert_retenu_id), None)
        choix = classement[:EXPERTS_PROPOSES]
        if retenu is not None and retenu not in choix:
            choix.append(retenu)
        lignes.append(
            {
                "b": b,
                "classement": classement,
                "choix": choix,
                "retenu": retenu,
                "complets": sum(1 for x in classement if x.complet),
            }
        )
    return lignes


# -- dossier d'un AMI (AV11, AV14) ----------------------------------------------------------------
LOGOS = "ADMINISTRATIF\\LOGOS"  # le logo du bureau, LOGO.png (ou .jpg), y est lu


def logo_du_bureau() -> Path | None:
    """Le logo du bureau, lu sur le partage (règle 4). None : pas de logo, ou partage injoignable
    (le dossier imprime alors le nom du bureau en texte)."""
    for extension in (".png", ".jpg", ".jpeg"):
        try:
            chemin = chemin_absolu(f"{LOGOS}\\LOGO{extension}")
            if chemin.is_file():
                return chemin
        except PartageIndisponibleError:
            return None
        except (ValueError, OSError):
            continue
    return None


def bureau() -> sommaire_moteur.Bureau:
    identite = settings.BUREAU
    return sommaire_moteur.Bureau(identite["raison_sociale"], identite["nom_court"])


def _reference_du_dossier(m: Mission) -> sommaire_moteur.Reference:
    """Une référence retenue, avec les sept colonnes des listes et ses pièces sur le partage."""
    pieces = tuple(sommaire_moteur.Justificatif(p.type, p.chemin) for p in m.pieces.all())
    bailleur = (m.bailleur.sigle or m.bailleur.nom) if m.bailleur else ""
    return sommaire_moteur.Reference(
        code=m.code,
        titre=m.intitule,
        client=m.client.nom if m.client else "",
        pays=m.pays,
        montant=m.montant,
        devise=m.devise,
        source=bailleur,
        annee=m.annee,
        debut=m.date_debut,
        fin=m.date_fin,
        justificatifs=pieces,
    )


def _criteres_du_dossier(avis: Avis) -> list[sommaire_moteur.Critere]:
    """Les critères validés de l'avis et les références jointes à chacun : toutes celles qui
    répondent (`Selection`), pas seulement celles qui portent les points, sauf celles qu'une
    personne a exclues (règle du porteur, 09/11/2026). None tant qu'aucune simulation n'est
    enregistrée et qu'aucune personne n'en a forcé une."""
    retenues: dict[int, list[sommaire_moteur.Reference]] = {}
    selections = Selection.objects.filter(critere__avis=avis)
    selections = selections.exclude(retenue=False, retenue_par__isnull=False)
    selections = selections.select_related("mission__client", "mission__bailleur")
    for s in selections.prefetch_related("mission__pieces").order_by("critere", "rang"):
        retenues.setdefault(s.critere_id, []).append(_reference_du_dossier(s.mission))
    criteres = []
    for c in avis.criteres.filter(brouillon=False):
        trouvees = retenues.get(c.pk)
        if trouvees is None and avis.simulee_le is None:
            liste = None
        else:
            liste = tuple(trouvees or ())
        criteres.append(sommaire_moteur.Critere(c.code, c.libelle, c.experience, c.mode, liste))
    return criteres


def _references_generales() -> list[sommaire_moteur.Reference]:
    """D.1 : toutes les références du bureau, sauf les absorbées (on cite le code gardé)."""
    missions = Mission.objects.filter(absorbee_par__isnull=True).order_by("code")
    missions = missions.select_related("client", "bailleur").prefetch_related("pieces")
    return [_reference_du_dossier(m) for m in missions]


def _pieces_du_dossier(controle: Iterable[LigneControle]) -> list[sommaire_moteur.Piece]:
    """Les pièces exigées, dans l'ordre du registre des types, avec la version qu'on joindrait."""
    return [
        sommaire_moteur.Piece(
            x.type.code,
            x.libelle_etat,
            x.a_regler,
            x.type.libelle,
            x.version.chemin if x.version else "",
        )
        for x in sorted(controle, key=lambda x: (x.type.ordre, x.type.libelle))
    ]


def _postes_du_dossier(avis: Avis) -> list[sommaire_moteur.Poste]:
    postes = []
    for b in avis.besoins.select_related("expert_retenu"):
        e = b.expert_retenu
        nom = f"{e.nom} {e.prenoms}".strip() if e else ""
        postes.append(sommaire_moteur.Poste(b.poste, nom))
    return postes


def sommaire(
    avis: Avis, controle: Iterable[LigneControle] | None = None
) -> list[sommaire_moteur.Rubrique]:
    """Les intercalaires de la réponse (`moteur.avis.sommaire`) et ce qu'on sait de chacun, pour
    la carte de la fiche. `controle` : les pièces exigées, s'il est déjà calculé. Un critère en
    brouillon n'y entre pas tant qu'il n'est pas enregistré (règle 3)."""
    if controle is None:
        controle = controle_pieces(avis)
    actives = Mission.objects.filter(absorbee_par__isnull=True).values_list("code", flat=True)
    return sommaire_moteur.sommaire(
        _criteres_du_dossier(avis),
        avis.groupement,
        _pieces_du_dossier(controle),
        _postes_du_dossier(avis),
        bureau(),
        [sommaire_moteur.Reference(code, "") for code in actives],  # D.1 : le compte suffit
    )


@dataclass(frozen=True)
class Dossier:
    """Le dossier de réponse à un AMI, tel que la page à imprimer et l'outil MCP le montrent."""

    avis: Avis
    rubriques: list[sommaire_moteur.Rubrique]
    pages: list[sommaire_moteur.Page]
    postes: list[sommaire_moteur.Poste]
    bureau: dict
    logo: bool  # le logo est sur le partage ; sinon, le nom du bureau en texte

    @property
    def numero(self) -> str:
        """La référence de l'avis sans le « N° » qui la précède parfois : l'en-tête l'écrit."""
        return re.sub(r"^\s*n\s*°\s*", "", self.avis.reference, flags=re.IGNORECASE)

    @property
    def pays(self) -> tuple[str, str]:
        return sommaire_moteur.pays(self.avis.pays)

    @property
    def mois(self) -> str:
        return sommaire_moteur.mois_annee(self.avis.date_limite)

    @property
    def attention(self) -> str:
        """À qui s'adresse la lettre : le destinataire saisi, sinon le maître d'ouvrage."""
        if self.avis.destinataire:
            return f"L’attention de {self.avis.destinataire}"
        mo = self.avis.maitre_ouvrage
        return mo.nom if mo else ""

    @property
    def formule_appel(self) -> str:
        return self.avis.formule_appel or "Madame, Monsieur"

    @property
    def experts(self) -> list[sommaire_moteur.Poste]:
        """Les postes qui ont un expert retenu : ils s'ajoutent à l'organigramme."""
        return [p for p in self.postes if p.expert]

    @property
    def a_regler(self) -> list[sommaire_moteur.Page]:
        """Les pages manquantes ou périmées, dans l'ordre du dossier."""
        etats = (sommaire_moteur.Etat.MANQUANTE, sommaire_moteur.Etat.PERIMEE)
        return [p for p in self.pages if p.etat in etats]

    @property
    def compte(self) -> dict[str, int]:
        """Le nombre de pages par état : rédigées, à insérer, périmées, manquantes."""
        compte = Counter(p.etat.value for p in self.pages)
        return {e.value: compte[e.value] for e in sommaire_moteur.Etat}


def plan_dossier(avis: Avis, intercalaires_seulement: bool = False) -> Dossier:
    """Le dossier de réponse à un AMI, page par page (`moteur.avis.sommaire.plan`) : ce que
    l'application rédige, les fichiers du partage à insérer (chemins relatifs) et ce qui manque.
    `intercalaires_seulement` : le sommaire et les intercalaires, pour les imprimer à part."""
    criteres = _criteres_du_dossier(avis)
    pieces = _pieces_du_dossier(controle_pieces(avis))
    postes = _postes_du_dossier(avis)
    b = bureau()
    toutes = _references_generales()
    rubriques = sommaire_moteur.sommaire(criteres, avis.groupement, pieces, postes, b, toutes)
    pages = sommaire_moteur.plan(criteres, avis.groupement, pieces, postes, b, toutes)
    if intercalaires_seulement:
        pages = [p for p in pages if p.genre in ("sommaire", "intercalaire")]
    logo = logo_du_bureau() is not None
    return Dossier(avis, rubriques, pages, postes, settings.BUREAU, logo)


# -- propositions à valider (AV08) ---------------------------------------------------------------
TYPES_AVIS = {"AMI", "DP", "AO"}


def _date_proposee(texte) -> date | None:
    """« 28/10/2026 » ou « 2026-10-28 » ; rien sinon (la personne la saisit)."""
    for format_ in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(texte or "").strip(), format_).date()
        except ValueError:
            continue
    return None


def _organisme(modele, nom: str):
    nom = (nom or "").strip()
    if not nom:
        return None
    return modele.objects.filter(Q(nom__iexact=nom) | Q(sigle__iexact=nom)).first()


def creer_proposition(
    origine: str, champs: dict, source_url: str = "", fichier_chemin: str = "", par: str = ""
) -> Proposition:
    """Une proposition à valider ; jamais un avis (règle 3). `champs` : reference, objet, type,
    date_limite, maitre_ouvrage, bailleur, pays… tels qu'extraits."""
    if origine not in Proposition.Origine.values:
        raise ValueError(f"origine inconnue : {origine}")
    if not isinstance(champs, dict):
        raise ValueError("les champs extraits sont un objet (nom → valeur)")
    return Proposition.objects.create(
        origine=origine,
        champs_extraits={str(k): v for k, v in champs.items()},
        source_url=(source_url or "")[:500],
        fichier_chemin=(fichier_chemin or "")[:500],
        proposee_par=(par or "")[:150],
    )


def _cle_reference(texte) -> str:
    """« AMI n° 004/2026 » et « ami N°004-2026 » donnent la même clé."""
    return re.sub(r"[\W_]", "", str(texte or "").casefold())


def _meme_pays(a, b) -> bool:
    a, b = str(a or "").strip().casefold(), str(b or "").strip().casefold()
    return not a or not b or a == b


def deja_connu(champs, source_url: str = "") -> dict | None:
    """L'avis ou la proposition qui porte déjà cette référence (dans le même pays, quand les deux
    le disent) ou ce lien ; une proposition rejetée compte, pour ne pas la reproposer. Rien si
    l'avis est nouveau. Sert à la veille, qui relit les mêmes listes chaque jour."""
    extraits = champs if isinstance(champs, dict) else {}
    cle, pays = _cle_reference(extraits.get("reference")), extraits.get("pays")
    lien = (source_url or "").strip()
    if cle:
        for pk, reference, objet, pays_avis in Avis.objects.values_list(
            "pk", "reference", "objet", "pays"
        ):
            if _cle_reference(reference) == cle and _meme_pays(pays, pays_avis):
                return {"avis_id": pk, "adresse": f"/avis/{pk}/", "objet": objet[:200]}
    if not cle and not lien:
        return None
    for pk, connus, url, statut in Proposition.objects.values_list(
        "pk", "champs_extraits", "source_url", "statut"
    ):
        connus = connus or {}
        meme_reference = cle and _cle_reference(connus.get("reference")) == cle
        if (lien and url == lien) or (meme_reference and _meme_pays(pays, connus.get("pays"))):
            return {
                "proposition_id": pk,
                "adresse": f"/avis/propositions/{pk}",
                "statut": Proposition.Statut(statut).label,
                "objet": str(connus.get("objet", ""))[:200],
            }
    return None


def initiaux(p: Proposition) -> dict:
    """Les champs extraits, prêts pour le formulaire de l'avis. Un maître d'ouvrage ou un
    bailleur absent du référentiel est noté dans les observations, pour être choisi à la main."""
    e = p.champs_extraits or {}
    simples = (
        "reference",
        "objet",
        "pays",
        "lieu_depot",
        "courriel_depot",
        "methode_selection",
        "fichier_avis_chemin",
        "fichier_tdr_chemin",
        "observations",
    )
    initial = {k: str(e[k]) for k in simples if e.get(k)}
    type_ = str(e.get("type", "")).strip().upper()
    initial["type"] = type_ if type_ in TYPES_AVIS else Avis.Type.AUTRE
    for cle in ("date_limite", "date_publication"):
        if _date_proposee(e.get(cle)):
            initial[cle] = _date_proposee(e.get(cle))
    if p.fichier_chemin and "fichier_avis_chemin" not in initial:
        initial["fichier_avis_chemin"] = p.fichier_chemin
    notes = [initial.get("observations", "")]
    for cle, modele, libelle in (
        ("maitre_ouvrage", Client, "Maître d'ouvrage"),
        ("bailleur", Bailleur, "Bailleur"),
    ):
        trouve = _organisme(modele, str(e.get(cle, "")))
        if trouve:
            initial[cle] = trouve.pk
        elif e.get(cle):
            notes.append(f"{libelle} proposé : {e[cle]} (absent du référentiel)")
    initial["observations"] = "\n".join(n for n in notes if n)
    return initial


@transaction.atomic
def accepter(p: Proposition, formulaire, par) -> Avis:
    """L'avis confirmé est créé, une seule fois ; la proposition garde ce qui a été confirmé."""
    p = Proposition.objects.select_for_update().get(pk=p.pk)
    if p.statut != Proposition.Statut.A_VALIDER:
        raise ValueError(f"proposition déjà {p.get_statut_display()}")
    a = formulaire.save(commit=False)
    a.cree_par = par
    a.save()
    p.statut = Proposition.Statut.ACCEPTEE
    p.avis_cree = a
    p.champs_confirmes = {
        k: str(v) for k, v in formulaire.cleaned_data.items() if v not in (None, "", False)
    }
    p.decide_par = par
    p.decide_le = timezone.now()
    p.save()
    return a


def rejeter(p: Proposition, motif: str, par) -> None:
    if p.statut != Proposition.Statut.A_VALIDER:
        raise ValueError(f"proposition déjà {p.get_statut_display()}")
    if not (motif or "").strip():
        raise ValueError("indiquez le motif du rejet")
    p.statut = Proposition.Statut.REJETEE
    p.motif_rejet = motif.strip()[:500]
    p.decide_par = par
    p.decide_le = timezone.now()
    p.save()


def a_valider() -> int:
    return Proposition.objects.filter(statut=Proposition.Statut.A_VALIDER).count()


# -- outils MCP (AV09) ---------------------------------------------------------------------------
def rechercher(
    filtre: dict, texte: str = "", limite: int = 20, references: list[Reference] | None = None
) -> tuple[int, list]:
    """Les références qui répondent au filtre d'un critère et au texte libre (tous ses mots dans
    l'intitulé), classées comme pour un critère. `pieces_completes_requises` à vrai ne garde que
    les références prouvées. Rend (nombre total, les premières)."""
    if references is None:
        references = references_du_bureau()
    candidates = selectionner(lire_filtre(filtre), references)
    if filtre.get("pieces_completes_requises") is True:
        candidates = [c for c in candidates if c.preuve == Preuve.PROUVEE]
    if texte.strip():
        libre = lire_filtre({"mots_cles": [texte]})
        candidates = [c for c in candidates if correspond(libre, c.reference)]
    return len(candidates), candidates[:limite]


def vocabulaire_pour(texte: str) -> dict:
    """Le vocabulaire de la base qu'un filtre peut employer, chaque entrée marquée quand elle
    partage un mot avec le texte du bailleur (le thésaurus : familles et termes validés compris,
    avec leur pays, ADR 0019 ; les termes proposés sont signalés à part, ils ne comptent pas).
    Aucune traduction ici : Claude propose le filtre, une personne le valide à l'écran."""
    cherches = mots(texte or "")

    def evoque(*textes: str) -> bool:
        return bool(cherches & mots(" ".join(t for t in textes if t)))

    termes: dict[int, dict[str, list[dict]]] = {}
    for t in Terme.objects.exclude(statut=Terme.Statut.REJETE):
        place = termes.setdefault(t.type_ouvrage_id, {"valides": [], "proposes": []})
        cle = "valides" if t.statut == Terme.Statut.VALIDE else "proposes"
        place[cle].append({"terme": t.terme, "pays": t.pays or "tous", "portee": t.portee})
    vide: dict[str, list[dict]] = {"valides": [], "proposes": []}

    return {
        "domaines": [
            {"code": d.code, "libelle": d.libelle, "evoque": evoque(d.libelle)}
            for d in Domaine.objects.all()
        ],
        "categories": [
            {
                "cle": c.cle,
                "libelle": c.libelle,
                "domaine": c.domaine.code,
                "evoque": evoque(c.libelle),
            }
            for c in Categorie.objects.select_related("domaine")
        ],
        "types_ouvrage": [
            {
                "cle": o.cle,
                "libelle": o.libelle,
                "famille": o.famille,
                "termes": termes.get(o.pk, vide)["valides"],
                "termes_proposes": termes.get(o.pk, vide)["proposes"],
                "evoque": evoque(
                    o.libelle,
                    o.famille,
                    *(x["terme"] for x in termes.get(o.pk, vide)["valides"]),
                ),
            }
            for o in TypeOuvrage.objects.filter(actif=True)
        ],
        "types_quantite": [
            {"cle": q.cle, "libelle": q.libelle, "unite": q.unite}
            for q in TypeQuantite.objects.all()
        ],
        "natures": NATURES,
        "roles": ROLES,
    }


CHAMPS_CRITERE = (
    "code",
    "libelle",
    "reference_avis",
    "mode",
    "experience",
    "points_par_mission",
    "plafond",
    "nb_min_missions",
    "annees_seuil",
    "points_socle",
    "points_par_annee",
    "note_manuelle",
)


def enregistrer_brouillon(avis: Avis, donnees: dict) -> Critere:
    """Un critère préparé par Claude, marqué brouillon : il ne compte pas dans la note avant
    qu'une personne l'ouvre et l'enregistre. Lève `ValidationError` (filtre, mode, code pris)."""
    champs = {k: donnees[k] for k in CHAMPS_CRITERE if donnees.get(k) not in (None, "")}
    c = Critere(
        avis=avis,
        brouillon=True,
        filtre=donnees.get("filtre") or {},
        ordre=avis.criteres.count() + 1,
        **champs,
    )
    c.full_clean()
    c.save()
    return c


def rechercher_experts(
    besoin: experts_moteur.Besoin,
    disponibles_seulement: bool = True,
    references: list[Reference] | None = None,
) -> list[experts_moteur.Adequation]:
    """Le vivier comparé à un profil, cette année : comme pour un poste d'avis."""
    profils = profils_du_vivier(references if references is not None else references_du_bureau())
    if disponibles_seulement:
        profils = [p for p in profils if p.disponible]
    return experts_moteur.classer(besoin, profils, timezone.localdate().year)
