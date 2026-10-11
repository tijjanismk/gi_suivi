import json
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from suivi.models import DemandeRecalcul, Parametre, Racine

pytestmark = pytest.mark.django_db


def fichier(tmp_path, racines, lecteurs=None):
    p = tmp_path / "config.json"
    p.write_text(
        json.dumps({"racines": racines, "correspondance_lecteurs": lecteurs or {}}),
        encoding="utf-8",
    )
    return str(p)


def test_saisie_idempotente_et_recalcul(tmp_path):
    f = fichier(
        tmp_path,
        [
            {"chemin": r"\\AD-SERVEUR\ETUDES", "profondeur": 1},
            {"chemin": r"\\AD-SERVEUR\AMI", "profondeur": 4},
        ],
        {"H:": r"\\AD-SERVEUR\GIC"},
    )
    sortie = StringIO()
    call_command("suivi_racines", f, stdout=sortie)
    assert (
        "+ \\\\AD-SERVEUR\\ETUDES" in sortie.getvalue() and "Recalcul demandé" in sortie.getvalue()
    )
    assert Racine.objects.filter(active=True).count() == 2
    assert Racine.objects.get(chemin=r"\\AD-SERVEUR\AMI").profondeur == 4
    assert Parametre.objects.get(cle="correspondance_lecteurs").valeur == {
        "H:": r"\\AD-SERVEUR\GIC"
    }
    n = DemandeRecalcul.objects.count()
    assert n >= 1  # déposées par les signaux sur Racine
    # deuxième passage : rien ne change, pas de nouveau recalcul
    sortie = StringIO()
    call_command("suivi_racines", f, stdout=sortie)
    assert "= \\\\AD-SERVEUR\\ETUDES" in sortie.getvalue() and "Recalcul" not in sortie.getvalue()
    assert DemandeRecalcul.objects.count() == n


def test_lecteurs_modifies_rattachent_le_passe(tmp_path, employes, postes, racines):
    """Une mesure reçue en Q:\\… (lettre non déclarée) se rattache quand la lettre est déclarée."""
    import uuid
    from datetime import timedelta

    from django.core.management import call_command as cc
    from django.utils import timezone

    from suivi.models import Segment

    debut = timezone.now() - timedelta(hours=1)
    s = Segment.objects.create(
        employe=employes[0],
        poste=postes[0],
        debut=debut,
        fin=debut + timedelta(minutes=10),
        duree_s=600,
        etat="ACTIF",
        application="WINWORD.EXE",
        fichier="Sommaire.docx",
        chemin=r"Q:\2026-10\2026-SOMAPEP-001_recharge-nappe\Sommaire.docx",
        statut_classement="a_classer",
        lot_id=uuid.uuid4(),
    )
    DemandeRecalcul.objects.all().delete()
    racines_json = [{"chemin": r.chemin, "profondeur": r.profondeur} for r in racines]
    f = fichier(tmp_path, racines_json, {"Q:": r"\\AD-SERVEUR\GIC\AVIS\MALI"})
    sortie = StringIO()
    call_command("suivi_racines", f, stdout=sortie)
    assert "~ correspondance_lecteurs" in sortie.getvalue()
    assert DemandeRecalcul.objects.filter(motif__contains="lecteurs", traitee_le=None).exists()
    cc("suivi_recalculer", stdout=StringIO())
    s.refresh_from_db()
    assert s.statut_classement == "dossier" and s.dossier.code == "2026-SOMAPEP-001"
    # second passage : table inchangée, pas de nouvelle demande
    n = DemandeRecalcul.objects.count()
    sortie = StringIO()
    call_command("suivi_racines", f, stdout=sortie)
    assert "correspondance_lecteurs inchangée" in sortie.getvalue()
    assert DemandeRecalcul.objects.count() == n


def test_mise_a_jour_simulation_et_desactivation(tmp_path):
    Racine.objects.create(chemin=r"\\AD-SERVEUR\ETUDES", profondeur=2, active=False)
    Racine.objects.create(chemin=r"\\AD-SERVEUR\GIC\MISSIONS_EN_COURS", profondeur=1)
    f = fichier(tmp_path, [{"chemin": r"\\ad-serveur\ETUDES", "profondeur": 1}])
    sortie = StringIO()
    call_command("suivi_racines", f, "--simuler", stdout=sortie)
    assert "~ " in sortie.getvalue() and "Simulation" in sortie.getvalue()
    assert Racine.objects.get(chemin=r"\\AD-SERVEUR\ETUDES").profondeur == 2  # rien écrit
    call_command("suivi_racines", f, "--desactiver-les-autres", stdout=StringIO())
    etudes = Racine.objects.get(chemin=r"\\AD-SERVEUR\ETUDES")
    assert etudes.profondeur == 1 and etudes.active
    assert not Racine.objects.get(chemin=r"\\AD-SERVEUR\GIC\MISSIONS_EN_COURS").active


def test_fichier_invalide(tmp_path):
    with pytest.raises(CommandError):
        call_command("suivi_racines", str(tmp_path / "absent.json"), stdout=StringIO())
    vide = tmp_path / "vide.json"
    vide.write_text("{}", encoding="utf-8")
    with pytest.raises(CommandError):
        call_command("suivi_racines", str(vide), stdout=StringIO())
