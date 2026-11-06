"""Pont MCP du poste (ADR 0016) : lancé par Claude Desktop, relaie vers le serveur en Kerberos.
Point d'entrée de `pont-mcp.exe` ; la logique est dans `gisuivi_agent/pont_mcp.py`."""

import sys

from gisuivi_agent.pont_mcp import main

if __name__ == "__main__":
    sys.exit(main())
