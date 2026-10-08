"""File de recalcul (A03)."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("suivi", "0003_employe_sid_facultatif")]
    operations = [
        migrations.CreateModel(
            name="DemandeRecalcul",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("motif", models.CharField(max_length=300)),
                ("creee_le", models.DateTimeField(auto_now_add=True, verbose_name="créée le")),
                (
                    "traitee_le",
                    models.DateTimeField(blank=True, null=True, verbose_name="traitée le"),
                ),
            ],
            options={
                "verbose_name": "demande de recalcul",
                "verbose_name_plural": "demandes de recalcul",
                "ordering": ["-creee_le"],
            },
        ),
    ]
