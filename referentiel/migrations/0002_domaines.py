"""Les sept domaines du code de référence (docs/schema-donnees.md). Libellés modifiables dans
l'administration ; celui d'AQA n'est écrit nulle part dans le dépôt : à préciser."""

from django.db import migrations

DOMAINES = [
    ("HYD", "Hydraulique"),
    ("AEP", "Alimentation en eau potable"),
    ("ENV", "Environnement"),
    ("BAT", "Bâtiment"),
    ("RTE", "Routes"),
    ("AQA", "AQA (libellé à préciser)"),
    ("VRD", "Voirie et réseaux divers"),
]


def creer(apps, schema_editor):
    Domaine = apps.get_model("referentiel", "Domaine")
    for i, (code, libelle) in enumerate(DOMAINES, start=1):
        Domaine.objects.get_or_create(code=code, defaults={"libelle": libelle, "ordre": i * 10})


def retirer(apps, schema_editor):
    Domaine = apps.get_model("referentiel", "Domaine")
    Domaine.objects.filter(code__in=[c for c, _ in DOMAINES]).delete()  # refusé s'il y a des missions


class Migration(migrations.Migration):
    dependencies = [("referentiel", "0001_referentiel_initial")]

    operations = [migrations.RunPython(creer, retirer)]
