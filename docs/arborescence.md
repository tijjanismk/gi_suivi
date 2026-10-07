# Arborescence du dépôt

```
gic/
├── README.md                    # présentation, installation, lancement
├── CONTEXT.md                   # contexte pour l'IA, lu en début de session
├── pyproject.toml               # dépendances, ruff, pytest, version du projet
├── .env.exemple                 # variables d'environnement documentées
├── .gitignore
├── .pre-commit-config.yaml      # ruff avant chaque commit
├── manage.py
│
├── .github/
│   └── workflows/
│       └── ci.yml               # lint + tests à chaque push et pull request
│
├── config/                      # projet Django
│   ├── settings/
│   │   ├── base.py              # commun
│   │   ├── dev.py               # SQLite interdit : PostgreSQL local, utilisateur fictif
│   │   ├── test.py              # base éphémère, cache en mémoire
│   │   └── prod.py              # IIS, chemins UNC, journalisation fichier
│   ├── urls.py
│   └── asgi.py                  # monte Django ET le serveur MCP sous /mcp/
│
├── moteur/                      # ★ Python pur, aucun import Django
│   ├── __init__.py
│   ├── types.py                 # dataclasses : MissionDTO, CritereDTO, ResultatCritere…
│   ├── filtres.py               # interprète Critere.filtre sur des MissionDTO
│   ├── selection.py             # sélectionne et classe les missions par critère
│   ├── notation.py              # applique les modes de calcul, note totale, verdict
│   ├── completude.py            # état des pièces, points perdus, classement
│   ├── normalisation.py         # dates, durées, montants, pays/lieu depuis texte libre
│   └── tests/                   # tests unitaires rapides, centaines de cas
│
├── referentiel/                 # application Django : vocabulaire de la base
│   ├── models.py                # Domaine, Categorie, TypeOuvrage, Localite, Client, Bailleur, TypeQuantite
│   ├── admin.py
│   ├── services.py
│   ├── fixtures/                # domaines, catégories, localités du Mali, thésaurus initial
│   ├── management/commands/initialiser_referentiel.py
│   ├── migrations/
│   └── tests/
│
├── references/                  # missions et pièces justificatives
│   ├── models.py                # Mission, Quantite, PieceJustificative
│   ├── admin.py
│   ├── services.py              # conversion ORM → DTO, appels à moteur/
│   ├── outils_mcp.py            # rechercher_missions, detail_mission
│   ├── vues/                    # liste, fiche, écran de revue (assainissement)
│   ├── management/commands/
│   │   ├── importer_missions.py       # CSV → missions "importee"
│   │   └── rapprocher_justificatifs.py # parcourt le partage, crée les pièces
│   ├── migrations/
│   └── tests/
│
├── experts/                     # vivier
│   ├── models.py                # Expert, Diplome, Affectation, ExperienceExterne
│   ├── admin.py
│   ├── services.py
│   ├── outils_mcp.py            # rechercher_experts
│   ├── vues/
│   ├── migrations/
│   └── tests/
│
├── avis/                        # avis, barèmes, validation, sélections
│   ├── models.py                # Proposition, Avis, Critere, Selection, BesoinExpert
│   ├── admin.py                 # critères en ligne sous l'avis
│   ├── services.py              # simuler, valider une proposition, enregistrer brouillons
│   ├── outils_mcp.py            # simuler_avis, pieces_manquantes, proposer_filtre_critere, creer_proposition
│   ├── vues/                    # fiche avis, barème, simulation, file de validation
│   ├── management/commands/creer_avis_exemple.py   # SOMAPEP 09/2026/001 : jeu d'essai
│   ├── migrations/
│   └── tests/
│
├── mcp/                         # assemblage du serveur MCP
│   ├── serveur.py               # instancie FastMCP, enregistre les outils des applications
│   ├── identite.py              # lit l'en-tête d'identité posé par le pont
│   └── tests/                   # appelle les outils via le client MCP de test
│
├── identite/                    # utilisateur depuis IIS
│   ├── models.py                # Utilisateur (login_windows, groupes)
│   ├── middleware.py            # REMOTE_USER → Utilisateur ; version dev avec utilisateur fictif
│   └── tests/
│
├── interface/                   # tout ce qui est partagé entre applications côté HTML
│   ├── templates/
│   │   ├── base.html            # mise en page mobile d'abord
│   │   └── composants/          # fragments HTMX réutilisés
│   ├── static/
│   │   ├── css/app.css
│   │   └── js/htmx.min.js       # fourni localement, aucune dépendance réseau
│   └── templatetags/
│
├── scripts/                     # hors application
│   ├── import/                  # nettoyage ponctuel des CSV, scripts à usage unique datés
│   └── exploitation/            # sauvegarde PostgreSQL, rotation des journaux
│
├── deploy/                      # tout ce qui touche le serveur Windows
│   ├── nssm/installer_service.ps1
│   ├── iis/web.config           # ARR vers Uvicorn, auth Windows, en-têtes
│   ├── pont-mcp/
│   │   ├── pont_mcp.py          # stdio ↔ HTTP, transmet l'identité Windows
│   │   ├── construire.ps1       # PyInstaller → pont-mcp.exe
│   │   └── claude_desktop_config.exemple.json
│   └── gpo/README.md            # déploiement du pont et de la config par GPO
│
├── docs/
│   ├── design.md
│   ├── schema-donnees.md
│   ├── outils-mcp.md
│   ├── arborescence.md          # ce fichier
│   ├── exploitation.md          # (partie 2)
│   ├── tests.md                 # (partie 2)
│   ├── git.md                   # (partie 2)
│   ├── rituels-ia.md            # (partie 3)
│   ├── plan/
│   │   └── taches.md            # (partie 3) tickets ordonnés et leur état
│   └── adr/
│       ├── 0001-choix-du-stack.md
│       ├── 0002-code-de-reference-immuable.md      # (à écrire, tâche 02)
│       ├── 0003-pont-mcp-local-et-identite.md      # (à écrire, tâche 03)
│       └── 0004-aucune-ia-cote-serveur-au-mvp.md   # (à écrire, tâche 02)
│
└── tests/
    ├── conftest.py              # fixtures : base de test, missions d'exemple, client MCP
    └── e2e/                     # parcours complets : SOMAPEP de l'import à la note
```

## Modules futurs (dossiers non créés au MVP)

`veille/`, `extraction/`, `offres/`, `projets/`, `temps/` — chacun une
application Django au même format, ajoutée avec son ADR et ses tâches.

## Règles de rangement

- Une application Django = un domaine métier. Si deux applications
  s'importent mutuellement, c'est qu'il en manque une ou qu'il y en a une de
  trop.
- `moteur/` ne connaît ni la base, ni le web, ni les fichiers.
- `scripts/import/` contient des scripts jetables, datés, jamais importés
  par l'application.
- `deploy/` est la seule source de vérité pour le serveur : rien ne se
  configure à la main sur Windows sans être reporté ici.
