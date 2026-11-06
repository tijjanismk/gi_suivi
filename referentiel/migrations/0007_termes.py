"""Termes des types d'ouvrages par pays (ADR 0019) : la table, puis la reprise de chaque synonyme
du tableau `TypeOuvrage.synonymes` en terme validé, sans pays, de portée « partout » et d'origine
« reprise ». Le tableau reste jusqu'à ce que plus aucun code ne le lise (migration suivante)."""

import re
import unicodedata

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def _cle(texte):
    """Copie figée de `moteur.references.doublons.normaliser` au 06/11/2026 : la migration
    garde le même résultat même si le moteur change ensuite."""
    t = unicodedata.normalize("NFKD", texte or "")
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t).split())


def reprendre(apps, schema_editor):
    TypeOuvrage = apps.get_model("referentiel", "TypeOuvrage")
    Terme = apps.get_model("referentiel", "Terme")
    for o in TypeOuvrage.objects.all():
        for s in o.synonymes or []:
            terme = (s or "").strip()
            if not terme:
                continue
            Terme.objects.get_or_create(
                type_ouvrage=o,
                cle=_cle(terme),
                pays="",
                defaults={
                    "terme": terme,
                    "portee": "partout",
                    "statut": "valide",
                    "origine": "reprise",
                    "propose_par": "migration referentiel 0007",
                },
            )


class Migration(migrations.Migration):
    dependencies = [
        ("referentiel", "0006_retrait_developpement_rural"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Terme",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("terme", models.CharField(help_text="Tel qu'il s'écrit dans les avis : accents, tiret, sigle.", max_length=120)),
                ("cle", models.CharField(editable=False, max_length=120, verbose_name="clé")),
                ("pays", models.CharField(blank=True, choices=[("Mali", "Mali"), ("Niger", "Niger"), ("Burkina Faso", "Burkina Faso"), ("Guinée", "Guinée"), ("Mauritanie", "Mauritanie"), ("Sénégal", "Sénégal"), ("Togo", "Togo"), ("Gabon", "Gabon"), ("Cameroun", "Cameroun")], help_text="Vide : tous les pays.", max_length=100)),
                ("portee", models.CharField(choices=[("partout", "références et avis"), ("references", "références du bureau seulement")], default="partout", max_length=10, verbose_name="portée")),
                ("statut", models.CharField(choices=[("propose", "proposé"), ("valide", "validé"), ("rejete", "rejeté")], default="propose", max_length=8)),
                ("origine", models.CharField(choices=[("reprise", "ancien synonyme"), ("collecte", "collecte d'avis"), ("saisie", "saisie"), ("claude", "Claude Desktop"), ("avis", "rattaché depuis un avis")], default="saisie", max_length=10)),
                ("source_url", models.URLField(blank=True, max_length=500, verbose_name="avis qui l'emploie")),
                ("nb_avis", models.PositiveIntegerField(blank=True, null=True, verbose_name="nombre d'avis")),
                ("motif", models.CharField(blank=True, max_length=500)),
                ("propose_par", models.CharField(blank=True, max_length=150, verbose_name="proposé par")),
                ("propose_le", models.DateTimeField(auto_now_add=True, verbose_name="proposé le")),
                ("decide_le", models.DateTimeField(blank=True, null=True, verbose_name="décidé le")),
                ("decide_par", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="+", to=settings.AUTH_USER_MODEL, verbose_name="décidé par")),
                ("type_ouvrage", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="termes", to="referentiel.typeouvrage", verbose_name="type d'ouvrage")),
            ],
            options={
                "verbose_name": "terme d'un type d'ouvrage",
                "verbose_name_plural": "termes des types d'ouvrages",
                "ordering": ["type_ouvrage__ordre", "terme", "pays"],
                "constraints": [models.UniqueConstraint(fields=("type_ouvrage", "cle", "pays"), name="terme_unique_par_type_et_pays")],
            },
        ),
        migrations.RunPython(reprendre, migrations.RunPython.noop),
    ]
