"""Réglages communs aux trois environnements (dev, test, prod).

Les valeurs propres à un poste ou à un serveur viennent de `.env` (voir `.env.exemple`).
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlparse

from django.templatetags.static import static
from environs import Env

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = Env()
env.read_env(str(BASE_DIR / ".env"), recurse=False)


def base_depuis_url(url: str) -> dict:
    """`postgres://utilisateur:mot_de_passe@hote:port/base` → entrée de `DATABASES`.

    PostgreSQL seulement : SQLite est refusé partout, y compris en développement
    (les types et les index diffèrent, voir docs/tests.md).
    """
    u = urlparse(url)
    if u.scheme not in ("postgres", "postgresql"):
        raise ValueError("DATABASE_URL doit désigner une base PostgreSQL (postgres://…).")
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": u.path.lstrip("/"),
        "USER": unquote(u.username or ""),
        "PASSWORD": unquote(u.password or ""),
        "HOST": u.hostname or "localhost",
        "PORT": str(u.port or 5432),
        "CONN_MAX_AGE": 60,
    }


SECRET_KEY = env.str("SECRET_KEY", "")
DEBUG = False
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", ["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    "unfold",  # thème de l'admin et des écrans direction (ADR 0005) : avant django.contrib.admin
    "unfold.contrib.filters",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "identite",
    "suivi",
    "administratif",  # pièces administratives du bureau (ADR 0010)
    "referentiel",  # domaines, catégories, clients, bailleurs
    "references",  # références du bureau : une mission = un contrat (ADR 0008)
    "experts",  # vivier des experts et affectations (ADR 0012)
    "avis",  # avis de marchés : barème, sélection, pièces exigées (ADR 0013)
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "identite.middleware.IdentiteMiddleware",  # remplace request.user par l'identité Windows
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "interface" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": base_depuis_url(env.str("DATABASE_URL", "postgres://gic:gic@localhost:5432/gic"))
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Pas de mot de passe : l'utilisateur vient d'IIS (CONTEXT.md, règle 6)
AUTH_USER_MODEL = "identite.Utilisateur"
AUTH_PASSWORD_VALIDATORS: list[dict] = []

LOCALE_PATHS = [BASE_DIR / "locale"]  # nos traductions passent avant celles des bibliothèques
LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Bamako"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "interface" / "static"]
# Sur le serveur : C:\GIC\<env>\static_collecte, hors du code, servi par IIS (installer.ps1)
STATIC_ROOT = env.path("STATIC_ROOT", BASE_DIR / "static_collecte")

# --- Identité (application identite) -------------------------------------------------
# "dev" : utilisateur fictif ; "iis" : REMOTE_USER ou X-Remote-User posé par IIS ;
# "negotiate" : ticket Kerberos validé par l'application (SSPI, ADR 0007) — la production.
IDENTITE_SOURCE = "iis"
IDENTITE_AUTHENTIFICATEUR_NEGOTIATE = "identite.negotiate.authentifier"
# X-Remote-User n'est cru que s'il arrive de ces adresses (IIS sur la même machine).
IDENTITE_PROXYS_DE_CONFIANCE = ["127.0.0.1", "::1"]
# Chemins servis sans identité (supervision IIS).
IDENTITE_CHEMINS_PUBLICS = ["/sante/", "/api/sante"]
# Durée pendant laquelle les groupes AD lus pour un utilisateur restent valables.
IDENTITE_GROUPES_VALIDITE_S = 600

GROUPE_DIRECTION = env.str("GROUPE_DIRECTION", "GI-Direction")
# Consultation seule (compte « visionneuse ») : tous les écrans, aucune action. Groupe AD à
# créer en P04.
GROUPE_DIRECTION_LECTURE = env.str("GROUPE_DIRECTION_LECTURE", "GI-Direction-Lecture")
GROUPE_OFFRES = env.str("GROUPE_OFFRES", "GI-Offres")
# Partage des documents du bureau (D:\GIC). Les pièces administratives y sont lues, jamais écrites
# (ADR 0010, règle 4). Vide en développement : les écrans le signalent.
PARTAGE_GIC = env.str("PARTAGE_GIC", "")
ENVIRONNEMENT = env.str("ENVIRONNEMENT", "")  # test ou prod sur le serveur, vide en développement

# Identité du bureau, imprimée dans le dossier d'un AMI (AV14), telle qu'elle figure dans les
# vrais dossiers du bureau : une variante par usage, pas d'adresse unique (décision du porteur,
# 07/11/2026 : « pour les adresses et raison sociale on laisse ces incoherences »). Le siège
# « ext sud » sur la page d'adresse (et sur le logo, qui le porte) ; ACI Golf sur la couverture
# et au pied des listes de références, comme dans les listes Word du bureau. Un contrôle de
# concordance ne doit pas signaler ces différences. Sortir l'identité des réglages (un modèle)
# demanderait un ADR. Le logo n'est pas ici : il se lit sur le partage,
# ADMINISTRATIF\LOGOS\LOGO.png.
BUREAU = {
    "raison_sociale": env.str("BUREAU_RAISON_SOCIALE", "GI-Conseils SARL"),
    "nom_court": env.str("BUREAU_NOM_COURT", "GI-Conseils"),
    "gerant": env.str("BUREAU_GERANT", "Oumar Almahamoudou DICKO"),
    "titre_gerant": env.str("BUREAU_TITRE_GERANT", "Le Gérant"),
    "adresse": env.str("BUREAU_ADRESSE", "Bacodjicoroni-ext sud, Rue : 839 Porte : 523"),
    "boite_postale": env.str("BUREAU_BOITE_POSTALE", "BPE : 4853"),
    "ville": env.str("BUREAU_VILLE", "Bamako"),
    "pays": env.str("BUREAU_PAYS", "Mali"),
    "telephones": env.list(
        "BUREAU_TELEPHONES", ["(223) 20 28 02 10", "74 45 13 29", "90 46 35 20"]
    ),
    "courriels": env.list("BUREAU_COURRIELS", ["gi_conseil@yahoo.fr", "contact@gi-conseils.ml"]),
    "couverture_siege": env.str(
        "BUREAU_COUVERTURE_SIEGE", "Baco-djicoroni ACI GOLF Rue : 414 Porte : 302 Bamako"
    ),
    "couverture_contact": env.str(
        "BUREAU_COUVERTURE_CONTACT", "BP. E1773 – Tél. : 20 28 02 10/74 45 13 29"
    ),
    "listes_siege": env.str(
        "BUREAU_LISTES_SIEGE", "Baco-djicoroni aci GOLF Rue : 414 Porte : 302 Bamako ; Mali"
    ),
    "listes_contact": env.str(
        "BUREAU_LISTES_CONTACT",
        "BP. E1773 – Tél. : 20 28 02 10/74 45 13 29/74 11 22 39/90 46 35 20",
    ),
    "listes_courriels": env.list(
        "BUREAU_LISTES_COURRIELS", ["contact@gi-conseils.ml", "gi_conseil@yahoo.fr"]
    ),
}


# --- Interface (Unfold, ADR 0005) -----------------------------------------------------
def _version_fichier(chemin_statique: str) -> int:
    """Date de modification d'un fichier de interface/static, pour casser le cache."""
    try:
        return int((BASE_DIR / "interface" / "static" / chemin_statique).stat().st_mtime)
    except OSError:
        return 0


