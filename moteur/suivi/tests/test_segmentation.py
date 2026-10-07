from datetime import datetime, timedelta

from moteur.suivi.segmentation import Segmenteur, filtrer_actifs, segmenter
from moteur.suivi.types import Etat, EtatSession, Observation, Parametres

T0 = datetime(2026, 10, 7, 9, 0, 0)


def obs(
    sec,
    app="WINWORD.EXE",
    fichier="rapport.docx",
    chemin=r"\\srv\gic\MISSIONS_EN_COURS\GIC-HYD-ETU-052_x\rapport.docx",
    inactif=0,
    session=EtatSession.ACTIVE,
    fen=1,
):
    return Observation(T0 + timedelta(seconds=sec), app, fichier, chemin, inactif, session, fen)


def suite(secs, **kw):
    return [obs(s, **kw) for s in secs]


def test_observations_identiques_fusionnees_en_un_segment():
    segs = list(segmenter(suite(range(0, 60, 5))))
    actifs = filtrer_actifs(segs)
    assert len(actifs) == 1
    assert actifs[0].duree_s == 55


def test_changement_de_fichier_clot_le_segment():
    o = suite(range(0, 30, 5)) + suite(
        range(30, 60, 5), fichier="devis.xlsx", app="EXCEL.EXE", chemin=r"c:\x\devis.xlsx"
    )
    actifs = filtrer_actifs(segmenter(o))
    assert [s.fichier for s in actifs] == ["rapport.docx", "devis.xlsx"]


def test_pause_de_quatre_minutes_est_comptee():
    # inactivité croissante jusqu'à 240 s puis reprise : sous le seuil, rien n'est retiré
    o = [obs(s, inactif=s) for s in range(0, 245, 5)] + [obs(250, inactif=0)]
    actifs = filtrer_actifs(segmenter(o))
    assert len(actifs) == 1
    assert actifs[0].duree_s == 250


def test_pause_de_six_minutes_est_retiree_depuis_la_derniere_action():
    # actif 0-60 s, puis inactif pendant 360 s (dernière action à t=60), reprise à t=425
    o = (
        suite(range(0, 65, 5))
        + [obs(60 + s, inactif=s) for s in range(5, 365, 5)]
        + suite(range(425, 455, 5))
    )
    segs = list(segmenter(o))
    actifs = filtrer_actifs(segs)
    inactifs = [s for s in segs if s.etat == Etat.INACTIF]
    assert len(actifs) == 2
    assert actifs[0].fin == T0 + timedelta(seconds=60)  # tronqué à la dernière action réelle
    assert len(inactifs) == 1 and inactifs[0].debut == T0 + timedelta(seconds=60)


def test_verrouillage_est_inactif():
    o = (
        suite(range(0, 30, 5))
        + suite(range(30, 90, 5), session=EtatSession.VERROUILLEE)
        + suite(range(90, 120, 5))
    )
    segs = list(segmenter(o))
    # 0-30 actif (l'intervalle 25-30 revient à l'observation de 25), 30-90 verrouillé, 90-115 actif
    assert sum(s.duree_s for s in filtrer_actifs(segs)) == 30 + 25
    assert sum(s.duree_s for s in segs if s.etat == Etat.INACTIF) == 60


def test_cloture_forcee_a_cinq_minutes():
    o = suite(range(0, 605, 5))
    actifs = filtrer_actifs(segmenter(o))
    assert len(actifs) == 2 or len(actifs) == 3  # 300 + 300 (+ reste)
    assert all(s.duree_s <= 300 for s in actifs)
    assert sum(s.duree_s for s in actifs) == 600


def test_brouillon_puis_enregistrement_fusionnes():
    o = suite(range(0, 30, 5), fichier="Document1", chemin=None) + suite(
        range(30, 60, 5), fichier="Courrier.docx", chemin=r"c:\x\Courrier.docx"
    )
    actifs = filtrer_actifs(segmenter(o))
    assert len(actifs) == 1
    assert actifs[0].fichier == "Courrier.docx" and actifs[0].debut == T0


def test_chemin_trouve_avec_retard_fusionne():
    # Revit : titre sans nom, le chemin arrive à l'observation suivante (fichiers ouverts)
    revit = dict(app="Revit.exe", fichier=None, chemin=None)
    o = suite(range(0, 5, 5), **revit) + suite(
        range(5, 60, 5), app="Revit.exe", fichier="digue.rvt", chemin=r"c:\x\digue.rvt"
    )
    actifs = filtrer_actifs(segmenter(o))
    assert len(actifs) == 1
    assert actifs[0].chemin == r"c:\x\digue.rvt" and actifs[0].debut == T0


def test_brouillon_autre_fenetre_non_fusionne():
    o = suite(range(0, 30, 5), fichier="Document1", chemin=None, fen=1) + suite(
        range(30, 60, 5), fichier="Courrier.docx", chemin=r"c:\x\Courrier.docx", fen=2
    )
    assert len(filtrer_actifs(segmenter(o))) == 2


