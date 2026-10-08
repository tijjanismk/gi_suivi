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

**En cours :** Phase 1 — S01, S03 à S06 faits ; S02 fait — groupes AD par l'API Windows du DC, `pywin32`, ADR 0006 (ex-« ADR à
écrire) ; S07 attend le serveur. T01 (interface) commencé : thème Unfold (ADR 0005), menu,
accueil à indicateurs, français, groupe de consultation seule `GI-Direction-Lecture`. Agent
v0.2.0 en pilote sur le poste du développeur (service G06 installé, MSI G07 en attente de WiX).
Phase 0 (serveur) toujours à faire.
**Dernière session :** 2026-10-08 — interface Unfold fusionnée, catalogue français du thème
(`locale/fr`, compilé par `scripts/dev/compiler_traductions.py`), compte « visionneuse » en
lecture seule côté application (groupe AD à créer en P04) ; **A01 fait** : `POST /api/segments`
(validation, idempotence par `lot_id`, identité = personne authentifiée, employé par SID ou
login — `sid_ad` facultatif, migration 0003 —, poste tenu vivant, classement à la réception,
1 000 segments < 1 s) ; **A02 fait** : dossier conforme jamais vu créé « détecté » à la réception, segments rattachés. **A03 fait** : file de recalcul (`DemandeRecalcul`, signaux sur exceptions et racines, `valider_dossier`), commande `suivi_recalculer`, action « Valider » dans l'admin, exception à effet immédiat. **A04 fait** : `GET /api/moi/aujourdhui` (sa propre journée, rien d'autre), `GET /api/racines` (ce que l'agent lit), page `/moi` ouverte par l'icône de l'agent. **A05 fait** : rapports JSON pour la direction et la consultation (`/api/rapports/synthese`, `/api/rapports/dossiers`, `/api/employes/{id}/activite`, `/api/dossiers`, `/api/aclasser`, `/api/postes/etat`, période `debut`/`fin`), jeu de 64 segments dans `conftest.py`. **A06 fait** : actions direction (`POST /api/dossiers/{id}/valider`, `PUT /api/dossiers/{id}`, `POST /api/aclasser/{id}/rattacher` → exception + recalcul), journal d'accès sur chaque action et consultation ; `/api/segments` réservé à l'en-tête `User-Agent: GiSuivi-Agent/`. **A07 fait** : `suivi_purger` (rétention en mois, `--simuler`), `suivi_postes_muets` (rouge/orange, code de sortie 1 si rouge, `--remettre-demarrages` le lundi), `/api/sante` ; `deploy/taches.ps1` aligné. **Phase 2 (API) terminée.** **T02 fait** : vue d'ensemble `/suivi/` (quatre indicateurs, barres SVG par personne, tableau jour × employé coloré, arrivée/départ), sélecteur de période dans l'URL (T09 en cours), `suivi_jeu_demo` (deux semaines de données de démonstration déterministes). **T03 fait** : écran Dossiers `/suivi/dossiers/` (barres par dossier, tableau dossier × personne, hors dossier). **T04 fait** : écran Personnes `/suivi/personnes/` (état indicatif, heures, % prévu, dernière activité) et fiche `/suivi/personnes/{id}/` (journées cliquables, chronologie SVG du jour colorée par dossier, fichiers, applications). **T05 fait** : gestion des dossiers `/suivi/gestion-dossiers/` (racines en lecture, détectés à valider avec temps déjà enregistré, actifs modifiables, clore/rouvrir ; formulaires POST + redirection, consultation seule sans boutons). **T06 fait** : file « à classer » `/suivi/a-classer/` (groupes fichier × personne, rattachement en un clic par exception — chemin exact, dossier parent, mot-clé —, brouillons signalés, nom seul non rattachable) ; `services.rattacher` partagé avec l'API. **T07 fait** : état des postes `/suivi/postes/` (alertes rouge/orange, version, dernier envoi, heures ouvrées muettes, démarrages, dernière personne). **T08 fait** : export Excel `/suivi/export.xlsx` (six feuilles, totaux en formules, en-têtes figés, nom daté ; bouton sur chaque écran à période). **T09 et T01 faits** : filtre dossier sur la vue d'ensemble, les personnes, la fiche et l'export ; menu des écrans, mise en page, page de refus. **Phase 4 (tableau de bord) terminée.** Puis, sur retour du porteur (08/10) : écran **Journée** `/suivi/journee/` (accueil du site : chaque personne, un jour, arrivée/départ, actif, pauses, hors mesure, frise) et détail bloc par bloc `/suivi/journee/{id}/` ; menu : groupe Écrans en tête (demande du 08/10, après un premier essai Suivi en haut), puis Suivi, Classement, Administration ; nombres SVG avec `|unlocalize` (le format français mettait une virgule : barres invisibles) ; icônes de cartes en ligne (le filigrane Unfold paraissait coupé). 176 tests, couverture 98 %, plus le parcours de bout en bout `tests/e2e/test_parcours.py` (trois lots → écrans → rattachement → export cohérent). **Chaîne réelle vérifiée sur ce poste** : l'agent installé envoie au serveur de dev (`url_api` 127.0.0.1:8010, `.env` UTILISATEUR_DEV=GICONSEILS\USER) — 236 segments repris en un coup, 0 doublon (G03 fait, CONTROLE n° 5 en partie). Projets de documents du pilote dans `docs/pilote/` (note à l'équipe D01, relevé manuel D03), à valider par la direction. Vérifié aussi en direct contre le serveur de
développement. Un login propre à l'application a été écarté (CONTEXT.md r. 6 et 7, ADR 0001).
**Fiche personne enrichie** (`/suivi/personnes/{id}/`, « la partie la plus importante du logiciel »
pour le porteur) : totaux de la période, tableau jour par jour (arrivée → départ, actif, pauses,
hors mesure, % prévu, mini-frise), chronologie du jour choisi bloc par bloc avec pauses, lien
vers l'écran Journée ; le filtre dossier ne touche que fichiers et logiciels, la journée reste
entière. Frise et couleurs partagées dans `suivi/vues/frise.py` (plus d'import croisé
direction ↔ journee). **Déploiement par Git, et Git seul** : `deploy/installer.ps1 -Env test -Ref main`
clone/met à jour `C:\GIC\depot` (jeton GitHub lecture seule, dépôt privé) ; en prod `-Ref` est un
tag ; liste de contrôle imprimable `docs/exploitation/liste-de-controle-serveur.md`. **Aucun
outil de développement sur le serveur** (décision du porteur 08/10) : `gic.css`, `django.mo` et
`deploy/requirements.txt` (généré par `scripts/dev/exporter_dependances.py`, contrôlé par
`verifier.ps1`) sont construits sur le poste et commités ; le serveur fait `pip install
--only-binary=:all: -r deploy/requirements.txt`, sans `pip install -e .`. `deploy/verifier.ps1`
et `deploy/sauvegarde_pg.ps1` écrits ; la voie « archive zip » (`publier.ps1`) est supprimée. **Serveur : on ne touche à
rien de ce qui existe** (décision du porteur 08/10) : partages, droits, fichiers et disques restent
tels quels (inventaire du 06/10 : HP ProLiant ML350e Gen8 v2, Windows Server 2025, 8 Go, deux SSD
TEAM de 1 908 Go sains, `C:` = disque 1 à 98 % libre, `D:` = disque 2 à 85 % libre, soit déjà la
séparation système/données que les scripts supposent — pas de repartitionnement) ; les scripts n'**ajoutent** que
`C:\GIC`, `D:\GIC` (par copie, duplication acceptée), PostgreSQL, IIS ; `Rangement-GIC.ps1
-GelerAnciens` désactivé, plus de passage en `_ANCIEN` ni de suppression de partages. Même règle
pour l'application d'avis à venir. **Agent
0.2.2**, kit d'installation manuelle `agent\preparer-kit.ps1 -Config .\config-pilote.json` (pas de
GPO pour l'instant, D02 reporté) : `C:\dev\livraisons\agent\GiSuivi-agent-0.2.2-poste.zip`,
`url_api` = serveur test, premier poste Dicko. **HTTPS sans autorité interne** (inventaire 06/10 :
pas d'AD CS ; IIS déjà en service sur 80/443 pour RDWeb — nos sites sont liés par nom d'hôte, SNI) :
`08-Python-IIS.ps1 -AutoSigne` crée un certificat auto-signé 5 ans et l'exporte en
`C:\GIC\deploy\gic-serveur.cer` ; `installer-poste.ps1` l'importe dans les autorités racines du
poste ; l'agent vérifie avec le magasin Windows (`truststore`), plus avec certifi.
**Prochaine étape (engagée le 08/10) :** déploiement de l'environnement test sur AD-SERVEUR par le
porteur en suivant `docs/exploitation/liste-de-controle-serveur.md` (P01 sauvegarde d'abord,
scripts 01→08 avec `-AutoSigne`, puis `installer.ps1 -Env test -Ref main`, `verifier.ps1`) ;
rapporter `C:\GIC\deploy\gic-serveur.cer` dans le kit ; installation manuelle de l'agent chez Dicko
(note D01 signée avant) ; puis reprise des étapes non faites (CONTROLE n° 6, WiX, P05, pilote D03-D05). Toujours
`scripts\dev\verifier.ps1` avant d'envoyer (docs/git.md). Penser à `manage.py migrate` sur la
base de dev après chaque nouvelle migration (la base de test, elle, est recréée). Après un
changement de gabarit ou de classes : `scripts\dev\construire_css.ps1` (classes préfixées
`gic:`, ADR 0005) puis redémarrer le serveur de dev (cache des gabarits, `--noreload`).

## Ce que l'IA doit faire en début de session

1. Lire ce fichier, puis `docs/plan/taches.md` (section « En cours »).
2. Lire l'ADR le plus récent dans `docs/adr/`.
3. Ne proposer aucune nouvelle dépendance, aucun nouveau modèle, aucune
   nouvelle application sans le dire explicitement et sans proposer un ADR.
4. Écrire les tests avec le code, pas après.
