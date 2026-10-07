"""Développement : PostgreSQL local (jamais SQLite), utilisateur fictif injecté."""

from .base import *  # noqa: F403
from .base import env

DEBUG = True
SECRET_KEY = SECRET_KEY or "dev-seulement-jamais-en-production"  # noqa: F405

IDENTITE_SOURCE = "dev"
UTILISATEUR_DEV = env.str("UTILISATEUR_DEV", "GICONSEILS\\dev")
GROUPES_DEV = env.list("GROUPES_DEV", ["GI-Direction"])
