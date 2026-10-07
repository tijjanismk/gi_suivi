"""Paramètres par défaut du dossier GI-SUIVI. Les racines ne sont pas posées ici : elles relèvent
de la décision P05 (racines de classement) et se saisissent dans l'admin."""

from django.db import migrations

PARAMETRES = [
    ("seuil_inactivite_s", 300, "Au-delà, le temps depuis la dernière action est retiré (secondes)."),
    ("intervalle_s", 5, "Intervalle d'observation de l'agent (secondes)."),
    ("retention_mois", 24, "Durée de conservation des segments (mois)."),
    ("heures_prevues_semaine", 40, "Heures prévues par défaut pour un nouvel employé."),
    ("correspondance_lecteurs", {"H:": "\\\\AD-SERVEUR\\GIC"}, "Lettre de lecteur réseau → chemin UNC."),
]


def poser(apps, schema_editor):
    Parametre = apps.get_model("suivi", "Parametre")
    for cle, valeur, description in PARAMETRES:
        Parametre.objects.get_or_create(cle=cle, defaults={"valeur": valeur, "description": description})


def retirer(apps, schema_editor):
    apps.get_model("suivi", "Parametre").objects.filter(cle__in=[p[0] for p in PARAMETRES]).delete()


class Migration(migrations.Migration):
    dependencies = [("suivi", "0001_modeles_suivi")]
    operations = [migrations.RunPython(poser, retirer)]