def _lien(nom: str):
    from django.urls import reverse_lazy

    return reverse_lazy(nom)


# Bleu GI-CONSEILS (palette Tailwind « blue »), en oklch comme l'attend Unfold
_BLEU = {
    "50": "oklch(97% 0.014 254.604)",
    "100": "oklch(93.2% 0.032 255.585)",
    "200": "oklch(88.2% 0.059 254.128)",
    "300": "oklch(80.9% 0.105 251.813)",
    "400": "oklch(70.7% 0.165 254.624)",
    "500": "oklch(62.3% 0.214 259.815)",
    "600": "oklch(54.6% 0.245 262.881)",
    "700": "oklch(48.8% 0.243 264.376)",
    "800": "oklch(42.4% 0.199 265.638)",
    "900": "oklch(37.9% 0.146 265.522)",
    "950": "oklch(28.2% 0.091 267.935)",
}

UNFOLD = {
    "SITE_TITLE": "GI-SUIVI",
    "SITE_HEADER": "GI-CONSEILS",
    "SITE_SUBHEADER": "Suivi d'activité",
    "SITE_SYMBOL": "monitoring",
    "SHOW_VIEW_ON_SITE": False,
    # CSS du projet (ADR 0005, point 4) : classes de nos gabarits absentes du CSS d'Unfold.
    # ?v=<date du fichier> : une recompilation change l'URL, le navigateur ne garde pas l'ancien.
    "STYLES": [lambda request: f"{static('css/gic.css')}?v={_version_fichier('css/gic.css')}"],
    "DASHBOARD_CALLBACK": "suivi.tableau_de_bord.contexte",
    "COLORS": {"primary": _BLEU},
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        # Ordre voulu par le porteur (08/10/2026) : les Écrans d'abord, l'administration ensuite.
        # Allégé le 21/10/2026 : plus de doublons des Écrans (tableau de bord, dossiers, postes)
        # ni de pages techniques (segments, recalculs) ; « Qui suis-je ? » reste à son adresse
        "navigation": [
            {
                "title": "Écrans",
                "items": [
                    {
                        "title": "Journée",
                        "icon": "today",
                        "link": _lien("suivi:journee"),
                    },
                    {
                        "title": "Vue d'ensemble",
                        "icon": "insights",
                        "link": _lien("suivi:vue_ensemble"),
                    },
                    {
                        "title": "Dossiers",
                        "icon": "folder_open",
                        "link": _lien("suivi:dossiers"),
                    },
                    {
                        "title": "Personnes",
                        "icon": "groups",
                        "link": _lien("suivi:employes"),
                    },
                    {
                        "title": "Tâches",
                        "icon": "task_alt",
                        "link": _lien("suivi:taches"),
                    },
                    {
                        "title": "Gestion des dossiers",
                        "icon": "rule_folder",
                        "link": _lien("suivi:gestion_dossiers"),
                    },
                    {
                        "title": "À classer",
                        "icon": "inbox",
                        "link": _lien("suivi:a_classer"),
                    },
                    {
                        "title": "État des postes",
                        "icon": "computer",
                        "link": _lien("suivi:postes"),
                    },
                ],
            },
            {
                # Avis (ADR 0013), références (ADR 0008), experts, pièces administratives (ADR 0010)
                "title": "Offres",
                "items": [
                    {
                        "title": "Avis",
                        "icon": "campaign",
                        "link": _lien("avis:liste"),
                    },
                    {
                        "title": "Propositions d'avis",
                        "icon": "inbox",
                        "link": _lien("avis:propositions"),
                        "badge": "avis.vues.ecrans.pastille_propositions",
                        "badge_variant": "info",
                    },
                    {
                        "title": "Références",
                        "icon": "library_books",
                        "link": _lien("references:liste"),
                    },
                    {
                        "title": "Experts",
                        "icon": "engineering",
                        "link": _lien("experts:vivier"),
                    },
                    {
                        "title": "Doublons à arbitrer",
                        "icon": "difference",
                        "link": _lien("references:doublons"),
                    },
                    {
                        "title": "Pièces administratives",
                        "icon": "verified",
                        "link": _lien("administratif:registre"),
                        "badge": "administratif.vues.registre.pastille",
                        "badge_variant": "warning",
                    },
                    {
                        "title": "Contrôle avant un dépôt",
                        "icon": "fact_check",
                        "link": _lien("administratif:controle"),
                    },
                    {
                        "title": "Types de pièces",
                        "icon": "category",
                        "link": _lien("administratif:types"),
                    },
                ],
            },
            {
                "title": "Classement",
                "items": [
                    {
                        "title": "Racines",
                        "icon": "account_tree",
                        "link": _lien("admin:suivi_racine_changelist"),
                    },
                    {
                        "title": "Exceptions",
                        "icon": "alt_route",
                        "link": _lien("admin:suivi_regleexception_changelist"),
                    },
                ],
            },
            {
                "title": "Administration",
                "items": [
                    {
                        "title": "Employés",
                        "icon": "badge",
                        "link": _lien("admin:suivi_employe_changelist"),
                    },
                    {
                        "title": "Paramètres",
                        "icon": "tune",
                        "link": _lien("admin:suivi_parametre_changelist"),
                    },
                    {
                        "title": "Utilisateurs",
                        "icon": "person",
                        "link": _lien("admin:identite_utilisateur_changelist"),
                    },
                    {
                        "title": "Journal d'accès",
                        "icon": "history",
                        "link": _lien("admin:suivi_journalacces_changelist"),
                    },
                ],
            },
        ],
    },
}

# --- Suivi d'activité ---------------------------------------------------------------
SUIVI_RETENTION_MOIS = env.int("SUIVI_RETENTION_MOIS", 24)
SUIVI_SEUIL_INACTIVITE_S = env.int("SUIVI_SEUIL_INACTIVITE_S", 300)
SUIVI_HEURES_PREVUES_SEMAINE = env.int("SUIVI_HEURES_PREVUES_SEMAINE", 40)
