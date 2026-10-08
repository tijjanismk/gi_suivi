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
