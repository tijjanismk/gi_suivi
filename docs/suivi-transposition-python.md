# GI-SUIVI — Transposition en Python

Référence : dossier technique GI-SUIVI v1.0 (blueprint, architecture, plan).
Ce document dit comment chaque élément se réalise dans le dépôt `gic`. Il ne
reprend pas les règles fonctionnelles, qui restent celles du blueprint.

## 1. Place dans le dépôt

```
gic/
├── moteur/
│   └── suivi/                 # Python pur, testé sans Windows ni base
│       ├── segmentation.py    # fusion des observations en segments, clôture, inactivité
│       ├── classement.py      # chemin → racine → dossier de projet → code ; file « à classer »
│       ├── indicateurs.py     # heures effectives, % prévu, arrivée/départ, amplitude, occupation
│       └── tests/
├── suivi/                     # application Django
│   ├── models.py              # Employe, Poste, Segment, Dossier, Exception, JournalAcces, Parametre
│   ├── api/                   # ingestion et points d'accès JSON
│   ├── vues/                  # les huit écrans
│   ├── export.py              # classeur Excel (openpyxl)
│   ├── taches.py              # purge, recalcul, postes muets
│   ├── admin.py               # paramètres, exceptions, dossiers
│   ├── migrations/
│   └── tests/
├── agent/                     # agent de poste, paquet séparé du serveur
│   ├── gisuivi_agent/
│   │   ├── observation.py     # fenêtre active, processus, titre, inactivité (pywin32)
│   │   ├── fichiers.py        # chemin exact via COM Office ; extraction depuis le titre sinon
│   │   ├── tampon.py          # SQLite local, lots, acquittement
│   │   ├── envoi.py           # HTTPS + Negotiate (pyspnego), identifiant de lot, reprise
│   │   ├── icone.py           # pystray : état, « mon activité du jour »
│   │   ├── config.py          # lecture du registre HKLM\SOFTWARE\GI-CONSEILS\Suivi
│   │   └── principal.py       # boucle 5 s, orchestration
│   ├── gisuivi_service/
│   │   └── service.py         # service Windows : surveille et relance l'agent de session
│   ├── construire.ps1         # PyInstaller → dist\ → WiX → GiSuivi-Agent-x.y.z.msi
│   ├── installeur.wxs         # définition WiX
│   └── tests/                 # tests de la logique hors Windows (fichiers.py sur des titres)
└── deploy/gpo/GI-Suivi-Agent.md   # création de la GPO, paramètres registre
```

`moteur/suivi/` est partagé par le serveur et l'agent : la segmentation
tourne dans l'agent, le classement et les indicateurs sur le serveur, les
trois sont testés au même endroit.

## 2. Modèle de données (Django)

Six tables du dossier, plus une table de paramètres.

| Modèle | Champs | Remarques |
|---|---|---|
| `Employe` | `sid_ad` (unique), `login`, `nom_affiche`, `actif`, `heures_prevues_semaine` (défaut 40), `utilisateur` FK identite null | Le SID est la clé stable ; le login change parfois. Créé à la première ingestion ou au premier accès. |
| `Poste` | `nom` (unique), `version_agent`, `dernier_envoi`, `demarrages_semaine`, `premier_vu` | Alimenté par chaque lot. |
| `Segment` | `employe` FK, `poste` FK, `dossier` FK null, `debut`, `fin`, `duree_s`, `etat` (ACTIF/INACTIF), `application`, `fichier`, `chemin`, `statut_classement` (dossier / a_classer / ignore / brouillon), `lot_id` (UUID), `cree_le` | Jamais modifié sauf `dossier` et `statut_classement` lors d'un recalcul. Index (employe, debut), (dossier, debut), (lot_id). |
| `Dossier` | `code`, `nom`, `client`, `responsable` FK Employe null, `statut` (detecte / actif / clos), `chemin_windows` (unique, normalisé en minuscules), `racine` FK, `valide`, `valide_par`, `valide_le`, `mission` FK references null, `avis` FK avis null | C'est la future table `Projet`. Les deux FK vers les autres modules sont nullables et absentes tant que ces modules n'existent pas (ajoutées par migration plus tard). |
| `Racine` | `chemin` (ex. `\\AD-SERVEUR\GIC\MISSIONS_EN_COURS`), `profondeur` (1), `motif_code` (regex, ex. `^(GIC-[A-Z]{3}-[A-Z]{3}-\d{3})`), `active` | Plusieurs racines au lieu d'une. La GPO pousse la même liste à l'agent pour qu'il puisse déjà étiqueter. |
| `Exception` | `motif` (chemin exact, préfixe ou mot-clé), `type`, `dossier` FK, `cree_par`, `cree_le` | Rattachements hors convention. |
| `JournalAcces` | `utilisateur`, `action`, `cible`, `horodatage`, `adresse_ip` | Qui a consulté ou modifié quoi. |
| `Parametre` | `cle`, `valeur` | Seuil d'inactivité, intervalle, rétention (24 mois), heures prévues par défaut. |

