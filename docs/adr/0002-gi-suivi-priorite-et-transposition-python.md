# ADR 0002 — GI-SUIVI en priorité, transposé du dossier .NET vers le stack Python

- **Statut** : proposé, à valider par le développeur et la direction
- **Date** : 2026-10-06
- **Complète** : ADR 0001 (choix du stack)

## Contexte

Rien n'est déployé à ce jour : le dossier GI-SUIVI mentionne un prototype
PowerShell qui n'est pas en service au bureau ; le projet démarre de zéro.

Le dossier technique « GI-SUIVI v1.0 » (5 octobre 2026) décrit une application
de suivi d'activité : un agent sur chaque poste Windows mesure le temps actif
et le rattache à un dossier de projet par convention de dossiers ; une API et
un tableau de bord réservés au groupe AD `GI-Direction` restituent les heures
par employé et par dossier. Le dossier prévoit un stack ASP.NET Core 8 +
Blazor Server, un agent .NET livré en MSI, Kerberos de bout en bout,
PostgreSQL, un serveur membre dédié.

La direction demande que ce projet soit mis en place dès maintenant, avant le
module de réponse aux avis, et que l'ensemble reste en Python (ADR 0001 :
un seul langage pour un développeur seul).

Le même serveur, la même base PostgreSQL, le même IIS et les mêmes groupes AD
servent aux deux modules : GI-SUIVI est une application Django de plus dans le
dépôt `gic`, pas un second projet.

## Décision

1. **GI-SUIVI est le premier module livré.** Le module avis (références,
   barèmes, MCP) suit, sur le même socle.
2. **Le serveur est transposé en Django** : application `suivi/` (modèles,
   ingestion, classement, rapports, export Excel) dans le dépôt existant.
   Authentification Kerberos assurée par IIS (Authentification Windows), pas
   par le code.
3. **L'agent de poste est écrit en Python** (pywin32, SQLite, pyspnego pour
   Kerberos, pystray pour l'icône), supervisé par un service Windows Python,
   empaqueté avec PyInstaller et livré en MSI par WiX, déployé par GPO — avec
   un **point de contrôle** : si, au pilote, l'agent dépasse 1 % de processeur
   ou 80 Mo de mémoire, ou se montre instable, l'agent seul est réécrit en
   .NET (environ 1 500 lignes, isolées) sans toucher au serveur.
4. **Une seule racine de fichiers pour tout le bureau** : le partage `GIC`
   défini dans l'état des lieux du serveur. L'agent accepte plusieurs racines
   de classement avec leur profondeur (`GIC\MISSIONS_EN_COURS\<dossier>`,
   `GIC\AVIS\<année>\<dossier>`), au lieu de la racine unique `D:\DOSSIERS`
   du dossier initial.
5. **Le code de dossier suit la convention existante du bureau** : un dossier
   de projet porte le code GIC (`GIC-HYD-ETU-052_Client_objet`) ou, pour un
   avis non encore gagné, la référence courte de l'avis
   (`2026-SOMAPEP-001_recharge-nappe`). Le code est lu dans le nom du
   dossier ; la table `dossiers` de GI-SUIVI est la table `Projet` prévue dans
   `schema-donnees.md`, et se reliera plus tard aux missions et aux avis.

## Correspondance .NET → Python

