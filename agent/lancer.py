"""Point d'entrée de l'exécutable : importe le paquet, puis lance l'agent."""

import sys

from gisuivi_agent.principal import main

if __name__ == "__main__":
    if sys.argv[1:2] == ["--service"]:  # lancé par le gestionnaire de services (G06)
        from gisuivi_agent.service import executer_service

        sys.exit(executer_service())
    sys.exit(main())
