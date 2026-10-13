"""Point d'entrée ASGI (Uvicorn). Le serveur MCP sera monté sous /mcp/ avec le module avis."""

from django.core.asgi import get_asgi_application

from config.demarrage import choisir_reglages

choisir_reglages()

application = get_asgi_application()
