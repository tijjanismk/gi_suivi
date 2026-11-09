# Dossier d'un AMI au modèle réel (AV14) : la rubrique D d'un critère et le destinataire de la
# lettre de manifestation d'intérêt.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("avis", "0004_critere_brouillon"),
    ]

    operations = [
        migrations.AddField(
            model_name="avis",
            name="destinataire",
            field=models.CharField(
                blank=True,
                help_text="Après « L'attention de », ex. Monsieur le Coordonnateur National de "
                "l'Unité de gestion du projet, Niamey ; vide : le maître d'ouvrage",
                max_length=300,
                verbose_name="destinataire de la lettre",
            ),
        ),
        migrations.AddField(
            model_name="avis",
            name="formule_appel",
            field=models.CharField(
                blank=True,
                help_text="Ex. Monsieur le Coordonnateur National ; vide : Madame, Monsieur",
                max_length=150,
                verbose_name="formule d'appel",
            ),
        ),
        migrations.AddField(
            model_name="critere",
            name="experience",
            field=models.CharField(
                blank=True,
                choices=[
                    ("generale", "expérience générale (liste de D.1)"),
                    ("specifique", "expérience spécifique (un D.2 à lui)"),
                    ("hors", "hors des expériences (pas de liste)"),
                ],
                help_text="Vide : d'après le texte (« expériences générales », « spécifiques ») "
                "ou le critère parent, sinon spécifique pour des points par référence",
                max_length=10,
                verbose_name="rubrique du dossier",
            ),
        ),
    ]
