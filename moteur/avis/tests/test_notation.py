"""ADR 0013 § 3 — note d'un avis : les quatre modes, note sûre et note possible, sans base.

Cas réels : la DP UNICEF LRPS-MLI-2026-9206428 (2 points par référence, 25 au-delà de 12) et
l'AMI SOMAPEP 09/2026/001 (critères 1, 2.1 et 3 de `docs/schema-donnees.md`).
"""

from decimal import Decimal

from moteur.avis.filtres import Piece, Preuve, Reference, lire_filtre
from moteur.avis.notation import Critere, Mode, Verdict, noter, noter_critere

D = Decimal
PROUVEES = (
    Piece("garde", auditee=True, bonne=True),
    Piece("signature", auditee=True, bonne=True),
    Piece("attestation", auditee=True, bonne=True),
)
A_AUDITER = (*PROUVEES[:2], Piece("attestation"))

UNICEF = Critere(
    "2",
    Mode.PAR_MISSION,
    plafond=D(25),
    points_par_mission=D(2),
    filtre=lire_filtre({"natures": ["CTR", "ETC"]}),
)


def ref(ident, annee=2020, pieces=PROUVEES, nature="CTR", intitule="Contrôle des forages"):
    code = f"GIC-HYD-{nature}-{ident:03}"
    domaines = frozenset({"HYD"})
    return Reference(
        ident, code, intitule, nature=nature, domaines=domaines, annee=annee, pieces=pieces
    )


def somapep(note_manuelle):
    """Critère 1 : 10 ans en hydraulique (30 points, 0 en dessous) ; 2.1 : deux études
    d'ouvrages de mobilisation des eaux, 2010-2025 (20 points chacune, plafond 40) ; 3 :
    organisation et moyens, notés à la main (10)."""
    etudes = {
        "natures": ["ETU", "ETC"],
        "annee_min": 2010,
        "annee_max": 2025,
        "mots_cles": ["barrage", "retenue", "digue", "seuil", "recharge", "impluvium"],
    }
    return [
        Critere(
            "1",
            Mode.ANCIENNETE,
            plafond=D(30),
            annees_seuil=10,
            points_socle=D(30),
            filtre=lire_filtre({"domaines": ["HYD"]}),
        ),
        Critere(
            "2.1",
            Mode.PAR_MISSION,
            plafond=D(40),
            points_par_mission=D(20),
            nb_min_missions=2,
            filtre=lire_filtre(etudes),
        ),
        Critere("3", Mode.MANUEL, plafond=D(10), note_manuelle=note_manuelle),
    ]


def test_unicef_deux_points_par_reference_plafond_25():
    for n, note in [(0, 0), (12, 24), (13, 25), (20, 25)]:
        res = noter_critere(UNICEF, [ref(i) for i in range(n)], 2026)
        assert res.note_sure == res.note_possible == note
    assert len(res.retenues) == 13 and res.en_jeu == [] and res.alertes == []


def test_note_sure_note_possible_et_pieces_en_jeu():
    refs = [ref(i) for i in range(10)] + [ref(10 + i, pieces=A_AUDITER) for i in range(5)]
    res = noter_critere(UNICEF, refs, 2026)
    assert (res.note_sure, res.note_possible) == (20, 25)
    assert [p.points for p in res.en_jeu] == [2, 2, 1]
    premiere = res.en_jeu[0]
    assert premiere.preuve == Preuve.A_AUDITER and premiere.manques[0].exigence == "attestation"


def test_verdict_au_seuil():
    refs = [ref(i) for i in range(10)] + [ref(10 + i, pieces=A_AUDITER) for i in range(5)]
    attendus = [(20, Verdict.ELIGIBLE), (22, Verdict.INCERTAIN), (26, Verdict.NON_ELIGIBLE)]
    for seuil, verdict in attendus:
        assert noter([UNICEF], refs, 2026, seuil=D(seuil)).verdict == verdict
    sans_seuil = noter([UNICEF], refs, 2026)
    assert sans_seuil.verdict is None and [p.points for p in sans_seuil.en_jeu] == [2, 2, 1]


def test_somapep_eligible():
    refs = [
        ref(1, 2013, nature="ETU", intitule="Étude de la digue filtrante de Kodougou"),
        ref(2, 2023, nature="ETU", intitule="Études APD des micro-barrages de Farabaleda"),
        ref(3, 2019, intitule="Contrôle des travaux du seuil de Mougui"),  # contrôle : pas au 2.1
    ]
    res = noter(somapep(D(10)), refs, 2026, seuil=D(75))
    assert [r.note_sure for r in res.criteres] == [30, 40, 10]
    assert res.note_sure == 80 and res.verdict == Verdict.ELIGIBLE
    assert [c.reference.ident for c in res.criteres[1].retenues] == [2, 1]


def test_somapep_trop_recent_et_note_manuelle_absente():
    refs = [
        ref(2, 2023, nature="ETU", intitule="Études APD des micro-barrages de Farabaleda"),
        ref(4, 2017, nature="ETU", intitule="Étude du barrage de Sélingué"),
    ]
    res = noter(somapep(None), refs, 2026, seuil=D(75))
    assert [r.note_sure for r in res.criteres] == [0, 40, 0]
    assert res.criteres[0].alertes == ["9 an(s) prouvé(s) pour 10 demandé(s)"]
    assert res.criteres[2].alertes == ["note à saisir à la main"]
    assert res.verdict == Verdict.NON_ELIGIBLE


def test_somapep_une_seule_etude_et_anciennete_a_auditer():
    refs = [
        ref(1, 2012, pieces=A_AUDITER, nature="ETU", intitule="Étude de la digue de Kodougou"),
        ref(5, 2018),
    ]
    anciennete, etudes, _ = (noter_critere(c, refs, 2026) for c in somapep(D(10)))
    assert (anciennete.note_sure, anciennete.note_possible) == (0, 30)
    assert [(p.code, p.points) for p in anciennete.en_jeu] == [("GIC-HYD-ETU-001", 30)]
    assert (etudes.note_sure, etudes.note_possible) == (0, 20)
    assert etudes.alertes == ["0 référence(s) prouvée(s) et 1 possible(s) pour 2 demandée(s)"]


def test_forfait_partage_entre_les_references_qui_manquent():
    agence = Critere("4", Mode.FORFAIT, plafond=D(10), nb_min_missions=2)
    res = noter_critere(agence, [ref(1), ref(2, pieces=A_AUDITER)], 2026)
    assert (res.note_sure, res.note_possible) == (0, 10)
    assert [(p.code, p.points) for p in res.en_jeu] == [("GIC-HYD-CTR-002", 10)]
    seule = noter_critere(agence, [ref(1)], 2026)
    assert seule.en_jeu == [] and seule.alertes == ["1 référence(s) prouvée(s) pour 2 demandée(s)"]
    assert noter_critere(agence, [ref(1), ref(2)], 2026).note_sure == 10


def test_note_manuelle_plafonnee():
    res = noter_critere(Critere("3", Mode.MANUEL, plafond=D(10), note_manuelle=D(12)), [], 2026)
    assert res.note_sure == res.note_possible == 10
    assert res.alertes == ["note saisie au-dessus du plafond, ramenée à 10"]
