"""Tests : base PostgreSQL éphémère créée par pytest-django (test_<base>), cache en mémoire."""

from .base import *  # noqa: F403

SECRET_KEY = SECRET_KEY or "tests-seulement"  # noqa: F405
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

IDENTITE_SOURCE = "dev"
UTILISATEUR_DEV = "GICONSEILS\\essai"
GROUPES_DEV = ["GI-Direction"]
