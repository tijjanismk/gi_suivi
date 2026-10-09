# Document de conception

Version 1 — octobre 2026. Mis à jour quand l'architecture change ; les
décisions ponctuelles vont dans `docs/adr/`.

## 1. Objectif

Permettre à GI-CONSEILS de décider en minutes, et non en heures, s'il peut
répondre à un avis de marché, avec quelles références, quels experts et quelle
note probable ; puis de constituer le dossier sans oublier une pièce.

Mesures de succès du MVP, sur un avis réel (SOMAPEP 09/2026/001 ou PARCB) :

- Saisir l'avis et son barème en moins de 15 minutes.
- Obtenir la liste des références éligibles et la note simulée en moins d'une
  minute, depuis l'application comme depuis Claude Desktop.
- Obtenir la liste des pièces manquantes classée par points en jeu.
- Obtenir, par profil demandé, les experts du vivier qui répondent aux
  exigences (années d'expérience, nombre de références).

## 2. Utilisateurs

| Rôle | Qui | Accès |
|---|---|---|
| Responsable des offres | 2-3 personnes | Web + Claude Desktop, toutes les opérations |
| Ingénieur | tous | Web + Claude Desktop, consultation, correction de ses missions |
| Direction | 1-2 | Web, tableaux de bord, décisions de réponse |
| Agent de terrain (module projets, plus tard) | variable | Web mobile via VPN |
| Automates (veille, extraction, plus tard) | — | Écrivent uniquement des propositions |

L'identité vient d'Active Directory via IIS. Les rôles sont des groupes AD
(`GIC-Offres`, `GIC-Direction`) lus dans l'en-tête transmis par IIS ; le MVP
peut vivre avec deux rôles : lecteur et éditeur.

## 3. Architecture

### 3.1 Vue d'ensemble

Une seule application ASGI Django sert trois façades sur une même couche
métier :

- `/` : vues HTML (templates Django + HTMX), interface de saisie et de
  consultation, pensée mobile dès le départ.
- `/mcp/` : serveur MCP (SDK Python officiel, FastMCP) exposant des outils à
  Claude Desktop. Transport HTTP sur le réseau local ; chaque poste exécute un
  pont stdio minimal déployé par GPO.
- Commandes `manage.py` : imports, maintenance, tâches planifiées.

La couche métier est le paquet `moteur/`, Python pur, sans Django : il reçoit
des dataclasses et rend des dataclasses. Les vues et les outils MCP y
délèguent tout calcul. Les services Django (`services.py` de chaque
application) font le lien : lire en base, convertir, appeler `moteur/`,
écrire le résultat.

### 3.2 Pourquoi cette séparation

- Une seule implémentation de la note : l'écran et Claude ne peuvent pas
  diverger.
- `moteur/` se teste sans base de données, en millisecondes, avec des
  centaines de cas.
- Si le framework web change un jour (voir ADR 0001, contre-argument
  FastAPI), `moteur/` et les tests survivent intacts.

### 3.3 Identité et droits

Le poste présente son ticket Kerberos (`Authorization: Negotiate`) ; IIS le
transmet tel quel et **l'application le valide elle-même** (SSPI, sous le compte
de service porteur des SPN — ADR 0007 ; le schéma initial « IIS authentifie et
transmet `REMOTE_USER` » reste possible avec `IDENTITE_SOURCE = "iis"`). Les
groupes AD sont lus par l'API Windows du contrôleur de domaine (ADR 0006). Un
middleware Django crée ou met à jour un `identite.Utilisateur` minimal (login,
nom affiché, groupes). Il n'y a ni mot de passe ni page de connexion. En
développement, un utilisateur fictif est injecté. **Le module avis réutilisera
ce mécanisme tel quel** : mêmes utilisateurs, mêmes groupes (`GI-Offres`,
`GI-Direction`…), même middleware.

Le pont MCP transmet l'identité Windows du poste au serveur. Au MVP, il
l'envoie en en-tête et le serveur lui fait confiance (réseau interne). Une
authentification Negotiate (Kerberos) du pont est prévue comme amélioration ;
elle fait l'objet d'une tâche distincte.

