"""Attribution des codes de référence (ADR 0008 § 2)."""

import pytest

from moteur.references.codes import decomposer, prochain_code


def test_decomposer():
    assert decomposer("GIC-HYD-ETU-043") == ("HYD", "ETU", 43)
    assert decomposer(" gic-aep-ctr-1003 ") == ("AEP", "CTR", 1003)
    assert decomposer("AQA-ETU-001") is None and decomposer("") is None


def test_prochain_code_de_la_serie():
    existants = ["GIC-HYD-ETU-043", "GIC-HYD-ETU-007", "GIC-HYD-CTR-090", "GIC-AEP-ETU-120", "XX"]
    assert prochain_code("HYD", "ETU", existants) == "GIC-HYD-ETU-044"
    assert prochain_code("hyd", "ctr", existants) == "GIC-HYD-CTR-091"
    assert prochain_code("BAT", "ETC", existants) == "GIC-BAT-ETC-001"  # série vide
    assert prochain_code("HYD", "ETU", ["GIC-HYD-ETU-999"]) == "GIC-HYD-ETU-1000"
    with pytest.raises(ValueError):
        prochain_code("HYD", "XYZ", existants)
    with pytest.raises(ValueError):
        prochain_code("HY", "ETU", existants)
