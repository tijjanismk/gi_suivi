from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("experts", "0001_experts")]

    operations = [
        migrations.AddField(
            model_name="expert",
            name="a_verifier",
            field=models.TextField(
                blank=True,
                help_text="Un point par ligne, affiché sur la fiche ; l'effacer quand il est réglé",
                verbose_name="points à vérifier",
            ),
        ),
    ]