| Composant du dossier | Prévu (.NET) | Retenu (Python) |
|---|---|---|
| Serveur API + tableau de bord | ASP.NET Core 8 + Blazor Server | Django 6 : vues HTML + HTMX pour les huit écrans, API JSON (vues Django ou Django REST Framework si le volume de points d'accès le justifie) |
| Authentification | Negotiate dans Kestrel | IIS Authentification Windows → `REMOTE_USER` → middleware `identite` ; NTLM refusé, Kerberos seul |
| Autorisation | Politique « Direction » = groupe `GI-Direction` | Même groupe ; décorateur `@groupe_requis("GI-Direction")` ; `/api/segments` et `/api/moi/aujourdhui` ouverts à tout utilisateur authentifié pour lui-même |
| Accès aux données | Entity Framework Core + Npgsql | ORM Django + migrations ; `psycopg` |
| Agrégations | SQL agrégé | Requêtes ORM avec `annotate`/`Sum`, ou vues SQL matérialisées si nécessaire |
| Export Excel | ClosedXML | `openpyxl`, totaux en formules |
| Tâches planifiées (purge, recalcul, postes muets) | Hosted services | `django.tasks` + un service Windows « travailleur », ou Tâches planifiées Windows appelant `manage.py` |
| Compte de service | gMSA | Compte de service du pool IIS (`svc-application`, ou gMSA si l'administrateur le préfère) ; SPN `HTTP/suivi.giconseils.local` sur ce compte |
| Connexion à la base | SSPI | SSPI possible avec PostgreSQL sur Windows (`sspi` dans `pg_hba.conf`) ; sinon mot de passe dans un fichier protégé par ACL, lu au démarrage |
| Agent de session | WinForms .NET | Python : `pywin32` (`GetForegroundWindow`, `GetLastInputInfo`, COM Office), `psutil`, SQLite standard, `requests` + `pyspnego` (Negotiate avec les identifiants de la session), `pystray` pour l'icône |
| Service de supervision | Worker Service .NET | Service Windows Python (`pywin32` `win32serviceutil`) qui lance l'agent dans chaque session via `CreateProcessAsUser`, ou plus simple : tâche planifiée « à l'ouverture de session » + redémarrage automatique, le service se bornant à surveiller |
| Paquet | MSI WiX | `PyInstaller --onedir` puis WiX pour le MSI ; version dans le registre `HKLM\SOFTWARE\GI-CONSEILS\Suivi` |
| Mises à jour | Nouveau MSI dans la GPO | Identique |
| Tests | xUnit | `pytest` ; le cœur (segmentation, inactivité, classement) en Python pur dans `moteur/suivi/`, testé sans Windows |

## Ce qui ne change pas

Le blueprint fonctionnel (règles 7.1 à 7.5, huit écrans, glossaire, décisions
de la section 11), le modèle de données (six tables), le contrat d'API
(section 6 de l'architecture), les exigences non fonctionnelles, les critères
de réussite du pilote et le plan en sept phases restent la référence. Seule
la technologie de réalisation change.

## Note du 06/10/2026 — version de Python

La série 3.12, d'abord retenue, n'a plus d'installateurs Windows (sécurité
seule depuis 3.12.10). Le projet est calé sur **Python 3.14**, série courante,
avec 3.13 en repli si une bibliothèque de l'agent manque de paquet compilé.
Serveur, postes et poste de construction utilisent la même version.

## Conséquences

Positives : un seul langage, un seul dépôt, une seule base, une seule
identité ; le module avis héritera des groupes, du partage `GIC`, de la table
des projets et de la chaîne de déploiement (IIS, service, GPO) construits
pour GI-SUIVI.

Négatives, assumées :

- L'agent Python est plus lourd qu'un agent .NET (30 à 60 Mo résidents contre
  15 à 25) et dépend d'un empaquetage PyInstaller plus fragile face aux
  antivirus. D'où le point de contrôle de la décision 3.
- La supervision multi-session (lancer l'agent dans chaque session ouverte
  depuis un service) est plus délicate en Python ; la variante « tâche
  planifiée à l'ouverture de session » est retenue par défaut, le service ne
  faisant que surveiller et relancer.
- Kerberos côté agent repose sur `pyspnego` ; à valider en première semaine
  sur un poste du domaine (test d'arrêt : si Negotiate échoue, l'agent
  s'authentifie par l'intermédiaire d'IIS en NTLM, acceptable en réseau
  local, et on note la dette).

## Préalables non négociables, hérités de l'état des lieux du serveur

Le dossier GI-SUIVI suppose un serveur membre dédié (8 à 16 Go), une
sauvegarde quotidienne hors serveur et une autorité de certification interne.
Le serveur réel est l'unique contrôleur de domaine, avec 8 Go, sans
sauvegarde, sans autorité de certification. Avant la phase 2 du plan GI-SUIVI
(API déployée) : sauvegarde en place et testée (A1), mises à jour appliquées
(A11), mémoire portée à 16 Go (A17), autorité de certification installée ou
certificat obtenu autrement (A7), groupes AD créés (A3). La phase 1 « Socle
serveur » du plan GI-SUIVI et les actions A1 à A8 de l'état des lieux sont la
même chose ; elles sont fusionnées dans `docs/plan/taches.md`.

## Point d'attention hors technique

Un agent qui observe le poste de chaque employé est un changement de relation
de travail. Le blueprint le sait (principes de transparence et de non-sanction,
note écrite, réunion avant le pilote). Ces engagements doivent être tenus
avant le premier déploiement, écrits, signés par la direction, et visibles
dans l'application (icône, « mon activité du jour »). Le développeur doit
refuser de livrer un agent sans icône visible : la discrétion technique ne
doit pas devenir de la dissimulation.