### 3.4 Fichiers

Les justificatifs, avis originaux et TDR restent sur le partage Windows. La
base stocke un chemin UNC relatif à une racine configurée
(`PARTAGE_REFERENCES=\\SERVEUR\REFERENCES`). L'application lit ces fichiers
pour compter les pages, vérifier l'existence, et plus tard assembler le
dossier ; elle n'écrit jamais dans les dossiers existants. Les dossiers
assemblés vont dans un dossier de sortie dédié.

### 3.5 Déploiement

Windows Server 2025 : PostgreSQL 18 en service, Uvicorn en service Windows
(NSSM, compte `svc-application`), IIS en frontal avec Application Request
Routing et HTTPS (certificat auto-signé approuvé sur les postes, faute
d'autorité interne ; ADR 0007 pour l'authentification). Accès distant par VPN.
Un seul projet Django, une seule chaîne de déploiement (`deploy\installer.ps1`,
Git) pour les deux modules : GI-SUIVI (`/suivi/`, application `suivi`) et le
module avis (`/avis/`, application `avis`, à venir). Voir `docs/exploitation.md`.

## 4. Modèle de données (vue d'ensemble)

Détail champ par champ dans `docs/schema-donnees.md`.

```
referentiel              references                experts
─────────────            ──────────────            ──────────────
Domaine ──┐              Mission ◄──────────────── Affectation ──► Expert
Categorie ─┼──────────►  │  code (immuable)                         │
TypeOuvrage ◄── M:N ─────┤  domaine, nature, categorie              Diplome
Localite ◄── M:N ────────┤  client, bailleur, pays
Client ◄─────────────────┤  dates, montant, duree
Bailleur ◄───────────────┤
                         ├── PieceJustificative (garde/signature/attestation)
                         └── Quantite (type, valeur, unite, source)

avis                                               projets (plus tard)
──────────────                                     ──────────────
Proposition (origine, extrait, statut) ─► Avis ─► Projet ─► (clôture) ─► Mission
                                           ├── Critere (mode, points, plafond, filtre)
                                           ├── Selection ─► Mission (par critère)
                                           └── BesoinExpert ─► Expert retenu
```

Les trois décisions structurantes du modèle :

1. **Le barème est une donnée.** Un `Critere` porte un mode de calcul (par
   mission, par ancienneté, forfait, manuel), des points, un plafond, un
   nombre minimal de missions et un **filtre** JSON décrit dans
   `schema-donnees.md`. Aucun avis ne demande de toucher au code.
2. **Les quantités sont une table, pas des colonnes.** Superficie en ha,
   longueur de piste en km, nombre de forages, capacité en m³ : chaque mission
   a de zéro à plusieurs quantités typées, avec leur origine (saisie, extraite
   du texte, estimée). Ajouter un type de quantité n'exige pas de migration.
3. **Le thésaurus des types d'ouvrages relie le vocabulaire des bailleurs au
   nôtre.** « Recharge de nappe » n'apparaît pas dans nos textes ; « seuil »,
   « micro-barrage » et « retenue » y sont. Les types d'ouvrages portent leurs
   synonymes et leur famille ; l'étiquetage des missions se fait une fois,
   avec l'aide de Claude Desktop, validé par un ingénieur.

## 5. Flux principaux

### 5.1 Répondre à un avis (MVP)

1. L'avis est créé : à la main, ou par validation d'une `Proposition`.
2. Le responsable saisit les critères. Pour chaque critère quantitatif, il
   traduit le texte du bailleur en filtre (catégories, types d'ouvrages,
   quantités minimales, période, zone, nature). Claude Desktop peut proposer
   cette traduction via l'outil `proposer_filtre_critere` ; l'humain valide.
3. `moteur.selection.selectionner(avis, missions)` rend, par critère, les
   missions éligibles classées, les points obtenus, le plafond atteint ou non,
   et pour chaque mission retenue l'état de ses pièces et les points perdus si
   une pièce manque.
