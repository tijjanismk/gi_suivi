"""Point d'entrée ASGI (Uvicorn). Le serveur MCP sera monté sous /mcp/ avec le module avis."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

application = get_asgi_application()
