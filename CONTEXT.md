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
Navigateur (poste / VPN) ──────────────────────HTTPS────► IIS (proxy, anonyme)
                                                            │ Authorization: Negotiate
                                                            ▼
                                              Uvicorn ── Django ASGI
                                               ├── /mcp/   (FastMCP, outils)
                                               ├── /       (vues, HTMX)
                                               └── moteur/ (Python pur)
                                                            │
                                                     PostgreSQL 18
                                                            │
                                      \\AD-SERVEUR\GIC  (D:\GIC, lecture seule)
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
4. **Les fichiers restent sur le partage.** La base stocke un chemin (relatif au
   partage GIC) et une empreinte, pas le fichier. Lecture seule depuis l'application.
5. **Aucune IA côté serveur dans le MVP.** Claude Desktop traduit et propose
   via le MCP ; l'application compte. Quand l'extraction automatique des TDR
   arrivera, elle vivra dans `extraction/` derrière une seule fonction, et
   nulle part ailleurs.
6. **L'utilisateur vient de sa session Windows** (ticket Kerberos vérifié par
   l'application, ADR 0007). Pas de mot de passe, pas de page de connexion. En
   développement, un middleware injecte un utilisateur fictif.
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

## Pièges durables

Ce qui a coûté du temps et reviendra. Le récit complet : `docs/plan/journal.md`.

- **Serveur intouchable** (décision du 08/10) : sur AD-SERVEUR, rien d'existant n'est modifié,
  déplacé ni supprimé (partages, droits, disques, AD, stratégies existantes) ; on ajoute
  seulement (`C:\GIC`, `D:\GIC` par copie, PostgreSQL, IIS, tâches, GPO nouvelle).
- **Déploiement par Git seul**, aucun outil de développement sur le serveur : `gic.css`,
  `django.mo` et `deploy/requirements.txt` sont construits sur le poste et commités.
  `Tout-en-un.ps1` déploie `origin/main` sur `test` : ce qui est poussé y part.
- **Seul `main` sur GitHub fait foi** (dépôt privé, vérifier avant chaque envoi) ; un travail
  d'une autre session qui n'y est pas n'existe pas.
- **Identité** (ADR 0007) : l'application valide elle-même le ticket Kerberos ; IIS est en
  anonyme et ne fait que transmettre. Compte de service en Kerberos AES (RC4 refusé par
  Server 2025). Sonde : `/api/sante?identite=1`.
- **Adresses** (ADR 0009) : test = `https://app.giconseils.local` (`suivi-test` en alias jusqu'à
  son retrait), prod = `suivi` ; noms écrits seulement dans `deploy/noms-hotes.ps1`. Un nom de
  plus = DNS, SPN et certificat auto-signé à rediffuser aux postes par la GPO.
- **Uvicorn** : un seul processus de travail, sans `--proxy-headers` ; port libéré avant
  chaque démarrage (`deploy/liberer-port.ps1`) ; `/api/sante` donne le commit en service.
- **Windows Server 2025, contrôleur de domaine** : plus de `wmic` ; les cmdlets WMI se
  figent (`netsh`, `appcmd` en fin de script, lecteur `IIS:\`) ; `allowedServerVariables`
  au niveau serveur seulement ; les tâches planifiées tournent sous SYSTEM (le droit
  « ouvrir une session en tant que tâche » est retiré au compte de service par la stratégie
  des contrôleurs de domaine).
- **Gabarits** : classes préfixées `gic:` (ADR 0005), puis `scripts\dev\construire_css.ps1` ;
  nombres SVG avec `|unlocalize` (la virgule française rendait les barres invisibles) ;
  serveur de dev en `--noreload` : redémarrer après un changement de gabarit.
- **PowerShell 5.1** : BOM UTF-8 dans les `.ps1` ; les `.cmd` en CRLF sans BOM.
- **Chemins** : lettres de lecteur et nom complet du serveur ramenés à l'UNC court
  (`correspondance_lecteurs`) ; les chemins relatifs au partage s'écrivent en `\`.

## Début et fin de session

Voir `CLAUDE.md` (lu automatiquement par Claude Code) : lectures de début de session,
travail, rituel de fin de session et note de passation `docs/plan/en-cours.md`.
