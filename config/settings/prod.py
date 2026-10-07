"""Production : derrière IIS (HTTPS, authentification Windows), journal dans un fichier."""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import ALLOWED_HOSTS, BASE_DIR, env

if not SECRET_KEY:  # noqa: F405
    raise ImproperlyConfigured("SECRET_KEY manquante dans .env (production).")

IDENTITE_SOURCE = "iis"

# IIS termine le HTTPS et transmet en HTTP local à Uvicorn
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_TRUSTED_ORIGINS = [
    f"https://{h}" for h in ALLOWED_HOSTS if h not in ("localhost", "127.0.0.1")
]

DOSSIER_JOURNAUX = env.path("DOSSIER_JOURNAUX", BASE_DIR / "journaux")
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