4. `moteur.notation.noter(avis, selection)` rend la note simulée et la compare
   au seuil d'éligibilité.
5. L'écran et l'outil MCP `simuler_avis` affichent le même résultat.
6. La liste des pièces manquantes est triée par points en jeu décroissants.

### 5.2 Valider une proposition

Une `Proposition` (origine : veille, dépôt de TDR, Claude, saisie) porte les
champs extraits et le fichier source. L'écran de validation montre champ par
champ ce qui a été extrait ; l'humain corrige, puis accepte (création de
l'avis) ou rejette (motif). La proposition reste en base pour audit.

### 5.3 Assainir les références (phase de démarrage, outillée)

Import du CSV existant → chaque mission reçoit un statut `à vérifier`. Écran
de revue par mission : champs normalisés proposés (dates, durée, pays, lieu),
quantités détectées dans le texte, types d'ouvrages suggérés par mots-clés,
pièces trouvées sur le partage. L'ingénieur confirme ; la mission passe
`vérifiée`. Claude Desktop peut assister via `proposer_normalisation_mission`.

## 6. Serveur MCP

Contrat détaillé dans `docs/outils-mcp.md`. Principes :

- Les outils sont **étroits et nommés en français** : `rechercher_missions`,
  `detail_mission`, `simuler_avis`, `pieces_manquantes`, `rechercher_experts`,
  `proposer_filtre_critere`, `creer_proposition`.
- Les outils qui écrivent ne créent que des `Proposition` ou des brouillons ;
  jamais une mission vérifiée, jamais un avis validé.
- Chaque outil documente ses paramètres en français avec des exemples : c'est
  ce que Claude lit pour bien l'utiliser.
- Les réponses sont compactes (identifiants, codes, libellés courts) ; Claude
  appelle `detail_mission` s'il veut tout.

## 7. Alternatives écartées

| Alternative | Pourquoi écartée | Reconsidérer si |
|---|---|---|
| FastAPI + SQLAlchemy (MCP d'abord) | Pas d'admin ni de formulaires ; l'année 1 est une année de données | Claude Desktop > 80 % des usages, API JSON devient centrale |
| MCP seul, admin généré | Sacrifie la saisie humaine, dépendance de fait à Claude comme interface | Jamais, sauf changement radical d'usage |
| Connecteur MCP distant (HTTPS public) | Exigerait d'exposer le serveur sur internet | Le bureau décide d'héberger hors site |
| Serveur MCP complet sur chaque poste | N installations et N accès directs à la base | Jamais |
| Docker | Non supporté nativement sur Windows Server, licence Docker Desktop | Migration vers un hôte Linux |
| Chiffrement par colonne (SIGMA) | Complexité réelle, bénéfice couvert par le chiffrement disque et des sauvegardes | Exigence réglementaire explicite |
| Comptes et mots de passe maison (SIGMA) | AD via IIS fait mieux pour zéro code | Utilisateurs externes hors domaine |
| Audit chaîné par empreinte (SIGMA) | Défense contre l'administrateur ; disproportionné | Exigence d'un bailleur |
| Celery + Redis pour les tâches | Pénible sur Windows | Volume de tâches élevé |
| Extraction des TDR par IA dans le MVP | Dépendance et coût avant d'avoir des données propres | Dès que le module `extraction/` est planifié |

## 8. Risques et parades

| Risque | Parade |
|---|---|
| Montage FastMCP dans Django ASGI plus douloureux que prévu | Tâche 03 : prototype en semaine 1, critère d'arrêt explicite |
| Données sources trop hétérogènes pour l'import automatique | Import en deux temps : brut puis revue humaine outillée ; objectif 50 missions vérifiées par semaine |
| Retour des fonctionnalités de SIGMA par habitude | Règle 7 de CONTEXT.md ; tout ajout passe par un ADR |
| Développeur unique indisponible | Documentation à jour, CONTEXT.md, déploiement scripté, sauvegardes testées |
| Vocabulaire bailleur ≠ vocabulaire interne | Thésaurus des types d'ouvrages, outil MCP de traduction, validation humaine |
