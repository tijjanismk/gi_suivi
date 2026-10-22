"""Types de départ des pièces administratives (ADR 0010, § 9, corrigé le 22/10/2026 d'après les
pièces réelles du bureau). Rappel 15 jours avant l'expiration pour toutes. « Exigée dans chaque
dossier » suit la liste du contexte de l'ADR ; les autres ne sont jointes que si l'avis les
demande. Tout se corrige ensuite dans l'écran « Types de pièces »."""

from django.db import migrations

# code, libellé, organisme, règle, durée en mois, exigée par défaut
TYPES = [
    ("QUITUS-FISCAL", "Certificat de situation fiscale (« quitus fiscal »)",
     "Centre des impôts (DGI)", "date_du_document", 3, True),
    ("TVA", "Attestation de déclaration mensuelle de TVA et taxes assimilées",
     "Direction des impôts", "date_du_document", 1, False),
    ("PATENTE", "Patente de l'année", "Centre des impôts", "fin_annee", None, False),
    ("INPS", "Attestation de paiement des cotisations", "INPS", "date_du_document", None, True),
    ("NON-FAILLITE", "Certificat de non-faillite", "Greffe du tribunal de grande instance",
     "apres_emission", 3, False),
    ("OMH", "Attestation de l'Office malien de l'habitat (taxe-logement du mois)", "OMH",
     "date_du_document", 1, False),
    ("NON-EXCLUSION", "Certificat de non-exclusion aux marchés publics",
     "ARMDS (Autorité de régulation des marchés publics et des délégations de service public)",
     "apres_emission", 12, False),
    ("NON-ENDETTEMENT", "Attestation de non-engagement envers le Trésor", "Trésorerie régionale",
     "apres_emission", 12, False),
    ("EXTRAIT-RCCM", "Extrait récent du RCCM", "Greffe du tribunal de commerce",
     "apres_emission", 3, False),
    ("RCCM", "Immatriculation au RCCM (déclaration de constitution)", "Greffe",
     "permanente", None, True),
    ("OICM", "Attestation d'affiliation à l'Ordre des ingénieurs-conseils", "OICM",
     "apres_emission", 12, True),
    ("AGREMENT", "Enregistrement API-Mali (tient lieu de certificat d'agrément)",
     "API-Mali, guichet unique", "permanente", None, True),
    ("MOYENS", "Liste des moyens matériels et logistiques", "Interne",
     "revue_periodique", 12, True),
    ("NIF", "Carte d'identification fiscale", "DGI", "permanente", None, True),
    ("STATUTS", "Statuts à jour", "Notaire", "permanente", None, True),
    ("DENOMINATIONS", "Note sur les dénominations, adresses et NIF successifs",
     "Interne, signée par la direction", "permanente", None, False),
]  # fmt: skip


def creer(apps, schema_editor):
    TypePiece = apps.get_model("administratif", "TypePiece")
    for i, (code, libelle, organisme, regle, duree, exigee) in enumerate(TYPES, start=1):
        TypePiece.objects.get_or_create(
            code=code,
            defaults={
                "libelle": libelle,
                "organisme": organisme,
                "regle_validite": regle,
                "duree_mois": duree,
                "rappel_jours": 15,
                "exigee_par_defaut": exigee,
                "dossier": f"ADMINISTRATIF\\PIECES\\{code}",
                "ordre": i * 10,
            },
        )


def retirer(apps, schema_editor):
    TypePiece = apps.get_model("administratif", "TypePiece")
    TypePiece.objects.filter(code__in=[t[0] for t in TYPES], versions=None, demandes=None).delete()


class Migration(migrations.Migration):
    dependencies = [("administratif", "0001_pieces_administratives")]

    operations = [migrations.RunPython(creer, retirer)]