def test_navigateur_sans_titre():
    o = suite(
        range(0, 30, 5), app="chrome.exe", fichier="Banque mondiale - appels d'offres", chemin=None
    )
    actifs = filtrer_actifs(segmenter(o))
    assert actifs[0].fichier is None and actifs[0].chemin is None


def test_navigateur_garde_le_nom_d_un_pdf_seulement():
    o = suite(range(0, 30, 5), app="chrome.exe", fichier="TDR_052.pdf", chemin=None)
    actifs = filtrer_actifs(segmenter(o))
    assert actifs[0].fichier == "TDR_052.pdf" and actifs[0].chemin is None


def test_fichier_technique_ignore_mais_application_comptee():
    o = suite(range(0, 30, 5), fichier="~$rapport.docx")
    actifs = filtrer_actifs(segmenter(o))
    assert actifs[0].fichier is None and actifs[0].application == "WINWORD.EXE"


def test_changements_de_fenetre_ne_perdent_aucun_intervalle():
    # explorer, Word, Excel, explorer, Word : 4 changements, 100 s observées de bout en bout
    o = (
        suite(range(0, 20, 5), app="explorer.exe", fichier=None, chemin=None)
        + suite(range(20, 40, 5))
        + suite(range(40, 60, 5), app="EXCEL.EXE", fichier="devis.xlsx", chemin=r"c:\x\devis.xlsx")
        + suite(range(60, 80, 5), app="explorer.exe", fichier=None, chemin=None)
        + suite(range(80, 105, 5))
    )
    actifs = filtrer_actifs(segmenter(o))
    assert sum(s.duree_s for s in actifs) == 100
    assert all(a.fin == b.debut for a, b in zip(actifs, actifs[1:], strict=False))


def test_passage_bref_vu_une_seule_fois_est_garde():
    # Word vu à une seule observation entre explorer et claude (cas réel du 07/10 à 17:17:21)
    o = (
        suite(range(0, 20, 5), app="explorer.exe", fichier=None, chemin=None)
        + [obs(20)]
        + suite(range(25, 45, 5), app="claude.exe", fichier=None, chemin=None)
    )
    actifs = filtrer_actifs(segmenter(o))
    assert [(s.application, s.duree_s) for s in actifs] == [
        ("explorer.exe", 20),
        ("WINWORD.EXE", 5),
        ("claude.exe", 15),
    ]


def test_veille_est_inactive_comme_le_verrouillage():
    o = (
        suite(range(0, 30, 5))
        + suite(range(30, 90, 5), session=EtatSession.VEILLE)
        + suite(range(90, 120, 5))
    )
    segs = list(segmenter(o))
    assert sum(s.duree_s for s in filtrer_actifs(segs)) == 30 + 25
    assert sum(s.duree_s for s in segs if s.etat == Etat.INACTIF) == 60


def test_reprise_apres_longue_pause_ouvre_un_nouveau_segment_actif():
    # dernière action à t=60 ; inactif jusqu'à 425 ; reprise : le segment repart de 425, pas de 60
    o = (
        suite(range(0, 65, 5))
        + [obs(60 + s, inactif=s) for s in range(5, 365, 5)]
        + suite(range(425, 455, 5))
    )
    actifs = filtrer_actifs(segmenter(o))
    assert actifs[1].debut == T0 + timedelta(seconds=425)
    assert sum(s.duree_s for s in actifs) == 60 + 25


def test_segments_contigus_couvrent_toute_la_periode_observee():
    o = (
        suite(range(0, 30, 5))
        + suite(range(30, 90, 5), session=EtatSession.VERROUILLEE)
        + suite(range(90, 130, 5), app="EXCEL.EXE", fichier="devis.xlsx", chemin=r"c:\x\devis.xlsx")
    )
    segs = sorted(segmenter(o), key=lambda s: s.debut)
    assert all(a.fin == b.debut for a, b in zip(segs, segs[1:], strict=False))
    assert segs[0].debut == T0 and segs[-1].fin == T0 + timedelta(seconds=125)


def test_fichier_technique_bref_ne_coupe_pas_l_application():
    # ~$rapport.docx est vu comme « Word sans fichier » : même application, pas de fichier fantôme
    o = suite(range(0, 30, 5), fichier="~$rapport.docx", chemin=None) + suite(
        range(30, 60, 5), fichier=None, chemin=None
    )
    actifs = filtrer_actifs(segmenter(o))
    assert len(actifs) == 1 and actifs[0].fichier is None and actifs[0].duree_s == 55


def test_observation_isolee_ne_produit_rien_d_actif():
    assert filtrer_actifs(segmenter([obs(0)])) == []


def test_segmenteur_incremental_rend_les_segments_clos():
    s = Segmenteur(Parametres(duree_max_segment_s=60))
    rendus = []
    for o in suite(range(0, 130, 5)):
        rendus += s.observer(o)
    rendus += s.clore_tout(T0 + timedelta(seconds=125))
    assert sum(x.duree_s for x in filtrer_actifs(rendus)) == 125