Normalisation des chemins : l'agent envoie le chemin tel qu'il le voit
(lettre de lecteur ou UNC). Le serveur le ramène à l'UNC canonique grâce à une
table de correspondance lettre → UNC poussée par GPO (`H:` → `\\AD-SERVEUR\GIC`),
puis le compare aux racines en minuscules. Sans cette étape, le même fichier
ouvert par `H:\` et par `\\AD-SERVEUR\GIC\` ferait deux dossiers.

## 3. L'agent de poste en Python

### 3.1 Observation (toutes les 5 s)

- `win32gui.GetForegroundWindow()`, `win32process.GetWindowThreadProcessId`,
  `psutil.Process(pid).name()`, `win32gui.GetWindowText`.
- Inactivité : `win32api.GetLastInputInfo()` comparé à `GetTickCount()`.
- Verrouillage, veille, fermeture de session : abonnement aux événements
  `WTS_SESSION_LOCK` / `UNLOCK` et `WM_POWERBROADCAST` via une fenêtre
  cachée ; à défaut, détection par l'absence de fenêtre au premier plan.
- Fichier ouvert : pour Word, Excel, PowerPoint, Project, l'objet COM actif
  (`win32com.client.GetActiveObject("Word.Application")`) donne
  `ActiveDocument.FullName` ; pour AutoCAD, QGIS, Acrobat et le reste,
  analyse du titre de fenêtre par des règles par application (dans
  `fichiers.py`, testables hors Windows avec des titres enregistrés).
- Filtres : extensions techniques et préfixes `~$` ignorés ; pour les
  navigateurs, seul le nom du processus est conservé, jamais le titre.

### 3.2 Segmentation (dans `moteur/suivi/segmentation.py`)

Entrée : une suite d'observations `(instant, application, fichier, chemin,
inactif_depuis_s, etat_session)`. Sortie : des segments clos selon les règles
7.1 du blueprint. Fonction pure, testée sur des scénarios : pause de 4 min
(comptée), pause de 6 min (retirée depuis la dernière action), verrouillage,
changement de fenêtre, clôture à 5 min, brouillon `Document1` devenu
`Courrier.docx` (même processus, même fenêtre → fusion).

### 3.3 Tampon et envoi

- SQLite dans `%LOCALAPPDATA%\GiSuivi\tampon.db`, un par utilisateur (ADR
  0003, décisions du 07/10/2026) ; table `segments`, colonnes `lot_id`,
  `envoye`. Rotation : purge des segments acquittés de plus de 7
  jours ; capacité de plusieurs semaines hors réseau.
- Envoi toutes les 2 à 5 minutes (aléa pour lisser) : `POST
  https://suivi.giconseils.local/api/segments` avec `requests` et une
  authentification Negotiate `pyspnego` qui utilise les identifiants de la
  session — aucun mot de passe. Chaque lot porte un UUID ; le serveur ignore
  un lot déjà reçu.
- Reprise : échec réseau → les segments restent marqués non envoyés ; 401 →
  journalisé et nouvel essai (Kerberos expiré après verrouillage long) ; 5xx
  → attente exponentielle plafonnée à 30 min.

### 3.4 Icône et transparence

`pystray` : icône verte (envoi récent), orange (tampon en attente), grise
(hors réseau). Menu : « Mon activité du jour » (ouvre
`https://suivi.giconseils.local/moi` dans le navigateur), « Dernier envoi : … »,
« Version x.y.z ». Pas de « Quitter » : l'agent se ferme avec la session.

### 3.5 Supervision et déploiement

- Lancement et relance (ADR 0004, qui remplace la tâche planifiée prévue
  ici) : service Windows `GiSuivi` (pywin32, même exécutable lancé avec
  `--service`). Toutes les 15 s, il énumère les sessions actives
  (`WTSEnumerateSessions`) et, là où aucun `gisuivi-agent.exe` ne tourne,
  lance l'agent avec le jeton de l'utilisateur (`CreateProcessAsUser`). Il
  n'observe rien lui-même. Un mutex par session empêche deux agents.
