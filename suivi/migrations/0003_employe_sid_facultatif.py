"""L'agent 0.2 n'envoie pas encore le SID : l'employé est reconnu par son login en attendant."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("suivi", "0002_parametres_par_defaut")]
    operations = [
        migrations.AlterField(
            model_name="employe",
            name="sid_ad",
            field=models.CharField(
                blank=True, max_length=100, null=True, unique=True, verbose_name="SID AD"
            ),
        ),
    ]
