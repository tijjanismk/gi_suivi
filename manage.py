#!/usr/bin/env python
"""Commandes Django. Réglages : variable d'environnement, sinon `.env`, sinon développement."""

import sys

from config.demarrage import choisir_reglages


def main() -> None:
    choisir_reglages()
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
