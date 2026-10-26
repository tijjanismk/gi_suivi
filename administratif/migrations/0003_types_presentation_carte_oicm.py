"""Deux types de pièces vus au premier remplissage du registre (chantier 8, 26/10/2026) : la
présentation du bureau, jointe aux offres et revue chaque année, rangée dans
ADMINISTRATIF\\PRESENTATION ; la carte professionnelle de l'OICM, distincte de l'attestation
d'affiliation annuelle, tenue pour permanente tant que l'Ordre n'indique pas d'échéance. Ni
l'une ni l'autre n'est exigée par défaut : la direction le change dans « Types de pièces »."""

from django.db import migrations

# code, libellé, organisme, règle, durée en mois, exigée par défaut, dossier, ordre
TYPES = [
    ("PRESENTATION", "Présentation du bureau (jointe aux offres)", "Interne",
     "revue_periodique", 12, False, "ADMINISTRATIF\\PRESENTATION", 170),
    ("CARTE-PRO-OICM", "Carte professionnelle de l'Ordre des ingénieurs-conseils", "OICM",
     "permanente", None, False, "ADMINISTRATIF\\PIECES\\CARTE-PRO-OICM", 180),
]  # fmt: skip


def creer(apps, schema_editor):
    TypePiece = apps.get_model("administratif", "TypePiece")
    for code, libelle, organisme, regle, duree, exigee, dossier, ordre in TYPES:
        TypePiece.objects.get_or_create(
            code=code,
            defaults={
                "libelle": libelle,
                "organisme": organisme,
                "regle_validite": regle,
                "duree_mois": duree,
                "rappel_jours": 15,
                "exigee_par_defaut": exigee,
                "dossier": dossier,
                "ordre": ordre,
            },
        )


def retirer(apps, schema_editor):
    TypePiece = apps.get_model("administratif", "TypePiece")
    TypePiece.objects.filter(code__in=[t[0] for t in TYPES], versions=None, demandes=None).delete()


class Migration(migrations.Migration):
    dependencies = [("administratif", "0002_types_initiaux")]

    operations = [migrations.RunPython(creer, retirer)]
