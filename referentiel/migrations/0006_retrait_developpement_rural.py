"""Retrait du développement rural (ADR 0017) : cinq domaines restent (AEP, RTE, HYD, BAT, ENV).
RUR et ses sept sous-domaines sont supprimés, sans être reportés ailleurs ; comme VRD (ADR 0014),
le domaine reste tant qu'une référence, un expert ou une catégorie de référence le porte."""

from django.db import migrations
from django.db.models import Q


def retirer(apps, schema_editor):
    Domaine = apps.get_model("referentiel", "Domaine")
    Categorie = apps.get_model("referentiel", "Categorie")
    Mission = apps.get_model("references", "Mission")
    Expert = apps.get_model("experts", "Expert")
    rur = Domaine.objects.filter(code="RUR").first()
    if rur is None:
        return
    sert = Mission.objects.filter(
        Q(domaine=rur) | Q(domaines_secondaires=rur) | Q(categorie__domaine=rur)
    ).exists()
    if sert or Expert.objects.filter(domaines=rur).exists():
        return
    Categorie.objects.filter(domaine=rur).delete()
    rur.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("referentiel", "0005_domaines_presentation"),
        ("references", "0003_piece_deuxieme_page"),
        ("experts", "0002_expert_a_verifier"),
    ]

    # Pas de retour automatique : RUR et ses sous-domaines restent décrits dans 0005
    operations = [migrations.RunPython(retirer, migrations.RunPython.noop)]