- Empaquetage : `pyinstaller --onedir --noconsole` pour l'agent et pour le
  service ; WiX assemble les deux dossiers, crée la tâche planifiée, installe
  le service, écrit la version dans le registre. Signature du MSI avec un
  certificat de signature de code de l'autorité interne quand elle existera,
  pour éviter les alertes SmartScreen et antivirus.
- Paramètres par GPO (préférences de registre) : `UrlApi`, `IntervalleS`
  (5), `SeuilInactiviteS` (300), `Racines` (liste), `CorrespondanceLecteurs`.
- Empreinte visée : < 1 % processeur, < 80 Mo résidents (point de contrôle de
  l'ADR 0002). Mesure au pilote avec le Gestionnaire des tâches et
  `psutil` dans les journaux de l'agent.

## 4. Serveur Django

### 4.1 Authentification et autorisation

IIS, Authentification Windows, fournisseurs `Negotiate` seulement (NTLM
retiré de la liste) sur le site `suivi.giconseils.local`, SPN
`HTTP/suivi.giconseils.local` enregistré sur le compte du pool. Le middleware
`identite` lit `REMOTE_USER` et les groupes (`LOGON_USER` + requête LDAP mise
en cache 10 min, ou en-tête de groupes si le module IIS le fournit).

- `GI-Direction` : tous les écrans et toutes les routes `/api/rapports/*`,
  `/api/dossiers/*`, `/api/aclasser/*`, `/api/postes/*`, `/api/export/*`.
- Tout utilisateur authentifié : `POST /api/segments` (uniquement pour son
  propre SID : le serveur ignore tout segment dont l'employé ne correspond
  pas à l'identité Kerberos de la requête) et `GET /api/moi/aujourdhui`.

### 4.2 Ingestion et classement

`POST /api/segments` : corps JSON `{lot_id, poste, version_agent, segments:
[...]}`. Transaction : si `lot_id` connu → 200 sans rien faire ; sinon
insertion en masse (`bulk_create`), mise à jour de `Poste`, puis classement
de chaque segment par `moteur.suivi.classement` :

1. chemin normalisé en UNC → recherche de la racine la plus longue qui le
   préfixe ;
2. élément au niveau `profondeur` sous la racine → `chemin_windows` du
   dossier ; dossier inconnu → créé `detecte`, `valide=False` ;
3. hors racine → exceptions (chemin exact, préfixe, mot-clé) → sinon
   `a_classer` ;
4. sans fichier → `brouillon` si le processus est un éditeur, sinon segment
   d'application sans dossier.

Validation d'un dossier ou création d'une exception → tâche de recalcul des
segments concernés (`statut_classement` et `dossier` mis à jour ; `debut`,
`fin`, `fichier` jamais touchés).

### 4.3 Rapports

Agrégations ORM sur `Segment` filtré par période et `etat=ACTIF` :

- synthèse : `Sum(duree_s)` par employé et par jour, % des heures prévues,
  `Min(debut)` / `Max(fin)` par jour pour arrivée/départ, amplitude,
  occupation ;
- dossiers : `Sum(duree_s)` par dossier, puis par (dossier, employé) ;
- employé : chronologie des segments du jour colorée par dossier, liste des
  fichiers avec `Sum(duree_s)` ;
- à classer : segments `a_classer` groupés par (fichier, chemin, employé) ;
- postes : `Poste` avec alertes orange (`demarrages_semaine` > seuil) et rouge
  (`dernier_envoi` > 24 h ouvrées).

Si une vue dépasse 2 s sur un an de données (2 à 4 millions de segments),
une table `agregat_jour` (employé, dossier, jour, durée) alimentée par la
tâche nocturne remplace les agrégations à la volée. Pas avant d'avoir mesuré.

### 4.4 Écrans

Huit vues Django + HTMX, mobiles d'abord, reproduisant la maquette cliquable
du dossier : connexion (message de refus hors `GI-Direction`), vue
d'ensemble, dossiers, employés, fiche employé, gestion dossiers, à classer,
état des postes. Graphiques en SVG rendus côté serveur (barres horizontales,
chronologies) : pas de bibliothèque JavaScript, rien à télécharger, impression
propre.

### 4.5 Export Excel

`openpyxl` : six feuilles (synthèse, dossiers, journées, fichiers, à
classer, postes), totaux en formules `=SOMME(...)`, largeurs de colonnes
fixées, figement des en-têtes, nom de fichier
`GI-Suivi_<debut>_<fin>.xlsx`.

### 4.6 Tâches planifiées

Trois commandes `manage.py` appelées par des Tâches planifiées Windows (plus
simple qu'un service dédié au départ) : `suivi_purger` (nuit, segments plus
vieux que la rétention), `suivi_recalculer` (toutes les 10 min, file de
recalcul), `suivi_postes_muets` (chaque heure ouvrée, calcul des alertes).

## 5. Contrat d'API

Identique à la section 6 de l'architecture GI-SUIVI, chemins et accès
inchangés. Deux ajouts : `GET /api/racines` (l'agent lit la liste des racines
et des correspondances lettre → UNC au démarrage, en plus du registre) et
`GET /api/sante` (sans authentification, pour la supervision IIS).

## 6. Plan de réalisation (adapté du plan GI-SUIVI)

Rien n'est déployé aujourd'hui : ni serveur applicatif, ni agent, ni prototype. Le plan part de zéro. Les semaines sont indicatives, pour une personne à temps plein. Les tâches
sont reprises au format ticket dans `docs/plan/taches.md`.

| Phase | Contenu | Semaines | Critère de sortie |
|---|---|---|---|
| 0 — Décisions et serveur | Décisions de la section 11 du blueprint (racines, convention, membres de `GI-Direction`, heures prévues, rétention, note à l'équipe). Actions A1, A11, A12, A3, A17 de l'état des lieux. Création du partage `GIC` et des racines. | S1–S2 | Sauvegarde testée ; mémoire commandée ; groupes créés ; racines décidées |
| 1 — Socle | Dépôt, CI, `moteur/suivi` (segmentation, classement, indicateurs) avec tests ; modèles et migrations ; IIS + Négociation Kerberos vérifiée avec une page de test affichant `REMOTE_USER` et les groupes | S2–S3 | `whoami` Kerberos fonctionne depuis un poste du domaine sans mot de passe |
| 2 — API | Ingestion, idempotence des lots, classement, dossiers détectés, à classer, recalcul ; `GET /api/moi/aujourdhui` ; tests d'intégration avec des lots fictifs | S3–S5 | Un lot de test est reçu, classé et restitué |
| 3 — Agent | Observation, segmentation, COM Office, tampon, envoi Negotiate, icône ; PyInstaller ; MSI WiX ; GPO non liée ; mesure d'empreinte | S4–S8 | Sur un poste de test : collecte correcte, reprise après coupure, < 1 % CPU, < 80 Mo ; sinon décision .NET pour l'agent |
| 4 — Tableau de bord | Les huit écrans, export Excel, journal d'accès, tâches planifiées | S6–S9 | La direction valide chaque écran sur des données de test |
| 5 — Pilote | 2 ou 3 volontaires, GPO limitée ; chaque volontaire tient pendant une semaine un relevé manuel de ses heures et de ses dossiers, comparé aux heures mesurées ; corrections | S9–S11 | Critères de réussite du plan GI-SUIVI (section 5), le critère « fiabilité » étant mesuré contre le relevé manuel des volontaires (écart < 10 %) puisqu'aucun prototype n'est en service |
| 6 — Généralisation | GPO liée à tous les postes, surveillance une semaine | S11–S12 | Tous les postes envoient depuis 5 jours ouvrés |

Le module avis démarre à la phase 4, en parallèle, sur le même socle : il
réutilise IIS, `identite`, les groupes, le partage et la table `Dossier`.

## 7. Risques propres à la transposition

| Risque | Parade |
|---|---|
| `pyspnego` n'obtient pas de ticket dans certaines sessions (poste hors réseau au démarrage, ticket expiré) | Nouvel essai à chaque envoi ; repli NTLM accepté en réseau local et journalisé ; test en semaine 3 |
| Antivirus bloque l'exécutable PyInstaller | Signature de code ; exclusion Defender par GPO sur `%ProgramFiles%\GI-CONSEILS\Suivi` ; `--onedir` plutôt que `--onefile` (moins suspect) |
| Empreinte mémoire trop élevée | Pas de bibliothèque lourde dans l'agent (ni pandas, ni Qt) ; mesure continue ; point de contrôle ADR 0002 |
| COM Office indisponible (Office absent, document protégé) | Repli sur le titre de fenêtre ; segment conservé comme activité de l'application |
| Deux chemins pour un même fichier (lettre et UNC) | Correspondance lettre → UNC poussée par GPO ; normalisation serveur |
| Serveur unique saturé (contrôleur de domaine + base + IIS) | Préalables A17 et A1 ; surveillance mémoire ; migration vers un serveur membre dès que le budget le permet, la stack étant portable |
