from datetime import datetime

from moteur.suivi.types import Etat, Observation, Segment

T0 = datetime(2026, 10, 7, 9, 0, 0)


def test_observation_brouillon_si_nom_sans_chemin():
    assert Observation(T0, "WINWORD.EXE", "Document1", None, 0).est_brouillon
    assert not Observation(T0, "WINWORD.EXE", "a.docx", r"c:\x\a.docx", 0).est_brouillon
    assert not Observation(T0, "explorer.exe", None, None, 0).est_brouillon


def test_segment_vers_dict_pour_l_envoi():
    s = Segment(
        T0,
        datetime(2026, 10, 7, 9, 0, 30, 250000),
        "WINWORD.EXE",
        "a.docx",
        r"c:\x\a.docx",
        Etat.ACTIF,
        7,
    )
    d = s.vers_dict()
    assert d["debut"] == "2026-10-07T09:00:00" and d["fin"] == "2026-10-07T09:00:30.250000"
    assert d["etat"] == "ACTIF" and d["duree_s"] == 30.2
    assert d["fichier"] == "a.docx" and d["fenetre_id"] == 7
