"""Les six domaines de la présentation du bureau, leurs sous-domaines et les ouvrages qu'ils
nomment (ADR 0014). Les codes à trois lettres existants sont gardés ; RUR (développement rural)
s'ajoute ; AQA et VRD sont supprimés s'ils ne servent plus (sur un serveur, VRD reste jusqu'au
recodage de ses références par `manage.py references_recoder`, qui le supprime alors)."""

from django.db import migrations
from django.db.models import Q

DOMAINES = [  # ordre de la présentation
    ("AEP", "Approvisionnement en eau et assainissement"),
    ("RUR", "Développement rural"),
    ("RTE", "Infrastructures de transport"),
    ("HYD", "Aménagements hydro-agricoles"),
    ("BAT", "Bâtiments civils et industriels"),
    ("ENV", "Environnement"),
]
RETIRES = ("AQA", "VRD")
# Sous-domaines : (domaine, clé, libellé). Les cinq clés déjà créées par l'import de la liste
# maîtresse (bas-fonds, PIV, PM, mares, assainissement) sont reprises telles quelles.
CATEGORIES = [
    ("AEP", "puits-modernes", "Puits modernes et puits-citernes"),
    ("AEP", "forages-pmh", "Forages équipés de PMH"),
    ("AEP", "forages-electropompe", "Forages équipés d'électropompe"),
    ("AEP", "adductions-eau-sommaires", "Adductions d'eau sommaires (AES)"),
    ("AEP", "systemes-solaires-adduction", "Systèmes solaires d'adduction d'eau"),
    ("AEP", "reseaux-eau-potable", "Adductions et réseaux de distribution d'eau potable"),
    ("AEP", "stations-pompage-traitement", "Stations de pompage et de traitement d'eau"),
    ("AEP", "latrines", "Latrines"),
    ("AEP", "dechets-liquides-solides", "Traitement des déchets liquides et solides"),
    ("AEP", "assainissement", "Assainissement (routier, pluvial, caniveaux et collecteurs)"),
    ("RUR", "pistes-rurales", "Pistes rurales"),
    ("RUR", "infrastructures-hydro-agricoles", "Infrastructures hydro-agricoles"),
    ("RUR", "infrastructures-elevage", "Infrastructures d'élevage"),
    ("RUR", "points-eau", "Points d'eau"),
    ("RUR", "hydraulique-villageoise-pastorale", "Hydraulique villageoise et pastorale"),
    ("RUR", "energie", "Énergie"),
    ("RUR", "equipements-socio-collectifs", "Équipements socio-collectifs"),
    ("RTE", "routes-en-terre", "Routes en terre"),
    ("RTE", "routes-nationales-interurbaines", "Routes nationales et interurbaines"),
    ("RTE", "voiries", "Voiries"),
    ("RTE", "ponts", "Ponts"),
    ("RTE", "ouvrages-franchissement", "Ouvrages de franchissement (dalots, radiers)"),
    ("RTE", "quais-fluviaux", "Quais fluviaux"),
    ("HYD", "barrages-retenues", "Barrages et retenues d'eau"),
    ("HYD", "bas-fonds-et-plaines", "Bas-fonds et plaines"),
    ("HYD", "perimetres-irrigues-villageois-piv", "Périmètres irrigués villageois (PIV)"),
    ("HYD", "perimetres-maraichers-pm", "Périmètres maraîchers (PM)"),
    ("HYD", "mares", "Mares"),
    ("HYD", "bassins-versants", "Aménagement de bassins versants"),
    (
        "HYD",
        "reseaux-irrigation-drainage",
        "Réseaux d'irrigation, de drainage, pistes et ouvrages de protection",
    ),
    ("HYD", "stations-pompage-hydromecaniques", "Stations de pompage et équipements hydromécaniques"),
    ("BAT", "ecoles-salles-classe", "Écoles et salles de classe"),
    ("BAT", "centres-sante", "Centres de santé"),
    ("BAT", "bureaux-administratifs", "Bureaux et bâtiments administratifs"),
    ("BAT", "magasins-industriels", "Magasins et bâtiments industriels"),
    ("ENV", "etudes-impact", "Études d'impact (EIES, NIES)"),
    ("ENV", "audits-bilans-environnementaux", "Audits et bilans environnementaux"),
    ("ENV", "suivi-environnemental", "Surveillance et suivi environnementaux"),
]
VILLAGEOISE = "hydraulique villageoise et AEP"
ROUTES = "infrastructures routières"
OUVRAGES = [  # mêmes familles que les types de départ (0004)
    ("aes", "Adduction d'eau sommaire (AES)", VILLAGEOISE, ["AES", "adduction d'eau sommaire"]),
    ("shva", "Système d'hydraulique villageoise amélioré (SHVA)", VILLAGEOISE, ["SHVA"]),
    ("shpa", "Système d'hydraulique pastorale amélioré (SHPA)", VILLAGEOISE, ["SHPA"]),
    ("pont", "Pont", ROUTES, ["ouvrage d'art"]),
    ("dalot", "Dalot ou ouvrage de franchissement", ROUTES, ["dalot", "radier"]),
]


def appliquer(apps, schema_editor):
    Domaine = apps.get_model("referentiel", "Domaine")
    Categorie = apps.get_model("referentiel", "Categorie")
    TypeOuvrage = apps.get_model("referentiel", "TypeOuvrage")
    Mission = apps.get_model("references", "Mission")
    Expert = apps.get_model("experts", "Expert")
    domaines = {}
    for i, (code, libelle) in enumerate(DOMAINES, start=1):
        domaines[code], _ = Domaine.objects.update_or_create(
            code=code, defaults={"libelle": libelle, "ordre": i * 10}
        )
    for code, cle, libelle in CATEGORIES:
        Categorie.objects.update_or_create(
            cle=cle, defaults={"domaine": domaines[code], "libelle": libelle}
        )
    depart = TypeOuvrage.objects.count()
    for i, (cle, libelle, famille, synonymes) in enumerate(OUVRAGES, start=1):
        TypeOuvrage.objects.get_or_create(
            cle=cle,
            defaults={
                "libelle": libelle,
                "famille": famille,
                "synonymes": synonymes,
                "ordre": (depart + i) * 10,
            },
        )
    for code in RETIRES:
        d = Domaine.objects.filter(code=code).first()
        if d is None:
            continue
        # les catégories d'un domaine retiré passent sous l'eau et l'assainissement
        Categorie.objects.filter(domaine=d).update(domaine=domaines["AEP"])
        sert = Mission.objects.filter(Q(domaine=d) | Q(domaines_secondaires=d)).exists()
        if not sert and not Expert.objects.filter(domaines=d).exists():
            d.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("referentiel", "0004_types_de_depart"),
        ("references", "0002_justificatifs_ouvrages_quantites"),
        ("experts", "0002_expert_a_verifier"),
    ]

    # Pas de retour automatique : les libellés précédents restent dans 0002_domaines
    operations = [migrations.RunPython(appliquer, migrations.RunPython.noop)]
