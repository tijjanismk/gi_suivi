"""ADR 0012 § 2 — années d'expérience et chevauchements d'affectations, sans base."""

from datetime import date

from moteur.experts.controles import Periode, alertes, annees_experience

AUJ = date(2026, 10, 22)


def test_annees_experience():
    assert annees_experience(2011, AUJ) == 15
    assert annees_experience(None, AUJ) is None and annees_experience(2030, AUJ) is None


def test_chevauchement_a_temps_plein():
    a = Periode(1, "GIC-HYD-ETU-033 (chef de mission)", date(2023, 1, 1), date(2023, 6, 30))
    b = Periode(2, "GIC-AEP-CTR-003 (chef de mission)", date(2023, 6, 1), date(2023, 12, 31))
    (x,) = alertes([a, b], AUJ)
    assert x.idents == (1, 2) and "pendant 30 jours (du 01/06/2023 au 30/06/2023)" in x.message


def test_temps_partiel_bout_a_bout_et_en_cours():
    a = Periode(1, "A", date(2023, 1, 1), date(2023, 6, 30))
    partiel = Periode(2, "B", date(2023, 3, 1), date(2023, 4, 1), plein_temps=False)
    suite = Periode(3, "C", date(2023, 7, 1), None)  # en cours : jusqu'à aujourd'hui
    assert alertes([a, partiel, suite], AUJ) == []
    autre = Periode(4, "D", date(2026, 10, 22), None)
    (x,) = alertes([suite, autre], AUJ)
    assert "pendant 1 jour " in x.message


def test_dates_incoherentes_et_periodes_sans_dates():
    (x,) = alertes(
        [Periode(1, "A", date(2024, 5, 1), date(2024, 1, 1)), Periode(2, "B", None, None)], AUJ
    )
    assert x.message == "A : la fin précède le début" and x.idents == (1,)
