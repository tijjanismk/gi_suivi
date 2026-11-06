# ADR 0016 — Serveur MCP du module avis et pont du poste

- **Statut** : accepté par le porteur le 06/11/2026, avec les deux ajustements du § 4 (proposé le 27/10/2026)
- **Date** : 2026-10-27
- **Décideur** : le porteur
- **Remplace** : —
- **Complète** : ADR 0001 (condition 1, serveur MCP dans l'application ASGI), ADR 0007 (Kerberos
  vérifié par l'application), ADR 0013, `docs/outils-mcp.md`, `docs/design.md` § 3.3 et § 6

## Contexte

Claude Desktop doit pouvoir chercher des références, simuler un avis et proposer un avis ou un
critère (`docs/outils-mcp.md`). Depuis AV09, les neuf outils existent comme fonctions testées dans
`avis/outils_mcp.py` : ils passent par les services, comme les écrans, et n'écrivent que des
propositions et des critères en brouillon. Il reste à les exposer.

Deux points ne se tranchent pas sans le porteur :

- le SDK MCP officiel (`mcp`, avec `pydantic`, `starlette`, `httpx`, `sse-starlette`…) est une
  dépendance nouvelle ; `docs/rituels-ia.md` § 6 réserve cette décision au développeur, et le
  serveur n'installe que des roues binaires (`deploy/requirements.txt`, construit sur le poste) ;
- Claude Desktop n'atteint un serveur MCP interne que par un programme local sur le poste (le
  « pont »), qu'il faut installer sur chaque poste, comme l'agent GI-SUIVI.

## Décision proposée

### 1. Les outils : des fonctions de `avis/outils_mcp.py` (fait)

Chaque outil est une fonction documentée en français pour Claude, qui rend des données compactes
et des erreurs dites en clair (`{"erreur": …}`). Les écritures sont bornées : `creer_proposition`
crée une `Proposition` (règle 3), `enregistrer_brouillon_critere` un critère `brouillon` qui ne
compte pas dans la note avant qu'une personne l'enregistre. Aucun outil ne change un statut
d'avis, ne modifie une référence, ne renvoie un fichier.

### 2. Le serveur : FastMCP sous `/mcp/` dans l'application ASGI

Le SDK `mcp` (transport HTTP « streamable ») est monté sous `/mcp/` dans `config/asgi.py`, à côté
de Django ; chaque outil s'enregistre tel quel (`OUTILS`). Les appels à l'ORM passent par
`sync_to_async` (ADR 0001, conséquence assumée). Dépendance à ajouter à `pyproject.toml`, puis à
`deploy/requirements.txt` depuis le poste (`scripts/dev/exporter_dependances.py`), roues binaires
pour Python 3.14 vérifiées avant l'envoi.

### 3. Le pont du poste et l'identité

`pont-mcp.py`, lancé par Claude Desktop en stdio, relaie vers
`https://app.giconseils.local/mcp/` (ADR 0009) **en Negotiate**, avec le ticket Kerberos de la session
Windows (`requests-negotiate-sspi`, déjà utilisé par l'agent) : le serveur vérifie l'identité comme
pour les écrans (ADR 0007) ; on ne fait plus confiance à un en-tête posé par le poste (le « MVP »
de `docs/design.md` § 3.3 est abandonné). Les outils d'écriture sont réservés à `GI-Direction` et
`GI-Offres` ; la lecture suit la consultation des écrans. Le pont s'installe avec le kit des
postes (fichier de configuration de Claude Desktop), par la GPO existante ou à la main.

### 4. Ajustements du 06/11/2026 (décision du porteur)

- Le pont vise `https://app.giconseils.local/mcp/`, nom de l'environnement test depuis l'ADR 0009 ;
  `suivi-test` n'y reste qu'en alias, le temps de la transition.
- Avant de fusionner le montage dans `main`, on vérifie depuis le poste que le SDK `mcp` et toutes
  ses dépendances existent en roues binaires pour Python 3.14 (`deploy/requirements.txt`, construit
  par `scripts/dev/exporter_dependances.py`) : le serveur n'installe rien d'autre. S'il en manque une,
  la fusion attend et la décision revient au porteur.

## Justification

- Les outils, testés sans le SDK, ne dépendent pas du choix du transport : la décision qui reste
  porte sur le montage et l'installation, pas sur la logique.
- Kerberos de bout en bout réutilise ce qui marche déjà pour les écrans et l'agent, sans secret
  à distribuer.

## Conséquences

Positives :

- Claude Desktop lit la base et prépare propositions et barèmes ; l'humain valide à l'écran.

Négatives, assumées :

- Une dépendance de plus (et ses dépendances), à tenir à jour ; Django reste synchrone, les
  outils passent par `sync_to_async`.
- Un programme de plus sur chaque poste.

## Contre-argument conservé

Un serveur MCP séparé (FastAPI, processus à part) isolerait le SDK de Django, au prix d'un
second service Windows et d'un accès à la base hors de l'application (écarté par l'ADR 0001).

**Reconsidérer cette décision si** : le montage ASGI se révèle instable (ADR 0001, condition 1) ;
Claude Desktop accepte un jour un connecteur distant interne sans pont local.
