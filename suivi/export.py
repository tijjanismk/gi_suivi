"""Export Excel (T08) : six feuilles, totaux en formules (recalculés si une cellule change),
largeurs fixées, en-têtes figés, nom de fichier daté `GI-Suivi_<debut>_<fin>.xlsx`."""

from __future__ import annotations

from io import BytesIO

from django.db.models import Sum
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from suivi import rapports
from suivi.models import Segment

GRAS = Font(bold=True)
FOND_ENTETE = PatternFill("solid", fgColor="DBEAFE")
FORMAT_HEURES = "0.00"
FORMAT_PCT = "0.0%"


def _heures(secondes) -> float:
    return round(int(secondes or 0) / 3600, 2)


def _feuille(classeur: Workbook, titre: str, entetes: list[str], largeurs: list[int]):
    feuille = classeur.create_sheet(titre)
    feuille.append(entetes)
    for cellule in feuille[1]:
        cellule.font = GRAS
        cellule.fill = FOND_ENTETE
        cellule.alignment = Alignment(vertical="center", wrap_text=True)
    for i, largeur in enumerate(largeurs, start=1):
        feuille.column_dimensions[get_column_letter(i)].width = largeur
    feuille.freeze_panes = "A2"
    return feuille


def _formater(feuille, colonnes_heures=(), colonnes_pct=()):
    for ligne in feuille.iter_rows(min_row=2):
        for c in ligne:
            if c.column in colonnes_heures:
                c.number_format = FORMAT_HEURES
            elif c.column in colonnes_pct:
                c.number_format = FORMAT_PCT


def _total(feuille, libelle: str, colonnes: list[int], derniere_ligne: int) -> None:
    """Ligne de total : =SOMME(...) sur chaque colonne demandée (une formule, pas un nombre)."""
    ligne = derniere_ligne + 1
    feuille.cell(row=ligne, column=1, value=libelle).font = GRAS
    for col in colonnes:
        lettre = get_column_letter(col)
        c = feuille.cell(row=ligne, column=col, value=f"=SUM({lettre}2:{lettre}{derniere_ligne})")
        c.font = GRAS
        c.number_format = FORMAT_HEURES


