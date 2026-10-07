from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from django.db import IntegrityError
from django.utils import timezone

from conftest import PROJET_052
from moteur.suivi.classement import classer_chemin
from suivi.models import Dossier, Parametre, RegleException, Segment
from suivi.services import correspondance_lecteurs, exceptions_moteur, parametre, racines_moteur

pytestmark = pytest.mark.django_db


def test_parametres_par_defaut_poses_par_la_migration():
    assert parametre("seuil_inactivite_s") == 300
    assert parametre("retention_mois") == 24
    assert correspondance_lecteurs() == {"H:": r"\\AD-SERVEUR\GIC"}
    assert parametre("inconnu", "défaut") == "défaut"


def test_chemin_du_dossier_normalise_une_seule_ecriture(racines):
    d = Dossier.objects.create(
        nom="x", chemin_windows=r"\\AD-SERVEUR\GIC\MISSIONS_EN_COURS\Études_X"
    )
    assert d.chemin_windows == r"\\ad-serveur\gic\missions_en_cours\etudes_x"
    with pytest.raises(IntegrityError):
        Dossier.objects.create(
            nom="doublon", chemin_windows=r"\\ad-serveur\GIC\Missions_en_cours\ETUDES_X"
        )


def test_racines_et_exceptions_passent_au_moteur(dossiers):
    RegleException.objects.create(
        motif=r"C:\Users\x\Desktop\TDR", type="prefixe", dossier=dossiers[0]
    )
    r, e = racines_moteur(), exceptions_moteur()
    c = classer_chemin(PROJET_052 + r"\a.docx", r, correspondance_lecteurs(), e)
    assert c.code == "GIC-HYD-ETU-052"
    c2 = classer_chemin(r"C:\Users\x\Desktop\TDR\b.pdf", r, correspondance_lecteurs(), e)
    assert (
        c2.par_exception
        and c2.code == "GIC-HYD-ETU-052"
        and c2.dossier_chemin == dossiers[0].chemin_windows
    )


def test_racine_inactive_ignoree(racines):
    racines[1].active = False
    racines[1].save()
    assert [r.chemin for r in racines_moteur()] == [racines[0].chemin]


def test_segment_fin_avant_debut_refuse(employes, postes):
    t = timezone.make_aware(datetime(2026, 10, 7, 9, 0))
    with pytest.raises(IntegrityError):
        Segment.objects.create(
            employe=employes[0],
            poste=postes[0],
            debut=t,
            fin=t - timedelta(seconds=1),
            duree_s=0,
            etat="ACTIF",
            application="x",
            lot_id=uuid4(),
        )


def test_parametre_valeur_json():
    Parametre.objects.create(cle="jours_feries_2026", valeur=["2026-01-01", "2026-03-26"])
    assert parametre("jours_feries_2026")[1] == "2026-03-26"
