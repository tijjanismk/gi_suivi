"""Point d'entrée ASGI (Uvicorn) : Django pour les écrans et l'API de l'agent, et le serveur MCP du
module avis sous /mcp/ (ADR 0016, `config/serveur_mcp.py`), dans le même processus (ADR 0001)."""

from django.core.asgi import get_asgi_application

from config.demarrage import choisir_reglages

choisir_reglages()

application_django = get_asgi_application()

# Après django.setup() (dans get_asgi_application) : les outils importent les modèles.
from config import serveur_mcp  # noqa: E402

application = serveur_mcp.aiguiller(application_django, serveur_mcp.creer_application())