def construire(p: rapports.Periode) -> Workbook:
    classeur = Workbook()
    classeur.remove(classeur.active)
    synthese = rapports.synthese(p)
    dossiers = rapports.dossiers(p)

    # 1. Synthèse ---------------------------------------------------------------------------
    f = _feuille(
        classeur,
        "Synthèse",
        ["Personne", "Heures effectives", "Heures prévues", "% du prévu", "Jours travaillés"],
        [28, 18, 16, 12, 16],
    )
    for i, e in enumerate(synthese["employes"], start=2):
        f.append(
            [
                e["employe"],
                _heures(e["effectif_s"]),
                _heures(e["prevu_s"]),
                None,
                e["jours_travailles"],
            ]
        )
        f.cell(row=i, column=4, value=f'=IF(C{i}=0,"",B{i}/C{i})')
    n = len(synthese["employes"]) + 1
    if n > 1:
        _total(f, "Total", [2, 3, 5], n)
        f.cell(row=n + 1, column=4, value=f'=IF(C{n + 1}=0,"",B{n + 1}/C{n + 1})').font = GRAS
        f.cell(row=n + 1, column=4).number_format = FORMAT_PCT
    _formater(f, colonnes_heures=(2, 3), colonnes_pct=(4,))
    f.cell(
        row=n + 3,
        column=1,
        value=(
            f"Période du {p.debut:%d/%m/%Y} au {p.fin:%d/%m/%Y} — GI-SUIVI, "
            f"exporté le {timezone.localdate():%d/%m/%Y}"
        ),
    )

    # 2. Dossiers -----------------------------------------------------------------------------
    personnes = sorted({e["employe"] for d in dossiers["dossiers"] for e in d["par_employe"]})
    f = _feuille(
        classeur,
        "Dossiers",
        ["Code", "Nom", "Statut", "Heures", *personnes],
        [18, 36, 10, 10] + [14] * len(personnes),
    )
    for d in dossiers["dossiers"]:
        par_nom = {e["employe"]: _heures(e["duree_s"]) for e in d["par_employe"]}
        f.append(
            [
                d["code"],
                d["nom"],
                d["statut"],
                _heures(d["duree_s"]),
                *[par_nom.get(pn, 0) for pn in personnes],
            ]
        )
    n = len(dossiers["dossiers"]) + 1
    if n > 1:
        _total(f, "Total dossiers", [4, *range(5, 5 + len(personnes))], n)
    f.append(["À classer", "", "", _heures(dossiers["a_classer_s"])])
    f.append(["Brouillons", "", "", _heures(dossiers["brouillon_s"])])
    f.append(["Sans fichier", "", "", _heures(dossiers["sans_fichier_s"])])
    _formater(f, colonnes_heures=tuple(range(4, 5 + len(personnes))))

    # 3. Journées -----------------------------------------------------------------------------
    f = _feuille(
        classeur,
        "Journées",
        [
            "Personne",
            "Jour",
            "Heures",
            "Prévu",
            "% du prévu",
            "Arrivée",
            "Départ",
            "Amplitude",
            "Occupation",
        ],
        [28, 12, 10, 10, 11, 9, 9, 11, 11],
    )
    ligne = 2
    for e in synthese["employes"]:
        for j in e["journees"]:
            f.append(
                [
                    e["employe"],
                    j["jour"],
                    _heures(j["effectif_s"]),
                    _heures(j["prevu_s"]),
                    None,
                    j["arrivee"],
                    j["depart"],
                    _heures(j["amplitude_s"]),
                    None,
                ]
            )
            f.cell(row=ligne, column=5, value=f'=IF(D{ligne}=0,"",C{ligne}/D{ligne})')
            f.cell(row=ligne, column=9, value=f'=IF(H{ligne}=0,"",C{ligne}/H{ligne})')
            ligne += 1
    if ligne > 2:
        _total(f, "Total", [3, 4, 8], ligne - 1)
    _formater(f, colonnes_heures=(3, 4, 8), colonnes_pct=(5, 9))

    # 4. Fichiers -----------------------------------------------------------------------------
    f = _feuille(
        classeur,
        "Fichiers",
        ["Personne", "Fichier", "Chemin", "Dossier", "Classement", "Heures"],
        [28, 32, 60, 18, 12, 10],
    )
    debut, fin = rapports._bornes(p)
    lignes = (
        Segment.objects.filter(debut__gte=debut, debut__lt=fin, etat=Segment.Etat.ACTIF)
        .exclude(fichier="", chemin="")
        .values(
            "employe__nom_affiche",
            "employe__login",
            "fichier",
            "chemin",
            "dossier__code",
            "statut_classement",
        )
        .annotate(duree_s=Sum("duree_s"))
        .order_by("-duree_s")
    )
    for ligne_f in lignes:
        f.append(
            [
                ligne_f["employe__nom_affiche"] or ligne_f["employe__login"],
                ligne_f["fichier"],
                ligne_f["chemin"],
                ligne_f["dossier__code"] or "",
                ligne_f["statut_classement"],
                _heures(ligne_f["duree_s"]),
            ]
        )
    if f.max_row > 1:
        _total(f, "Total", [6], f.max_row)
    _formater(f, colonnes_heures=(6,))

    # 5. À classer ----------------------------------------------------------------------------
    a_classer = rapports.a_classer(p)
    f = _feuille(
        classeur,
        "À classer",
        ["Personne", "Fichier", "Chemin", "Heures", "Segments", "Dernière vue"],
        [28, 32, 60, 10, 10, 20],
    )
    for g in a_classer["groupes"]:
        f.append(
            [
                g["employe"],
                g["fichier"],
                g["chemin"],
                _heures(g["duree_s"]),
                g["segments"],
                g["dernier"][:16].replace("T", " "),
            ]
        )
    if a_classer["groupes"]:
        _total(f, "Total", [4, 5], len(a_classer["groupes"]) + 1)
    _formater(f, colonnes_heures=(4,))

    # 6. Postes -------------------------------------------------------------------------------
    f = _feuille(
        classeur,
        "Postes",
        ["Poste", "Alerte", "Agent", "Dernier envoi", "Muet (h ouvrées)", "Démarrages / semaine"],
        [22, 10, 10, 20, 16, 20],
    )
    for poste in rapports.etat_postes():
        f.append(
            [
                poste["nom"],
                poste["alerte"] or "sain",
                poste["version_agent"],
                (poste["dernier_envoi"] or "jamais")[:16].replace("T", " "),
                poste["muet_depuis_h_ouvrees"],
                poste["demarrages_semaine"],
            ]
        )
    return classeur


def nom_fichier(p: rapports.Periode) -> str:
    return f"GI-Suivi_{p.debut:%Y-%m-%d}_{p.fin:%Y-%m-%d}.xlsx"


def octets(p: rapports.Periode) -> bytes:
    tampon = BytesIO()
    construire(p).save(tampon)
    return tampon.getvalue()
