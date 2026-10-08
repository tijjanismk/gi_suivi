"""Écrit deploy/requirements.txt à partir des dépendances d'exécution de pyproject.toml.

Le serveur n'a aucun outil de développement : il n'installe pas le projet (pas de
``pip install -e .``, pas de build), seulement cette liste, avec ``pip install -r``.
Le code tourne depuis C:\\GIC\\<env>\\app, importé par manage.py.

    python scripts/dev/exporter_dependances.py            # réécrit le fichier
    python scripts/dev/exporter_dependances.py --verifier # code de sortie 1 s'il n'est pas à jour
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
PYPROJECT = RACINE / "pyproject.toml"
CIBLE = RACINE / "deploy" / "requirements.txt"
ENTETE = (
    "# Généré par scripts/dev/exporter_dependances.py à partir de pyproject.toml — ne pas éditer.\n"
    "# Dépendances d'exécution seulement : le serveur les installe avec pip install -r, sans\n"
    "# outil de développement ni compilation (roues binaires uniquement, voir --only-binary).\n"
)


def contenu_attendu() -> str:
    with PYPROJECT.open("rb") as f:
        projet = tomllib.load(f)["project"]
    lignes = sorted(d.strip() for d in projet["dependencies"])
    return ENTETE + "\n".join(lignes) + "\n"


def main(argv: list[str]) -> int:
    attendu = contenu_attendu()
    if "--verifier" in argv:
        actuel = CIBLE.read_text(encoding="utf-8") if CIBLE.exists() else ""
        if actuel != attendu:
            print(f"{CIBLE.relative_to(RACINE)} n'est pas à jour : lancez {Path(__file__).name}")
            return 1
        print(f"{CIBLE.relative_to(RACINE)} à jour.")
        return 0
    CIBLE.write_text(attendu, encoding="utf-8", newline="\n")
    print(f"{CIBLE.relative_to(RACINE)} écrit ({attendu.count(chr(10)) - 3} dépendances).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
