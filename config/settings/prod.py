"""Production : derrière IIS (HTTPS, authentification Windows), journal dans un fichier."""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import ALLOWED_HOSTS, BASE_DIR, env

if not SECRET_KEY:  # noqa: F405
    raise ImproperlyConfigured("SECRET_KEY manquante dans .env (production).")

# Le ticket Kerberos est validé par l'application (ADR 0007) ; "iis" reste possible si IIS
# transmet un jour l'identité lui-même.
IDENTITE_SOURCE = env.str("IDENTITE_SOURCE", "negotiate")
# Groupes AD lus par l'API Windows du serveur, qui est le contrôleur de domaine (ADR 0006)
IDENTITE_LECTEUR_GROUPES = env.str(
    "IDENTITE_LECTEUR_GROUPES", "identite.groupes_windows.groupes_de"
)
IDENTITE_SERVEUR_GROUPES = env.str("IDENTITE_SERVEUR_GROUPES", "") or None

# IIS termine le HTTPS et transmet en HTTP local à Uvicorn
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_TRUSTED_ORIGINS = [
    f"https://{h}" for h in ALLOWED_HOSTS if h not in ("localhost", "127.0.0.1")
]

# Dossier des journaux : DOSSIER_JOURNAUX (ou JOURNAUX, nom écrit par les premiers installer.ps1) ;
# créé s'il manque, sinon le gestionnaire de journal refuse de démarrer.
DOSSIER_JOURNAUX = env.path("DOSSIER_JOURNAUX", env.path("JOURNAUX", BASE_DIR / "journaux"))
DOSSIER_JOURNAUX.mkdir(parents=True, exist_ok=True)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "%(asctime)s %(levelname)s %(name)s : %(message)s"}},
    "handlers": {
        "fichier": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(DOSSIER_JOURNAUX / "gic.log"),
            "maxBytes": 5_000_000,
            "backupCount": 10,
            "encoding": "utf-8",
            "formatter": "simple",
        }
    },
    "root": {"handlers": ["fichier"], "level": "INFO"},
}
