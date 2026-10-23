# Journal du projet

Le récit des sessions, sorti de `CONTEXT.md` le 23/10/2026 pour que ce fichier reste court
(règles, conventions, vocabulaire, pièges durables). On n'y revient que pour retrouver le
pourquoi d'un choix passé. L'état des tâches est dans `docs/plan/taches.md`, la passation
dans `docs/plan/en-cours.md`, les décisions dans `docs/adr/`. On ajoute en bas, daté.

## Jusqu'au 22/10/2026 (texte repris tel quel de `CONTEXT.md`)

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
1 000 segments < 1 s) ; **A02 fait** : dossier conforme jamais vu créé « détecté » à la réception, segments rattachés. **A03 fait** : file de recalcul (`DemandeRecalcul`, signaux sur exceptions et racines, `valider_dossier`), commande `suivi_recalculer`, action « Valider » dans l'admin, exception à effet immédiat. **A04 fait** : `GET /api/moi/aujourdhui` (sa propre journée, rien d'autre), `GET /api/racines` (ce que l'agent lit), page `/moi` ouverte par l'icône de l'agent. **A05 fait** : rapports JSON pour la direction et la consultation (`/api/rapports/synthese`, `/api/rapports/dossiers`, `/api/employes/{id}/activite`, `/api/dossiers`, `/api/aclasser`, `/api/postes/etat`, période `debut`/`fin`), jeu de 64 segments dans `conftest.py`. **A06 fait** : actions direction (`POST /api/dossiers/{id}/valider`, `PUT /api/dossiers/{id}`, `POST /api/aclasser/{id}/rattacher` → exception + recalcul), journal d'accès sur chaque action et consultation ; `/api/segments` réservé à l'en-tête `User-Agent: GiSuivi-Agent/`. **A07 fait** : `suivi_purger` (rétention en mois, `--simuler`), `suivi_postes_muets` (rouge/orange, code de sortie 1 si rouge, `--remettre-demarrages` le lundi), `/api/sante` ; `deploy/taches.ps1` aligné. **Phase 2 (API) terminée.** **T02 fait** : vue d'ensemble `/suivi/` (quatre indicateurs, barres SVG par personne, tableau jour × employé coloré, arrivée/départ), sélecteur de période dans l'URL (T09 en cours), `suivi_jeu_demo` (deux semaines de données de démonstration déterministes). **T03 fait** : écran Dossiers `/suivi/dossiers/` (barres par dossier, tableau dossier × personne, hors dossier). **T04 fait** : écran Personnes `/suivi/personnes/` (état indicatif, heures, % prévu, dernière activité) et fiche `/suivi/personnes/{id}/` (journées cliquables, chronologie SVG du jour colorée par dossier, fichiers, applications). **T05 fait** : gestion des dossiers `/suivi/gestion-dossiers/` (racines en lecture, détectés à valider avec temps déjà enregistré, actifs modifiables, clore/rouvrir ; formulaires POST + redirection, consultation seule sans boutons). **T06 fait** : file « à classer » `/suivi/a-classer/` (groupes fichier × personne, rattachement en un clic par exception — chemin exact, dossier parent, mot-clé —, brouillons signalés, nom seul non rattachable) ; `services.rattacher` partagé avec l'API. **T07 fait** : état des postes `/suivi/postes/` (alertes rouge/orange, version, dernier envoi, heures ouvrées muettes, démarrages, dernière personne). **T08 fait** : export Excel `/suivi/export.xlsx` (six feuilles, totaux en formules, en-têtes figés, nom daté ; bouton sur chaque écran à période). **T09 et T01 faits** : filtre dossier sur la vue d'ensemble, les personnes, la fiche et l'export ; menu des écrans, mise en page, page de refus. **Phase 4 (tableau de bord) terminée.** Puis, sur retour du porteur (08/10) : écran **Journée** `/suivi/journee/` (accueil du site : chaque personne, un jour, arrivée/départ, actif, pauses, hors mesure, frise) et détail bloc par bloc `/suivi/journee/{id}/` ; menu : groupe Écrans en tête (demande du 08/10, après un premier essai Suivi en haut), puis Suivi, Classement, Administration (allégé le 21/10 : groupe Suivi fondu dans Administration, plus de pages admin Postes, Segments, Recalculs ; Tableau de bord, Dossiers admin et « Qui suis-je ? » hors menu mais joignables ; cartes de l'accueil admin vers les Écrans) ; nombres SVG avec `|unlocalize` (le format français mettait une virgule : barres invisibles) ; icônes de cartes en ligne (le filigrane Unfold paraissait coupé). 176 tests, couverture 98 %, plus le parcours de bout en bout `tests/e2e/test_parcours.py` (trois lots → écrans → rattachement → export cohérent). **Chaîne réelle vérifiée sur ce poste** : l'agent installé envoie au serveur de dev (`url_api` 127.0.0.1:8010, `.env` UTILISATEUR_DEV=GICONSEILS\USER) — 236 segments repris en un coup, 0 doublon (G03 fait, CONTROLE n° 5 en partie). Projets de documents du pilote dans `docs/pilote/` (note à l'équipe D01, relevé manuel D03), à valider par la direction. Vérifié aussi en direct contre le serveur de
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
**Environnement test déployé sur AD-SERVEUR le 09/10** par `deploy\serveur\Tout-en-un.ps1 -Directeur
ODICKO -MotDePasseGic gic` (une commande, se met à jour par Git, idempotente) : PostgreSQL 18 et
Python 3.14 installés à la main puis reconnus, IIS (sites par nom d'hôte, Negotiate seul, ARR,
certificat auto-signé `B4126E92…A9` jusqu'en 2031), service `GIC-Test` (NSSM), application `main`,
6 tâches planifiées, 5 racines (partages existants) ; `verifier.ps1` sain, santé locale 200.
Leçons de ce serveur (Windows Server 2025, DC) : plus de `wmic` ; les cmdlets WMI (`*-NetFirewallRule`,
module WebAdministration sur certaines sections) se figent → `netsh`, `appcmd` en fin de script,
lecteur `IIS:\` ; pas d'`appcmd` mêlé au module dans la même session ; sections d'authentification
écrites par `<location>` ; Python « pour un seul compte » refusé ; bascule par copie miroir ;
Uvicorn **sans** `--proxy-headers` et **un seul** processus de travail (les anciens survivaient et
servaient l'ancien code). **ADR 0007** : IIS n'authentifie plus nos sites (en mode noyau,
`LOGON_USER` est vide pour la réécriture ; en mode utilisateur, il refuse les tickets des postes) ;
l'application valide elle-même le ticket Kerberos (`identite/negotiate.py`, SSPI via pywin32,
`IDENTITE_SOURCE=negotiate`), IIS en anonyme transmet `Authorization`. Sonde : `/api/sante?identite=1`.
**10/10 : Kerberos de bout en bout validé à travers IIS (200)** après deux corrections : port libéré
avant chaque démarrage (`deploy/liberer-port.ps1` : l'interpréteur lancé par `venv\Scripts\python.exe`
survivait et gardait l'ancien code ; `/api/sante` donne le commit en service, `verifier.ps1` le
compare) et **`svc-application` en Kerberos AES** (tickets RC4 refusés par Server 2025).
**F01 tâches confiées (11/10, avancé à la demande du porteur)** : `Tache` (dossier, fichiers en
motifs, personne, échéance, état), `/suivi/taches/` pour la direction, « Mes tâches » dans `/moi`,
temps passé calculé dans `suivi/taches.py` (segments actifs de la personne depuis le jour de
création jusqu'à la clôture ; par motifs de fichiers sinon par dossier). Aucun changement serveur,
IIS ou agent : un `Tout-en-un` suffit (migration 0005).
**Noms des logiciels (11/10)** : les écrans affichent « Microsoft Word », « Google Chrome »,
« Claude »… au lieu de l'exécutable (`suivi/applications.py`) ; les petits programmes de l'interface
Windows (ShellExperienceHost, SearchHost…) sont regroupés ; l'API et la base gardent l'exécutable.
Ajout sans redéploiement : paramètre `noms_applications` dans l'administration.
**Fichiers des partages en « à classer » (11/10)** : chemins reçus par lettre de lecteur (`E:\…`)
ou par un autre nom du serveur. Agent **0.2.3** : traduit lui-même les lettres réseau en UNC
(`win32wnet.WNetGetConnection`, cache 5 min). Moteur : nom complet du serveur ramené au nom court,
préfixes réseau acceptés dans `correspondance_lecteurs` (ex. `"\\\\192.168.2.250": "\\\\AD-SERVEUR"`).
Les segments déjà reçus en `E:\…` se rattachent après coup en déclarant la lettre dans
`correspondance_lecteurs` puis `suivi_recalculer`.
**Installation des postes (11/10)** : à la main, `Installer-GI-Suivi.cmd` du kit (double-clic :
élévation, copie locale — l'administrateur ne voit pas les lecteurs réseau —, PowerShell en Bypass
pour ce seul lancement). Pour les autres postes, **GPO** « GI-Suivi - Agent » :
`deploy/gpo/creer-gpo-agent.ps1 -Kit <zip>`, script de démarrage `demarrage-gpo.cmd/.ps1` qui
n'installe que si l'exécutable, la configuration ou le certificat a changé ; ciblage par le groupe
d'ordinateurs `GI-Postes-Suivi` (`docs/exploitation/gpo-agent.md`).
Le 500.50 via IIS venait d'un doublon de `allowedServerVariables` (site + serveur) : désormais au
niveau serveur seulement, par `appcmd`. **Pilote lancé le 09/10 sur le poste de Dicko** : kit 0.2.2 +
`gic-serveur.cer` + zone Intranet local (`zone-intranet.ps1`, aussi dans `installer-poste.ps1`) →
navigateur sans boîte de connexion, agent vert, lots du tampon repris (G04 validé) ;
`relancer-agent.ps1` pour forcer un nouvel essai après une période d'échecs.
**21-22/10 (sur AD-SERVEUR)** : menu allégé (doublons des Écrans et pages techniques retirés) ;
`D:\GIC` créé par `05-Partage-GIC.ps1` (AD inchangé, groupes GI-Offres, GI-Ingenieurs,
GI-Administratif, GI-Terrain encore vides) puis rempli par `Rangement-GIC.ps1` **sans doublon** :
3 174 fichiers (20,1 Go) copiés, 2 613 exemplaires en trop notés dans
`REFERENCES\00_REGISTRE\doublons.csv`. **ADR 0010 décidé (22/10)** : pièces administratives à
échéances, contrôlées à la date de dépôt (application `administratif`, tâches AD01-AD07),
maquettes Unfold bleu publiées.
**Prochaine étape :** vérifier « État des postes » et « Journée » depuis le poste de Dicko ; test
de restauration (P01) ; CONTROLE n° 6 ; note D01 signée ; relevés D03 ; WiX ; P07 mémoire. Toujours
`scripts\dev\verifier.ps1` avant d'envoyer (docs/git.md). Penser à `manage.py migrate` sur la
base de dev après chaque nouvelle migration (la base de test, elle, est recréée). Après un
changement de gabarit ou de classes : `scripts\dev\construire_css.ps1` (classes préfixées
`gic:`, ADR 0005) puis redémarrer le serveur de dev (cache des gabarits, `--noreload`).
