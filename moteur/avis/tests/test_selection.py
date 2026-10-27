"""ADR 0013 § 3 — sélection des références d'un critère, sans base."""

from moteur.avis.filtres import Piece, Preuve, Reference, lire_filtre
from moteur.avis.selection import selectionner

PROUVEES = (
    Piece("garde", auditee=True, bonne=True),
    Piece("signature", auditee=True, bonne=True),
    Piece("attestation", auditee=True, bonne=True),
)
A_AUDITER = (*PROUVEES[:2], Piece("attestation"))


def ref(ident, annee, intitule="Contrôle des forages", pieces=PROUVEES, **kw):
    code = f"GIC-AEP-CTR-{ident:03}"
    return Reference(ident, code, intitule, nature="CTR", annee=annee, pieces=pieces, **kw)


def test_classement_preuve_mots_cles_puis_annee():
    refs = [
        ref(1, 2024, pieces=()),
        ref(2, 2018, pieces=A_AUDITER),
        ref(3, 2017),
        ref(4, 2023),
        ref(5, 2016, "Contrôle des forages et des latrines"),
    ]
    selection = selectionner(lire_filtre({"mots_cles": ["forage", "latrine"]}), refs)
    assert [c.reference.ident for c in selection] == [5, 4, 3, 2, 1]
    assert [(c.sure, c.possible) for c in selection[3:]] == [(False, True), (False, False)]
    assert selection[0].mots_cles == 2 and selection[4].preuve == Preuve.MANQUANTE


def test_absorbee_jamais_retenue_et_choix_d_une_personne():
    refs = [ref(1, 2020), ref(2, 2021, absorbee=True), ref(3, 2010), ref(4, 2022)]
    choix = {2: True, 3: True, 4: False}  # 3 forcée hors des années, 4 exclue
    selection = selectionner(lire_filtre({"annee_min": 2016}), refs, choix)
    assert [(c.reference.ident, c.forcee) for c in selection] == [(1, False), (3, True)]


def test_sans_justificatif_exige_tout_compte():
    filtre = lire_filtre({"pieces_completes_requises": False})
    (c,) = selectionner(filtre, [ref(1, 2020, pieces=())])
    assert c.preuve == Preuve.MANQUANTE and c.sure and c.possible
