# Stratégie de tests

Principe : **la logique métier se teste sans Windows, sans base et sans
navigateur**, parce qu'elle vit dans `moteur/`. Tout le reste (ORM, vues, API,
agent) est testé plus légèrement, sur ce qu'il ajoute vraiment.

## 1. Tests unitaires — `moteur/`

Outil : `pytest`, fonctions pures, pas de Django. Objectif : des centaines de
cas, exécutés en moins de cinq secondes, lancés avant chaque commit.

| Module | Ce qu'on teste | Exemples de cas |
|---|---|---|
| `moteur/suivi/segmentation.py` | Fusion des observations, clôture, inactivité | pause de 4 min comptée ; pause de 6 min retirée à partir de la dernière action ; verrouillage = inactif ; changement de fenêtre clôt le segment ; clôture forcée à 5 min ; `Document1` → `Courrier.docx` fusionné ; observation isolée sans suite |
| `moteur/suivi/classement.py` | Chemin → racine → dossier → code ; exceptions ; à classer | chemin sous `MISSIONS_EN_COURS\GIC-HYD-ETU-052_...` → code `GIC-HYD-ETU-052` ; chemin sous `AVIS\2026\2026-SOMAPEP-001_...` → code `2026-SOMAPEP-001` ; `H:\…` et `\\AD-SERVEUR\GIC\…` donnent le même dossier ; fichier sur le Bureau → à classer ; exception par préfixe l'emporte ; majuscules/minuscules et accents ignorés ; `~$rapport.docx` ignoré |
| `moteur/suivi/indicateurs.py` | Heures effectives, % prévu, arrivée/départ, amplitude, occupation | journée sans activité ; journée chevauchant minuit ; heures prévues à 0 (pas de division par zéro) ; semaine avec jour férié |
| `agent/gisuivi_agent/fichiers.py` | Extraction du fichier depuis un titre de fenêtre | titres enregistrés d'AutoCAD, QGIS, Acrobat, Bloc-notes, navigateur (doit rendre « aucun fichier ») |

Règles : un fichier de test par module ; un test = un comportement nommé en
français (`test_pause_de_six_minutes_est_retiree`) ; `Decimal` et dates
fixées avec `freezegun` ; jamais d'accès disque ni réseau.

## 2. Tests d'intégration — Django

Outil : `pytest-django`, base PostgreSQL de test (jamais SQLite : le
comportement des types et des index diffère). Objectif : vérifier que la
tuyauterie fait ce que `moteur/` a décidé.

| Ce qu'on teste | Comment |
|---|---|
| Ingestion `POST /api/segments` | Lot valide inséré ; même `lot_id` renvoyé deux fois → une seule insertion ; segment dont l'employé ≠ identité de la requête → rejeté ; `Poste` mis à jour |
| Classement à l'ingestion | Dossier inconnu créé `detecte` ; validation du dossier → recalcul des segments en attente |
| Autorisation | Utilisateur sans `GI-Direction` → 403 sur tous les écrans et routes direction ; `/api/moi/aujourdhui` ne rend que ses propres segments |
| Rapports | Sur un jeu de 50 segments fabriqués : totaux par employé, par dossier, arrivée/départ corrects ; filtres de période |
| Export Excel | Le classeur s'ouvre avec `openpyxl` ; six feuilles ; les cellules de total contiennent des formules, pas des nombres |
| Tâches | `suivi_purger` supprime au-delà de la rétention et rien d'autre ; `suivi_postes_muets` lève l'alerte rouge à 24 h ouvrées |
| Middleware `identite` | `REMOTE_USER` crée l'utilisateur et lit les groupes ; absence de l'en-tête en prod → 401 ; en dev → utilisateur fictif |

Fixtures : un `conftest.py` racine fournit `employes`, `postes`, `racines`,
`dossiers` et une fabrique `faire_lot(n, ...)` qui produit des lots
réalistes. Les tests d'intégration ne dépassent pas une minute au total.

## 3. Tests de bout en bout

Outil : `pytest -m e2e`, client Django + base PostgreSQL, sans navigateur
(l'interface est du HTML rendu côté serveur ; un test de rendu suffit).

Un seul parcours au MVP, celui qui résume le produit : **trois lots
d'activité d'un employé fictif sur deux dossiers et un fichier du Bureau →
la vue d'ensemble affiche ses heures, la vue dossiers la répartition, la file
« à classer » le fichier du Bureau ; la direction rattache ce fichier → les
totaux bougent ; l'export Excel contient les mêmes chiffres.** Si ce test
passe, le produit fait ce qu'il promet.

Pas de Playwright ni de Selenium au MVP : le coût de maintenance est
disproportionné pour huit écrans HTMX lus par trois personnes. À reconsidérer
si des interactions complexes apparaissent.

## 4. Tests de l'agent — sur un poste Windows, à la main

Les tests marqués `windows` ne tournent pas dans la CI. Avant chaque
construction de MSI, sur un poste du domaine, le développeur exécute
`pytest agent/tests -m windows` puis une **liste de contrôle manuelle**
conservée dans `agent/CONTROLE.md` :

1. Ouvrir Word sur un fichier du partage → le segment porte le bon chemin UNC.
2. Ouvrir un PDF depuis le Bureau → le segment est « à classer ».
3. Rester 6 minutes sans toucher au clavier → le temps est retiré.
4. Verrouiller l'écran 2 minutes → rien n'est compté.
5. Débrancher le réseau 10 minutes, travailler, rebrancher → les segments arrivent, une seule fois.
6. Fermer la session et la rouvrir → l'agent redémarre seul (icône visible).
7. Gestionnaire des tâches après une heure : processeur < 1 %, mémoire < 80 Mo.
8. Tuer `gisuivi-agent.exe` → relancé dans la minute par le service.

Le résultat (date, poste, version, 8 cases cochées) est collé dans la
description de la pull request qui publie le MSI.

## 5. Ce qu'il n'est PAS utile de tester

- Les écrans pixel par pixel ou les feuilles de style : revue visuelle à la
  main, c'est plus rapide et plus juste.
- L'ORM Django, `openpyxl`, `pywin32` : ce sont des bibliothèques testées
  par leurs auteurs ; on teste ce qu'on en fait, pas elles.
- L'authentification Kerberos elle-même : elle appartient à IIS et à l'AD.
  On teste que l'application fait confiance à `REMOTE_USER` et refuse son
  absence ; la page `/identite/qui-suis-je` sert de test manuel après chaque
  déploiement.
- Les migrations une à une : `makemigrations --check` dans la CI suffit à
  garantir qu'elles sont à jour.
- Les performances avant d'avoir des données : on mesure au pilote, on
  optimise si une vue dépasse 2 secondes.

## 6. Couverture

Objectif : 100 % sur `moteur/` (c'est petit et c'est le cœur), 80 % sur
`suivi/` et `identite/`, aucun objectif chiffré sur les vues HTML. La CI
affiche la couverture ; elle ne bloque pas dessus — un seuil bloquant
pousse à écrire de mauvais tests pour faire monter un chiffre.
