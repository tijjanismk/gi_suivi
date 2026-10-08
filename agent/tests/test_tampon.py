"""G03 — tampon SQLite de l'agent : coupure simulée, rien de perdu, rien en double."""

from datetime import datetime, timedelta

from gisuivi_agent.tampon import Tampon

from moteur.suivi.types import Etat, Segment

T0 = datetime(2026, 10, 7, 9, 0, 0)


def segments(n: int, debut: datetime = T0) -> list[Segment]:
    return [
        Segment(
            debut + timedelta(minutes=5 * i),
            debut + timedelta(minutes=5 * (i + 1)),
            "WINWORD.EXE",
            "rapport.docx",
            r"\\srv\gic\MISSIONS_EN_COURS\GIC-HYD-ETU-052_x\rapport.docx",
            Etat.ACTIF,
        )
        for i in range(n)
    ]


def test_un_lot_puis_acquittement(tmp_path):
    t = Tampon(tmp_path / "tampon.db")
    t.ajouter(segments(3))
    assert t.en_attente() == 3
    lot_id, lignes = t.preparer_lot()
    assert len(lignes) == 3 and lignes[0]["application"] == "WINWORD.EXE"
    assert lignes[0]["debut"] == T0.isoformat() and lignes[0]["duree_s"] == 300
    t.acquitter(lot_id)
    assert t.en_attente() == 0 and t.preparer_lot() is None


def test_coupure_reseau_le_meme_lot_est_represente_pas_un_autre(tmp_path):
    # L'envoi échoue : au prochain tour, le tampon rend LE MÊME lot (même lot_id) ; le serveur,
    # idempotent par lot_id, ne peut donc jamais compter deux fois.
    t = Tampon(tmp_path / "tampon.db")
    t.ajouter(segments(4))
    lot_a, lignes_a = t.preparer_lot()
    lot_b, lignes_b = t.preparer_lot()
    assert lot_a == lot_b and lignes_a == lignes_b
    # des segments arrivés pendant la coupure attendent le lot suivant
    t.ajouter(segments(2, T0 + timedelta(hours=1)))
    lot_c, lignes_c = t.preparer_lot()
    assert lot_c == lot_a and len(lignes_c) == 4  # le lot en cours n'absorbe pas les nouveaux
    t.acquitter(lot_a)
    lot_d, lignes_d = t.preparer_lot()
    assert lot_d != lot_a and len(lignes_d) == 2
    t.acquitter(lot_d)
    assert t.en_attente() == 0


def test_rien_de_perdu_entre_deux_demarrages(tmp_path):
    chemin = tmp_path / "tampon.db"
    t = Tampon(chemin)
    t.ajouter(segments(5))
    lot_id, _ = t.preparer_lot()
    del t  # l'agent s'arrête (session fermée) avant l'acquittement
    t2 = Tampon(chemin)
    assert t2.en_attente() == 5
    lot_bis, lignes = t2.preparer_lot()
    assert lot_bis == lot_id and len(lignes) == 5  # même lot : toujours idempotent côté serveur


def test_lot_borne(tmp_path):
    t = Tampon(tmp_path / "tampon.db")
    t.ajouter(segments(7))
    lot_1, lignes = t.preparer_lot(max_segments=5)
    assert len(lignes) == 5
    t.acquitter(lot_1)
    lot_2, lignes = t.preparer_lot(max_segments=5)
    assert len(lignes) == 2 and lot_2 != lot_1


def test_purge_ne_touche_que_l_acquitte_ancien(tmp_path):
    t = Tampon(tmp_path / "tampon.db")
    t.ajouter(segments(2, datetime(2026, 1, 1, 9)))  # vieux
    lot_id, _ = t.preparer_lot()
    t.acquitter(lot_id)
    t.ajouter(segments(1))  # récent, non envoyé
    t.purger(jours=7)
    assert t.en_attente() == 1
    assert t.resume_du_jour(datetime(2026, 1, 1).date())["total_s"] == 0  # purgé
    assert t.resume_du_jour(T0.date())["total_s"] == 300


def test_etat_cle_valeur(tmp_path):
    t = Tampon(tmp_path / "tampon.db")
    assert t.lire_etat("demarrages") is None
    t.ecrire_etat("demarrages", "3")
    t.ecrire_etat("demarrages", "4")
    assert t.lire_etat("demarrages") == "4"
