from datetime import date, datetime
from decimal import Decimal

from moteur.suivi.indicateurs import journees, prevu_du_jour, synthese
from moteur.suivi.types import Etat, Segment

LUNDI = date(2026, 10, 5)


def seg(debut, fin, etat=Etat.ACTIF):
    return Segment(debut, fin, "WINWORD.EXE", None, None, etat)


def h(jour, hh, mm=0):
    return datetime(jour.year, jour.month, jour.day, hh, mm)


def test_journee_vide_sans_division_par_zero():
    (j,) = journees([], LUNDI, LUNDI, 40)
    assert j.effectif_s == 0 and j.arrivee is None and j.depart is None
    assert j.amplitude_s == 0 and j.occupation_pct is None
    assert j.prevu_s == 8 * 3600 and j.prevu_pct == Decimal("0.0")


def test_heures_effectives_arrivee_depart_amplitude_occupation():
    s = [seg(h(LUNDI, 8), h(LUNDI, 12)), seg(h(LUNDI, 14), h(LUNDI, 17))]
    (j,) = journees(s, LUNDI, LUNDI, 40)
    assert j.effectif_s == 7 * 3600
    assert j.arrivee == h(LUNDI, 8) and j.depart == h(LUNDI, 17)
    assert j.amplitude_s == 9 * 3600
    assert j.occupation_pct == Decimal("77.8")  # 7 h sur 9 h
    assert j.prevu_pct == Decimal("87.5")  # 7 h sur 8 h


def test_segments_inactifs_ecartes():
    s = [seg(h(LUNDI, 8), h(LUNDI, 9)), seg(h(LUNDI, 9), h(LUNDI, 10), Etat.INACTIF)]
    (j,) = journees(s, LUNDI, LUNDI, 40)
    assert j.effectif_s == 3600 and j.depart == h(LUNDI, 9)


def test_segment_a_cheval_sur_minuit_coupe_en_deux_jours():
    mardi = date(2026, 10, 6)
    j1, j2 = journees([seg(h(LUNDI, 23), h(mardi, 1))], LUNDI, mardi, 40)
    assert j1.effectif_s == 3600 and j1.depart == datetime(2026, 10, 6, 0, 0)
    assert j2.effectif_s == 3600 and j2.arrivee == datetime(2026, 10, 6, 0, 0)


def test_heures_prevues_a_zero_pas_de_pourcentage():
    (j,) = journees([seg(h(LUNDI, 8), h(LUNDI, 9))], LUNDI, LUNDI, 0)
    assert j.prevu_s == 0 and j.prevu_pct is None


def test_week_end_rien_de_prevu():
    samedi = date(2026, 10, 10)
    assert prevu_du_jour(samedi, 40) == 0
    (j,) = journees([seg(h(samedi, 9), h(samedi, 10))], samedi, samedi, 40)
    assert j.effectif_s == 3600 and j.prevu_pct is None


def test_semaine_avec_jour_ferie():
    vendredi = date(2026, 10, 9)
    s = synthese([], LUNDI, date(2026, 10, 11), 40, jours_feries=frozenset({vendredi}))
    assert s.prevu_s == 4 * 8 * 3600  # lundi à jeudi
    assert len(s.journees) == 7


def test_synthese_sur_la_periode():
    s = [seg(h(LUNDI, 8), h(LUNDI, 16)), seg(h(date(2026, 10, 7), 8), h(date(2026, 10, 7), 12))]
    r = synthese(s, LUNDI, date(2026, 10, 9), 40)
    assert r.effectif_s == 12 * 3600 and r.prevu_s == 40 * 3600
    assert r.prevu_pct == Decimal("30.0") and r.jours_travailles == 2


def test_periode_sans_rien_de_prevu():
    samedi, dimanche = date(2026, 10, 10), date(2026, 10, 11)
    assert synthese([], samedi, dimanche, 40).prevu_pct is None


def test_segment_de_duree_nulle_ou_inverse_ignore():
    s = [seg(h(LUNDI, 8), h(LUNDI, 8)), seg(h(LUNDI, 9), h(LUNDI, 8))]
    (j,) = journees(s, LUNDI, LUNDI, 40)
    assert j.effectif_s == 0 and j.arrivee is None
