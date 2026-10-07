# ADR 0001 — Choix du stack technique

- **Statut** : accepté
- **Date** : 2026-10-06
- **Décideur** : développeur principal, après revue d'architecture assistée
- **Remplace** : —

## Contexte

GI-CONSEILS a besoin d'un système interne pour répondre aux avis de marchés,
accessible par Claude Desktop (serveur MCP) et par une application web, sur
un Windows Server 2025 avec Active Directory, sans Docker, développé et
maintenu par une seule personne.

Contraintes retenues :

- Claude Desktop seulement ; aucune API d'IA côté serveur dans le MVP.
- Claude Desktop ne peut atteindre un serveur MCP interne que par un
  processus local sur le poste (les connecteurs distants exigent une URL
  HTTPS publique).
- Indépendance vis-à-vis du fournisseur d'IA : l'IA doit rester une pièce
  remplaçable.
- Priorité à la simplicité : un seul langage, le moins de bibliothèques
  possible.
- La première année est dominée par l'assainissement de ~240 références
  héritées de fichiers Word hétérogènes.
- Le développeur maîtrise Django et PostgreSQL (projet précédent SIGMA,
  171 fichiers, abandonné pour excès de périmètre).

Options comparées : (A) Django monolithe, (B) FastAPI + SQLAlchemy +
FastMCP, (C) FastMCP + admin généré sans interface sur mesure. Un stack mixte
Python + ASP.NET a été écarté d'emblée (deux langages pour une personne).

## Décision

**Option A : Django 5, PostgreSQL 17, serveur MCP (SDK Python officiel,
FastMCP) monté dans l'application ASGI de Django, templates + HTMX,
pytest, IIS en frontal pour l'authentification Windows, Uvicorn en service
Windows.**

Avec trois conditions :

1. **Prototype MCP en première semaine** : un outil `rechercher_missions`
   fonctionnel depuis Claude Desktop avant toute autre fonctionnalité. Si le
   montage ASGI/async se révèle instable ou lent (> 2 s par appel simple, ou
   erreurs de connexion ORM non résolues en 5 jours), basculer sur l'option B
   avant d'avoir investi davantage.
2. **Couche métier `moteur/` indépendante de Django**, Python pur, testée
   seule. Les vues et les outils MCP y délèguent tout calcul.
3. **Périmètre tenu** : pas de comptes maison, pas de chiffrement par
   colonne, pas de bureaux multiples, pas d'audit chaîné dans le MVP. Tout
   ajout de ce type exige un ADR.

## Justification

Le facteur décisif n'est pas la familiarité du développeur avec Django mais
la nature de la première année : des milliers de corrections humaines sur
des données hétérogènes. L'admin et les formulaires de Django sont l'outil le
plus rapide en Python pour les outiller sans écrire d'écrans. La maîtrise du
framework est un multiplicateur, pas la raison.

Le modèle de données de SIGMA est repris comme base d'analyse (barème en
données, quantités typées, localités hiérarchiques, pièces vérifiées) ; son
code n'est pas repris.

## Conséquences

Positives :

- Temps jusqu'au premier résultat utile le plus court des options comparées.
- Une seule documentation de framework ; cycle de versions prévisible.
- L'admin Django sert d'outil d'assainissement dès le premier jour.

Négatives, assumées :

- Django est synchrone par culture ; les outils MCP accéderont à l'ORM via
  `sync_to_async` ou un exécuteur dédié. Moins élégant qu'un stack async
  natif.
- Application plus lourde que nécessaire pour la partie MCP seule.
- Risque de reconstruire SIGMA par habitude : parade par la condition 3.

## Contre-argument conservé

FastAPI aurait été le meilleur choix si l'interface web n'était qu'un outil
de correction secondaire : les outils MCP y sont des fonctions async
ordinaires, Pydantic sert à la fois de validation et de documentation pour
Claude, et le stack est aujourd'hui le socle dominant des nouveaux services
Python.

**Reconsidérer cette décision si** : le prototype de la condition 1 échoue ;
après trois mois, Claude Desktop représente plus de 80 % des usages ; les
automates (veille, extraction) deviennent les principaux clients et exigent
une API JSON ; un second développeur formé à FastAPI rejoint le bureau. La
condition 2 rend cette migration coûteuse mais possible.
