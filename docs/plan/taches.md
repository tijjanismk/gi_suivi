# Plan de tâches — GI-SUIVI jusqu'au pilote

Chaque tâche tient en une session de travail (une demi-journée à une
journée) et correspond à une branche `dev/<id>-<mot-clé>` et une pull
request. L'état est tenu ici : `à faire` → `en cours` → `fait (tag)`.

Préfixes : `P` préalables serveur (hors code), `S` socle et moteur, `A` API,
`G` agent, `T` tableau de bord, `D` déploiement et pilote.

## Phase 0 — Décisions et serveur (semaines 1-2)

| Id | Titre | Description | Critères d'acceptation | État |
|---|---|---|---|---|
| P01 | Sauvegarde complète de l'état du système | `wbadmin` vers D:, vérification, copie sur USB dès que possible | `wbadmin get versions` montre la sauvegarde ; un fichier restauré avec succès | à faire |
| P02 | Bureau à distance limité au réseau local | Règle de pare-feu `192.168.2.0/24`, NLA activée, test depuis un poste | Connexion RDP depuis le LAN fonctionne ; retour arrière documenté | à faire |
| P03 | Mises à jour Windows | Appliquer les mises à jour en attente, redémarrer hors heures, planifier les suivantes | `Get-HotFix` montre une mise à jour de moins de 30 jours | à faire |
| P04 | Groupes AD et compte de service | Créer `GI-Direction`, `GI-Direction-Lecture` (consultation seule : compte « visionneuse » pour la personne qui suit le travail de la direction sans agir), `GI-Offres`, `GI-Ingenieurs`, `GI-Administratif`, `GI-Terrain`, `GI-Application`, `svc-application` ; comptes d'administration nominatifs | Groupes peuplés selon la liste validée par la direction ; `Administrateur` n'est plus utilisé au quotidien | à faire |
| P05 | Décisions du blueprint consignées | Racines de classement, convention de nommage des dossiers, membres de `GI-Direction`, heures prévues, rétention, note à l'équipe | Décisions écrites dans un ADR `docs/adr/00NN-decisions-suivi.md` (prochain numéro libre ; 0003 et 0004 sont pris par l'agent), signées par la direction | à faire |
| P06 | Partage `GIC` et racines | Créer `D:\GIC` avec `MISSIONS_EN_COURS`, `AVIS\2026`, droits par groupes ; y déplacer les dossiers de projet existants selon la convention | Au moins 10 dossiers de projet rangés sous une racine avec un nom conforme | à faire |
| P07 | Mémoire du serveur | Devis et commande de 16 Go au minimum | Commande passée ; date d'installation connue | à faire |

## Phase 1 — Socle (semaines 2-3)

