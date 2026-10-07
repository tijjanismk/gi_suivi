# ADR 0003 — Agent : identification générique du fichier ouvert

- **Statut** : proposé, à valider par le développeur
- **Date** : 2026-10-07
- **Complète** : ADR 0002 (agent Python), ticket G02

## Contexte

L'agent v0.1.0 reconnaît le fichier de la fenêtre active par deux moyens :
COM pour Word, Excel, PowerPoint et Project ; des règles sur le titre de
fenêtre pour les autres, limitées à une liste fermée d'extensions
(`fichiers.py`, `_EXT`). Au premier essai sur poste (07/10/2026) :

- Revit n'est pas reconnu du tout (`.rvt`, `.rfa` absents de la liste) ;
- AutoCAD n'affiche par défaut que `plan.dwg` dans son titre : le temps tombe
  en « à classer » faute de chemin, même quand le fichier est dans un dossier
  de projet ;
- le bureau utilise bien plus de logiciels que ceux qu'on peut énumérer
  (« ce n'est pas la liste exhaustive ») ; écrire une règle par logiciel ne
  suivra jamais.

## Décision

L'agent cherche le chemin du fichier par des moyens **qui ne dépendent pas du
logiciel**, dans cet ordre, et s'arrête au premier qui répond :

1. **COM Office** (inchangé) : chemin exact du document actif.
2. **Chemin complet dans le titre** (inchangé) : Acrobat, Bloc-notes, QGIS…
3. **Fichiers ouverts par le processus de la fenêtre** (nouveau) : la liste
   des fichiers que le processus garde ouverts (`psutil.Process.open_files`),
   complétée par sa ligne de commande (fichier passé au double-clic).
   **Seuls les chemins situés sous une racine sont retenus**, après
   correspondance des lecteurs (`H:` → `\\AD-SERVEUR\GIC`).
   S'il en reste plusieurs, on garde celui dont le nom figure dans le titre ;
   à défaut, s'il n'en reste qu'un, celui-là ; sinon aucun.
4. **Nom seul dans le titre** : la liste fermée d'extensions, complétée des
   formats du bureau (Revit, IFC, Navisworks, SketchUp, ArchiCAD,
   MicroStation, Google Earth, GeoPackage, ArcGIS, Visio, Access). Une
   extension quelconque n'est pas acceptée : « jean.dupont@gic.ml » dans un
   titre Outlook deviendrait un brouillon. Un nom sans chemin ne rattache
   d'ailleurs à aucun dossier ; c'est le moyen n° 3 qui fait le travail.

Les navigateurs restent exclus des fichiers ouverts et des titres de page,
**sauf le nom d'un PDF** (décision du 07/10/2026, voir plus bas).

### Décisions du porteur, 07/10/2026

- **PDF lus dans un navigateur : le nom seul.** Sur le poste d'essai comme
  sur un Windows 11 neuf, les PDF s'ouvrent dans Edge ou Chrome ; les exclure
  revenait à ne jamais rattacher la lecture des TDR. Quand le titre de la
  fenêtre commence par un nom en `.pdf` (« TDR_052.pdf - Google Chrome »),
  l'agent garde ce nom, et rien d'autre : ni l'adresse, ni le titre d'une
  page web, ni un nom qui contient « / » ou « : ». Un nom sans chemin est
  « à classer » (et non « brouillon », réservé aux documents jamais
  enregistrés, sans extension : Document1, Classeur2).
- **Un tampon par utilisateur.** Le tampon et le journal de l'agent passent
  de `%ProgramData%\GiSuivi` (commun au poste) à `%LOCALAPPDATA%\GiSuivi`.
  Sur un poste partagé, l'agent d'une personne envoyait aussi les segments
  non envoyés de la précédente, sous sa propre identité, et chacun pouvait
  lire le tampon des autres. `%ProgramData%\GiSuivi` ne garde que
  `config.json` et le journal du service.

### Coût

Mesure du 07/10/2026 sur le poste de développement : `open_files` prend
**350 à 1 000 ms** par processus, quel que soit le processus, parce que
psutil parcourt toutes les poignées du système. L'énumération ne peut donc
pas se faire dans la boucle de 5 s :

- elle tourne **en arrière-plan**, une à la fois, une seule fois par
  (processus, titre) ; l'observation suivante lit le résultat en cache ;
- le chemin arrive donc **une observation plus tard** ; le moteur fusionne ce
  premier intervalle avec la suite quand la fenêtre est la même (règle du
  brouillon élargie : « pas de chemin, puis un chemin, même fenêtre ») ;
- la vérification n° 7 de `agent/CONTROLE.md` (< 1 % de processeur, < 80 Mo)
  est refaite sur une heure avec cette version et comparée à la v0.1.0. Si
  elle échoue, piste suivante : interroger les poignées du seul processus
  (`NtQueryInformationProcess`, classe `ProcessHandleInformation`) au lieu de
  celles du système.

### Confidentialité

Le moyen n° 3 voit tous les fichiers ouverts par un logiciel, y compris des
fichiers personnels. La règle « seulement sous une racine » est appliquée
**dans l'agent, avant tout enregistrement** : un chemin hors racine n'entre
jamais dans le tampon par ce moyen. Hors racine, l'agent n'en sait pas plus
qu'avec la v0.1.0.

## Conséquences

Positives : Revit, AutoCAD sans chemin dans le titre, et la plupart des
logiciels métier (HEC-RAS, ArcGIS, Covadis, EPANET…) donnent le dossier de
projet sans règle dédiée ; les dossiers de projet tenus sur les PC sont
rattachés dès qu'ils sont déclarés comme racines.

Négatives, assumées :

- Un logiciel qui lit son fichier puis le referme (certaines visionneuses) ne
  sera trouvé que si le titre suffit.
- Un logiciel ouvert sur plusieurs fichiers de projet, sans nom dans le titre,
  reste « à classer » plutôt que d'être rattaché au hasard.
- L'énumération des fichiers ouverts coûte : elle est mesurée, et retirée si
  elle fait échouer la vérification n° 7.
