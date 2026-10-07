import json

from gisuivi_agent.config import _depuis_fichier, _racines

CONTENU = {"racines": [{"chemin": r"C:\Users\x\PROJETS", "profondeur": 1}]}


def test_fichier_avec_bom_est_lu(tmp_path):
    f = tmp_path / "config.json"
    f.write_bytes(b"\xef\xbb\xbf" + json.dumps(CONTENU).encode("utf-8"))
    avertissements: list[str] = []
    brut = _depuis_fichier(avertissements, (f,))
    assert avertissements == []
    assert _racines(brut["racines"])[0].chemin == r"C:\Users\x\PROJETS"


def test_fichier_sans_bom_est_lu(tmp_path):
    f = tmp_path / "config.json"
    f.write_text(json.dumps(CONTENU), encoding="utf-8")
    assert _depuis_fichier([], (f,)) == CONTENU


def test_fichier_illisible_est_signale_et_le_suivant_pris(tmp_path):
    casse = tmp_path / "casse.json"
    casse.write_text("{ pas du json", encoding="utf-8")
    bon = tmp_path / "bon.json"
    bon.write_text(json.dumps(CONTENU), encoding="utf-8")
    avertissements: list[str] = []
    assert _depuis_fichier(avertissements, (casse, bon)) == CONTENU
    assert len(avertissements) == 1 and "casse.json" in avertissements[0]


def test_aucun_fichier(tmp_path):
    avertissements: list[str] = []
    assert _depuis_fichier(avertissements, (tmp_path / "absent.json",)) == {}
    assert avertissements == []