| Id | Titre | Description | Critères d'acceptation | État |
|---|---|---|---|---|
| S01 | Squelette du dépôt | Projet Django `config/`, applications vides `identite`, `suivi`, paquet `moteur/`, `pyproject.toml`, `.env.exemple`, pre-commit, CI, `CONTEXT.md` | CI verte sur une PR vide ; `manage.py check` passe ; README permet d'installer en local en 10 minutes | fait (non tagué) |
| S02 | Middleware d'identité | `REMOTE_USER` / `X-Remote-User` depuis 127.0.0.1 → `Utilisateur` ; groupes via LDAP mis en cache ; utilisateur fictif en dev ; page `/identite/qui-suis-je` ; décorateur `@groupe_requis` | Tests : création à la première requête, refus sans en-tête en prod, 403 hors groupe ; page affiche login et groupes | en cours |
| S03 | Moteur : segmentation | `moteur/suivi/segmentation.py` + types ; règles 7.1 et 7.3 du blueprint | 20 cas de test au moins (pauses, verrouillage, clôture, brouillon) ; 100 % de couverture du module | fait (non tagué) |
| S04 | Moteur : classement | `moteur/suivi/classement.py` : normalisation lettre → UNC, racines à profondeur, extraction du code, exceptions, à classer, fichiers ignorés | 20 cas de test ; même dossier obtenu par `H:\` et par UNC ; code `GIC-…` et `AAAA-…` extraits | fait (non tagué) |
| S05 | Moteur : indicateurs | `moteur/suivi/indicateurs.py` : heures effectives, % prévu, arrivée/départ, amplitude, occupation, par jour et par période | Cas limites couverts (journée vide, minuit, heures prévues 0) | fait (non tagué) |
| S06 | Modèles et migrations | `Employe`, `Poste`, `Segment`, `Dossier`, `Racine`, `Exception`, `JournalAcces`, `Parametre` ; index ; admin pour `Racine`, `Parametre`, `Exception` | `makemigrations --check` propre ; admin permet de saisir les racines et paramètres ; fixtures `conftest.py` | fait (non tagué) |
| S07 | IIS et Kerberos en environnement test | Site `suivi-test`, SPN, certificat, web.config, service NSSM `GIC-Test`, `qui-suis-je` depuis un poste | Depuis un poste du domaine, sans mot de passe, la page affiche l'utilisateur et `GI-Direction` ; en-tête `Authorization: Negotiate` observé (pas NTLM) | à faire |

## Phase 2 — API (semaines 3-5)

| Id | Titre | Description | Critères d'acceptation | État |
|---|---|---|---|---|
| A01 | Ingestion des lots | `POST /api/segments` : validation, idempotence par `lot_id`, `bulk_create`, mise à jour de `Poste`, contrôle employé = identité | Tests : lot valide, doublon, usurpation refusée, lot vide ; 1 000 segments en moins d'une seconde | fait (non tagué) |
| A02 | Classement à l'ingestion et dossiers détectés | Appel de `moteur.suivi.classement` ; création des dossiers `detecte` ; statuts | Test : un lot crée un dossier détecté avec le bon code et un segment à classer | fait (non tagué) |
| A03 | Recalcul | Commande `suivi_recalculer` + file de recalcul déclenchée par validation d'un dossier ou création d'une exception | Test : validation → segments en attente rattachés ; segments bruts inchangés | fait (non tagué) |
| A04 | `/api/moi/aujourdhui` et `/api/racines` | Activité du jour de l'utilisateur courant ; liste des racines et correspondances pour l'agent | Un utilisateur ne voit que ses segments ; racines renvoyées telles que saisies dans l'admin | fait (non tagué) |
| A05 | Points d'accès des rapports | `/api/rapports/synthese`, `/api/rapports/dossiers`, `/api/employes/{id}/activite`, `/api/dossiers`, `/api/aclasser`, `/api/postes/etat`, paramètres `debut`/`fin` | Tests sur la fixture de 50 segments ; réservé à `GI-Direction` | à faire |
| A06 | Actions direction | `POST /api/dossiers/{id}/valider`, `PUT /api/dossiers/{id}`, `POST /api/aclasser/{id}/rattacher` (dossier ou exception) ; journal d'accès | Chaque action journalisée avec utilisateur, cible, horodatage | à faire |
| A07 | Tâches planifiées | `suivi_purger`, `suivi_postes_muets` ; `/api/sante` | Tests de la purge (rien avant la rétention) et des seuils d'alerte | à faire |

## Phase 3 — Agent (semaines 4-8, en parallèle de la phase 2)

| Id | Titre | Description | Critères d'acceptation | État |
|---|---|---|---|---|
| G01 | Observation | `observation.py` : fenêtre active, processus, titre, inactivité, verrouillage/veille | Sur un poste de test, un journal d'observations toutes les 5 s correct pendant 30 min | en cours |
| G02 | Reconnaissance des fichiers | `fichiers.py` : COM Office ; règles par titre pour AutoCAD, QGIS, Acrobat, Bloc-notes ; navigateurs sans titre | Tests hors Windows sur 30 titres enregistrés ; sur poste : Word, Excel, AutoCAD donnent le chemin exact ou le nom | en cours |
| G03 | Tampon et lots | `tampon.py` : SQLite, `lot_id`, acquittement, purge 7 jours | Coupure simulée : rien de perdu, rien en double | à faire |
| G04 | Envoi Negotiate | `envoi.py` : `requests` + `pyspnego`, repli NTLM journalisé, attente exponentielle | Lot reçu par l'API test avec l'identité Kerberos de la session ; 401 et 5xx gérés | à faire |
| G05 | Icône et « mon activité du jour » | `pystray`, trois états, menu, ouverture du navigateur | Icône visible dès l'ouverture de session ; pas de « Quitter » | en cours |
| G06 | Service de supervision | `gisuivi_service` : énumération des sessions, relance de la tâche | Agent tué → relancé en moins d'une minute | fait (non tagué) |
| G07 | Empaquetage | `construire.ps1`, PyInstaller `--onedir`, WiX, registre, signature | MSI installable et désinstallable proprement sur un poste vierge ; version lisible dans le registre | en cours |
| G08 | Point de contrôle ADR 0002 | Mesure sur un poste pendant une journée : processeur, mémoire, stabilité ; liste `agent/CONTROLE.md` | < 1 % CPU, < 80 Mo, 8 cases cochées — sinon décision écrite de réécrire l'agent en .NET | en cours |

## Phase 4 — Tableau de bord (semaines 6-9)

| Id | Titre | Description | Critères d'acceptation | État |
|---|---|---|---|---|
| T01 | Gabarit et navigation | `base.html` mobile d'abord, menu des huit écrans, page de refus hors `GI-Direction`, HTMX local | Toutes les pages s'affichent avec le bon utilisateur ; refus propre | en cours |
| T02 | Vue d'ensemble | Quatre indicateurs, barres par employé (SVG serveur), tableau jour × employé coloré, % prévu, arrivée/départ | Validée par la direction sur `test` avec la fixture | à faire |
| T03 | Dossiers | Barres par dossier, tableau dossier × employé | idem | à faire |
| T04 | Employés et fiche employé | Liste avec état indicatif ; fiche : chronologie colorée par dossier, fichiers et applications | idem | à faire |
| T05 | Gestion dossiers | Racines (lecture), nouveaux dossiers détectés avec temps déjà enregistré, bouton Valider, dossiers actifs éditables | Validation d'un dossier déclenche le recalcul et met à jour les écrans | à faire |
| T06 | À classer | File groupée, rattachement en un clic, création d'exception, brouillons signalés | Le compteur baisse après rattachement | à faire |
| T07 | État des postes | Version, dernier envoi, démarrages, alertes orange et rouge | Un poste muet depuis 24 h ouvrées apparaît en rouge | à faire |
| T08 | Export Excel | `openpyxl`, six feuilles, formules, nom de fichier daté | Classeur ouvert dans Excel ; totaux recalculés si on modifie une cellule | à faire |
| T09 | Sélecteur de période et filtre dossier | 7 jours, semaine, 30 jours, mois, dates libres ; filtre dossier sur toutes les vues | Les URL portent la période (partageables) | à faire |

## Phase 5 — Pilote (semaines 9-11)

| Id | Titre | Description | Critères d'acceptation | État |
|---|---|---|---|---|
| D01 | Note à l'équipe et réunion | Rédiger avec la direction la note d'information (ce qui est collecté, ce qui ne l'est pas, à quoi ça sert, qui voit quoi, durée de conservation) ; réunion ; volontaires désignés | Note signée et diffusée avant tout déploiement d'agent | à faire |
| D02 | GPO pilote | OU `Postes-Pilote`, GPO liée, paramètres registre, exclusion Defender | Agent installé automatiquement sur les 2-3 postes au redémarrage | à faire |
| D03 | Relevé manuel des volontaires | Modèle d'une page : heures et dossiers par jour, une semaine | Trois relevés remplis | à faire |
| D04 | Comparaison et corrections | Heures mesurées vs relevés ; écart par jour et par personne ; file à classer ; retours | Écart < 10 % ; < 10 % du temps à classer après une semaine ; aucune gêne signalée | à faire |
| D05 | Rapport de pilote | Résultats, corrections faites, décision de généraliser ou non | Validé par la direction | à faire |

## Phase 6 — Généralisation (semaines 11-12)

| Id | Titre | Description | Critères d'acceptation | État |
|---|---|---|---|---|
| D06 | Production | `installer.ps1 -Env prod`, site `suivi`, tâches planifiées, sauvegarde `pg_dump`, tag `v1.0.0` | Liste de contrôle de `docs/exploitation.md` § 5 cochée | à faire |
| D07 | GPO sur tous les postes | Lier la GPO à l'OU des postes ; suivre « État des postes » une semaine | Tous les postes envoient depuis 5 jours ouvrés | à faire |

## Ensuite

Le module avis reprend à partir de ce socle : ses tâches seront ajoutées ici
quand GI-SUIVI sera en pilote, à partir de `docs/design.md` et de
`docs/schema-donnees.md`.
