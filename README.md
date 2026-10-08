# GIC — Plateforme de réponse aux avis et de suivi des missions

GI-CONSEILS, Bureau d'Ingénieurs Conseils, Bamako.

## Ce que fait l'application

Elle répond en quelques secondes à des questions qui demandaient une
après-midi : « avons-nous deux études de conception d'ouvrages de
mobilisation des eaux de surface, réalisées depuis 2010, avec attestation
de bonne exécution ? » — et affiche à côté ce qui manque pour marquer
tous les points.

Trois façons d'y accéder, une seule base de données :

- **Claude Desktop**, par le serveur MCP : on pose la question en langage
  naturel, Claude interroge la base et propose ; un humain décide.
- **L'application web**, pour déposer un avis, saisir son barème, corriger
  une référence, valider ce que la veille propose.
- **Les scripts**, pour les imports et les tâches planifiées.

Toute la logique métier (éligibilité, notation, complétude des pièces) est
du Python déterministe, sans intelligence artificielle : la note calculée
pour Claude et la note affichée à l'écran sortent de la même fonction.

## Périmètre

| Module | État |
|---|---|
| `referentiel` — domaines, catégories, types d'ouvrages, localités, clients, bailleurs | MVP |
| `references` — missions et pièces justificatives | MVP |
| `experts` — vivier, diplômes, affectations | MVP |
| `avis` — avis, barèmes, file de validation, sélections | MVP |
| `mcp` — outils exposés à Claude Desktop | MVP |
| `veille` — collecte RSS / email / sites | après MVP |
| `extraction` — lecture automatique des TDR (API externe, isolée) | après MVP |
| `offres` — offres techniques et financières | après MVP |
| `projets` — suivi des missions gagnées, terrain | après MVP |
| `temps` — feuille de temps par projet | après MVP |

## Prérequis

- Windows Server 2025 (production) ou Windows 11 / Linux (développement)
- Python 3.14 (série courante ; 3.13 en repli)
- PostgreSQL 18 en production comme en développement (SQLite refusé, même en local)
- Accès en lecture au partage `\\SERVEUR\REFERENCES` (module avis, plus tard)

## Installation (poste de développement)

```powershell
git clone https://github.com/gi-conseils/gic.git
cd gic
py -3.14 -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.exemple .env          # puis mettre une SECRET_KEY longue et aléatoire

# Base locale : compte gic / base gic (mot de passe du super-utilisateur postgres demandé)
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -h localhost -f scripts\dev\creer_base_dev.sql

python manage.py migrate
```

En développement, aucun compte n'est à créer : le middleware `identite` injecte
l'utilisateur fictif de `UTILISATEUR_DEV`, membre des groupes de `GROUPES_DEV`
(par défaut `GI-Direction`, qui ouvre l'administration).

## Lancement

```powershell
# Application web (le serveur MCP sera monté sous /mcp/ avec le module avis)
uvicorn config.asgi:application --reload --port 8000

# Vérifications
curl http://localhost:8000/sante/                 # {"etat": "ok"} si la base répond
start http://localhost:8000/identite/qui-suis-je  # login et groupes vus par l'application
start http://localhost:8000/admin/                # racines, paramètres, exceptions
```

Dans Claude Desktop, déclarer le pont MCP local (voir `docs/exploitation.md`,
section « Pont MCP ») puis redémarrer Claude Desktop.

## Qualité

```powershell
ruff check . && ruff format --check .   # lint et format
pytest                                   # tests unitaires et d'intégration
pytest -m e2e                            # parcours de bout en bout (nécessite PostgreSQL)
```

## Documentation

- `CONTEXT.md` — à fournir à l'IA au début de chaque session de travail
- `docs/design.md` — conception : objectif, architecture, flux, alternatives écartées
- `docs/schema-donnees.md` — modèle de données commenté
- `docs/outils-mcp.md` — contrat des outils exposés à Claude Desktop
- `docs/exploitation.md` — installation en production, IIS, service Windows, sauvegardes
- `docs/adr/` — décisions d'architecture, numérotées, jamais réécrites

## Licence

Logiciel interne de GI-CONSEILS. Tous droits réservés.
