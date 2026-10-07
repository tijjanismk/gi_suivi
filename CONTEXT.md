# CONTEXT.md — à lire avant toute session de travail

Ce fichier donne à l'assistant IA (et à tout nouveau développeur) le contexte
nécessaire pour travailler sur le dépôt sans relire toute la documentation.
Il est court à dessein. S'il dépasse 150 lignes, c'est qu'une partie doit
partir dans `docs/`.

## Le projet en cinq lignes

Plateforme interne de GI-CONSEILS (bureau d'études, Bamako). Premier module
livré : GI-SUIVI, suivi d'activité par convention de dossiers (agent de poste
+ tableau de bord direction, voir ADR 0002). Second module : réponse aux
avis de marchés (AMI, DP, AO). Base PostgreSQL unique ; application web
Django pour les humains ; serveur MCP pour Claude Desktop ; logique métier
déterministe dans `moteur/`. Développeur unique assisté par l'IA. Hébergée
sur Windows Server 2025, derrière IIS, en service Windows, sans Docker.

## Architecture en un schéma

```
Claude Desktop (poste) ──stdio──► pont-mcp.py ──HTTP LAN──┐
Navigateur (poste / VPN) ──────────────────────HTTPS────► IIS (auth Windows)
                                                            │ REMOTE_USER
                                                            ▼
                                              Uvicorn ── Django ASGI
                                               ├── /mcp/   (FastMCP, outils)
                                               ├── /       (vues, HTMX)
                                               └── moteur/ (Python pur)
                                                            │
                                                     PostgreSQL 17
                                                            │
                                      \\SERVEUR\REFERENCES  (PDF, lecture seule)
```

## Règles d'architecture (non négociables sans ADR)

1. **`moteur/` n'importe jamais Django.** Il reçoit des objets Python simples
   (dataclasses) et rend des résultats simples. Les vues et les outils MCP
   l'appellent ; ils ne calculent rien eux-mêmes.
2. **Le code de référence (`GIC-HYD-ETU-043`) est attribué une fois et jamais
   modifié.** Domaine et nature existent aussi comme champs séparés ; ce sont
   eux qu'on filtre et qu'on corrige.
3. **Rien n'entre dans la base sans validation humaine** quand l'origine est
   automatique (veille, extraction, Claude). Le modèle `avis.Proposition`
   porte l'origine, les champs extraits et le statut de validation.
4. **Les fichiers restent sur le partage.** La base stocke un chemin UNC, pas
   le fichier. Lecture seule depuis l'application.
5. **Aucune IA côté serveur dans le MVP.** Claude Desktop traduit et propose
   via le MCP ; l'application compte. Quand l'extraction automatique des TDR
   arrivera, elle vivra dans `extraction/` derrière une seule fonction, et
   nulle part ailleurs.
6. **L'utilisateur vient d'IIS.** Pas de modèle de mot de passe, pas de page de
   connexion. En développement, un middleware injecte un utilisateur fictif.
7. **Périmètre tenu.** Pas de comptes maison, pas de chiffrement par colonne,
   pas de bureaux multiples, pas d'audit chaîné. Ces idées viennent de SIGMA
   (projet précédent) et ont été écartées : voir ADR 0001.

## Conventions de code

- Python 3.14 (série courante au 06/10/2026 ; 3.12 n'a plus d'installateurs), `ruff` pour lint et format (configuration dans `pyproject.toml`),
  longueur de ligne 100.
- Noms de modèles, champs, fonctions et tables **en français**, sans accents
  (`superficie_ha`, `piece_justificative`, `calculer_note`). Les mots-clés
  Django et Python restent en anglais, évidemment.
- Un modèle = une table = une responsabilité. Pas de champ « fourre-tout ».
- Chaque application Django : `models.py`, `services.py` (orchestration,
  appelle `moteur/`), `vues/`, `outils_mcp.py` si elle expose des outils,
  `tests/`.
- Types partout (`from __future__ import annotations`, dataclasses, `Decimal`
  pour les montants et les points — jamais `float`).
- Les migrations sont nommées (`0007_ajout_type_ouvrage.py`), jamais `auto_`.
- Un commit = un changement. Message en français au format
  `type(portée): résumé` — voir `docs/git.md`.

## Vocabulaire métier (ne pas inventer de synonymes)

| Terme | Sens | Modèle |
|---|---|---|
| Référence / mission | Un contrat exécuté par le bureau, prouvable | `references.Mission` |
| Pièce | Page de garde, page de signature ou attestation d'un contrat | `references.PieceJustificative` |
| Avis | AMI, DP ou AO reçu, avec son barème | `avis.Avis` |
| Critère | Une ligne du barème, décrite en données | `avis.Critere` |
| Proposition | Un avis candidat, pas encore validé | `avis.Proposition` |
| Sélection | Les références choisies pour un avis donné | `avis.Selection` |
| Expert | Une personne du vivier (interne ou externe) | `experts.Expert` |
| Affectation | Un expert sur une mission, à un poste | `experts.Affectation` |
| Type d'ouvrage | Entrée du thésaurus (seuil, micro-barrage…) | `referentiel.TypeOuvrage` |
| Quantité | Mesure caractéristique d'une mission (ha, km, forages) | `references.Quantite` |

## État du projet

Voir `docs/plan/taches.md` pour la liste ordonnée et l'état de chaque tâche.
Mettre à jour la section « En cours » ci-dessous à la fin de chaque session.

**En cours :** Phase 1 — socle Django (S01, S02, S06) sur la branche `dev/S01-socle-django` ;
moteur S03 à S05 fait ; agent v0.2.0 en pilote sur le poste du développeur (service G06 installé,
MSI G07 en attente de WiX). Phase 0 (serveur) toujours à faire.
**Dernière session :** 2026-10-07 — agent mis au point sur poste (CONTROLE.md : 1 à 4, 7 à 10
passés ; 5 et 6 restent), ADR 0003 (identification générique du fichier, PDF en navigateur,
tampon par utilisateur) et 0004 (supervision par service), socle Django écrit
**Prochaine étape :** base de développement (`scripts/dev/creer_base_dev.sql`), tests Django,
fusion de S01 ; décider la source des groupes AD (S02) ; P01 sauvegarde du serveur

## Ce que l'IA doit faire en début de session

1. Lire ce fichier, puis `docs/plan/taches.md` (section « En cours »).
2. Lire l'ADR le plus récent dans `docs/adr/`.
3. Ne proposer aucune nouvelle dépendance, aucun nouveau modèle, aucune
   nouvelle application sans le dire explicitement et sans proposer un ADR.
4. Écrire les tests avec le code, pas après.
