"""Types d'ouvrages, livrables et types de quantités de départ (chantier 4, ADR 0011). La liste
des ouvrages et leurs synonymes sont à valider par l'arbitre métier ; tout se corrige dans
l'administration (Référentiel)."""

from django.db import migrations

EAUX = "mobilisation des eaux de surface"
AGRI = "aménagements hydro-agricoles"
VILLAGEOISE = "hydraulique villageoise et AEP"
OUVRAGES = [
    ("seuil-epandage", "Seuil d'épandage", EAUX, ["seuil", "recharge de nappe"]),
    ("micro-barrage", "Micro-barrage", EAUX, ["barrage", "retenue d'eau", "recharge de nappe"]),
    ("digue-filtrante", "Digue filtrante", EAUX, ["digue", "recharge de nappe"]),
    ("retenue-collinaire", "Retenue collinaire", EAUX, ["retenue", "recharge de nappe"]),
    ("surcreusement-mare", "Surcreusement de mare", EAUX, ["mare"]),
    ("bas-fond", "Bas-fond aménagé", AGRI, ["bas-fonds", "riziculture"]),
    ("piv", "Périmètre irrigué villageois (PIV)", AGRI, ["PIV", "périmètre irrigué"]),
    ("forage", "Forage", VILLAGEOISE, ["puits", "point d'eau"]),
    ("aep", "Adduction d'eau potable (AEP)", VILLAGEOISE, ["AEP", "eau potable", "mini-AEP"]),
    ("piste", "Piste", "infrastructures routières", ["route", "piste rurale"]),
    ("batiment", "Bâtiment", "bâtiment", ["construction"]),
    ("assainissement", "Assainissement", "assainissement", ["latrines", "drainage"]),
]
LIVRABLES = [
    ("aps", "Avant-projet sommaire (APS)"),
    ("apd", "Avant-projet détaillé (APD)"),
    ("dao", "Dossier d'appel d'offres (DAO)"),
    ("eies", "Étude d'impact environnemental et social (EIES)"),
    ("nies", "Notice d'impact environnemental et social (NIES)"),
    ("suivi-controle", "Suivi-contrôle des travaux"),
]
QUANTITES = [
    ("superficie-ha", "Superficie aménagée", "ha"),
    ("longueur-km", "Longueur", "km"),
    ("nb-forages", "Nombre de forages", "forages"),
    ("nb-ouvrages", "Nombre de sites ou d'ouvrages", "sites"),
    ("capacite-m3", "Capacité", "m³"),
]


def creer(apps, schema_editor):
    TypeOuvrage = apps.get_model("referentiel", "TypeOuvrage")
    Livrable = apps.get_model("referentiel", "Livrable")
    TypeQuantite = apps.get_model("referentiel", "TypeQuantite")
    for i, (cle, libelle, famille, synonymes) in enumerate(OUVRAGES, start=1):
        TypeOuvrage.objects.get_or_create(
            cle=cle,
            defaults={"libelle": libelle, "famille": famille, "synonymes": synonymes, "ordre": i * 10},
        )
    for i, (cle, libelle) in enumerate(LIVRABLES, start=1):
        Livrable.objects.get_or_create(cle=cle, defaults={"libelle": libelle, "ordre": i * 10})
    for i, (cle, libelle, unite) in enumerate(QUANTITES, start=1):
        TypeQuantite.objects.get_or_create(
            cle=cle, defaults={"libelle": libelle, "unite": unite, "ordre": i * 10}
        )


def retirer(apps, schema_editor):
    apps.get_model("referentiel", "TypeOuvrage").objects.filter(cle__in=[o[0] for o in OUVRAGES]).delete()
    apps.get_model("referentiel", "Livrable").objects.filter(cle__in=[x[0] for x in LIVRABLES]).delete()
    apps.get_model("referentiel", "TypeQuantite").objects.filter(cle__in=[q[0] for q in QUANTITES]).delete()


class Migration(migrations.Migration):
    dependencies = [("referentiel", "0003_ouvrages_livrables_quantites")]

    operations = [migrations.RunPython(creer, retirer)]
