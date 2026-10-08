"""Réglages communs aux trois environnements (dev, test, prod).

Les valeurs propres à un poste ou à un serveur viennent de `.env` (voir `.env.exemple`).
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlparse

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
STATIC_ROOT = BASE_DIR / "static_collecte"

# --- Identité (application identite) -------------------------------------------------
# "dev" : utilisateur fictif ; "iis" : REMOTE_USER ou X-Remote-User posé par IIS.
IDENTITE_SOURCE = "iis"
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


# --- Interface (Unfold, ADR 0005) -----------------------------------------------------
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
    "DASHBOARD_CALLBACK": "suivi.tableau_de_bord.contexte",
    "COLORS": {"primary": _BLEU},
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": [
            {
                "title": "Suivi",
                "items": [
                    {
                        "title": "Tableau de bord",
                        "icon": "space_dashboard",
                        "link": _lien("admin:index"),
                    },
                    {
                        "title": "Dossiers",
                        "icon": "folder",
                        "link": _lien("admin:suivi_dossier_changelist"),
                    },
                    {
                        "title": "Employés",
                        "icon": "badge",
                        "link": _lien("admin:suivi_employe_changelist"),
                    },
                    {
                        "title": "Postes",
                        "icon": "computer",
                        "link": _lien("admin:suivi_poste_changelist"),
                    },
                    {
                        "title": "Segments",
                        "icon": "timeline",
                        "link": _lien("admin:suivi_segment_changelist"),
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
                    {
                        "title": "Qui suis-je ?",
                        "icon": "fingerprint",
                        "link": _lien("identite:qui_suis_je"),
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
