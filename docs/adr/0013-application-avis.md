# ADR 0013 — Application `avis` : le barème en données, calculé par `moteur/avis/`

- **Statut** : accepté par le porteur le 27/10/2026
- **Date** : 2026-10-27
- **Décideur** : le porteur, sur proposition de l'assistant
- **Remplace** : —
- **Complète** : `docs/design.md` (§ 4 et 5), `docs/schema-donnees.md` (avis), `docs/outils-mcp.md`,
  ADR 0008 (une référence = un contrat), 0010 (pièces administratives), 0011 (justificatifs),
  0012 (experts) ; tâches AV01 à AV10 de `docs/plan/taches.md`
- **Numéro** : 0009 reste réservé au renommage `gic.giconseils.local` ; celui-ci prend 0013.

## Contexte

Le module avis est le second module de la plateforme (`CONTEXT.md`) : décider vite si le bureau
répond à un AMI, une DP ou un AO, avec quelles références, quels experts et quelle note
probable, puis constituer le dossier sans oublier une pièce. `docs/design.md` et
`docs/schema-donnees.md` le décrivent depuis le 06/10/2026, mais aucune table n'existe : un
modèle n'est créé que quand son module est planifié.

Le 27/10/2026, le porteur a mis la collecte en pause pour passer aux avis : dans `suivi-test`, il
les cherchait et n'en trouvait pas. Ce qui est prêt sur `test` :

- 268 références codées (ADR 0008), 702 pièces rattachées (217 références à trois pièces),
  toutes encore « à auditer » ;
- 75 experts au vivier, 73 diplômes, 30 experts marqués « à vérifier » (ADR 0012) ;
- 19 pièces administratives et l'écran « Contrôle avant un dépôt » (AD07, étape 1), qui attend
  le lien aux avis.

Le même jour, la DP UNICEF LRPS-MLI-2026-9206428 a été contrôlée à partir de la base de `test`
et des TDR (`C:\GIC\Claude outputs\UNICEF\Simulation-DP-UNICEF-2026-9206428.docx`). La base
a fourni les pièces, les références et les diplômes, mais le barème, le choix des références et
les postes ont été rapprochés à la main, dans un document Word. C'est ce travail que le module
doit faire.

`docs/rituels-ia.md` § 5 demande un ADR pour toute application Django et tout module de
`moteur/` nouveaux.

## Décision

### 1. Une application `avis`, sous `/avis/`, dans le menu Offres

Application Django `avis` (structure de `CONTEXT.md` : `models.py`, `services.py`, `vues/`,
`tests/`, puis `outils_mcp.py`), adresses `/avis/`, entrée « Avis » du groupe Offres du menu,
à côté des pièces administratives et des experts (ADR 0010 § 1). Mêmes gabarits (ADR 0005),
même identité (ADR 0007).

Droits : consultation par `consultation_requise` (direction et compte de lecture) ; saisie,
simulation et décision par `GI-Direction` ou `GI-Offres` (`GROUPE_OFFRES`, déjà dans les
réglages). `GI-Offres` est vide et l'AD ne change pas (décision du porteur) : la direction
saisit seule tant qu'il n'est pas peuplé.

Les fichiers de l'avis (avis, TDR, offre) restent sur le partage, sous `AVIS\<pays>\<AAAA-MM>\`
(chantier 7) ; la base garde le chemin relatif à `PARTAGE_GIC` et ne l'écrit jamais (règle 4).

### 2. Les modèles, par lots

Premier lot, migration `0001_avis`, champs de `docs/schema-donnees.md` :

- `Avis` : maître d'ouvrage `referentiel.Client`, bailleur `referentiel.Bailleur`. Un avis ne
  se supprime pas : il passe « sans suite ».
- `Critere` : le barème en données, avec les quatre modes (par mission, ancienneté, forfait,
  manuel) et le filtre JSON.
- `Selection` : une ligne par avis, critère et référence. Elle est recalculée à chaque
  simulation, sauf quand une personne a exclu ou forcé la référence (`retenue_par` et
  `motif` remplis) : ce choix est gardé.
- `PieceExigee` (avis, `administratif.TypePiece`, origine « par défaut » ou « demandée par
  l'avis ») : à la création d'un avis, les types exigés par défaut sont repris, et la personne
  coche le reste (ADR 0010 § 1).

Lots suivants : `BesoinExpert` (AV06) et `Proposition` (AV08). `DossierSoumis` (les offres
passées) reste « plus tard ».

### 3. Le calcul dans `moteur/avis/`

`filtres.py`, `selection.py` et `notation.py`, puis `experts.py` avec AV06 : du Python pur sur
des dataclasses, rangé comme `moteur/administratif/`, `moteur/references/` et
`moteur/experts/`. Les noms `moteur.filtres`, `moteur.selection` et `moteur.notation` de
`docs/design.md` deviennent `moteur.avis.*`. L'écran et, plus tard, les outils MCP appellent
`avis/services.py`, qui appelle le moteur : une seule implémentation de la note.

- **Le filtre** d'un critère (format de `docs/schema-donnees.md`) n'est interprété que là. Deux
  clés sont ajoutées pour l'avis UNICEF :
  - `roles` (seul, chef de file, membre), pour « contrôleur principal » ;
  - `pieces_requises` : les pièces qui prouvent la référence pour ce critère. Par défaut, ce
    sont la garde, la signature et l'attestation (ADR 0011). L'UNICEF ne demande que le PV de
    réception ou l'attestation de bonne fin, lus dans `nature_exacte`.
- **Les mots-clés** sont comparés dans le moteur après normalisation (casse, accents, pluriels :
  `moteur/references/doublons.normaliser`), sur l'intitulé et l'intitulé court ; le
  descriptif et les services n'existent pas encore sur `Mission`. Pas de recherche plein
  texte PostgreSQL pour 268 références.
- **Une référence absorbée** (ADR 0008) n'est jamais retenue.
- **La preuve d'une référence retenue a trois états** :
  - prouvée : les pièces requises sont rattachées, auditées lisibles et cohérentes ;
  - à auditer : elles sont rattachées mais pas encore auditées ;
  - manquante.
- **Deux notes en découlent** : la note sûre (références prouvées seulement) et la note
  possible (prouvées et à auditer). Le verdict se lit au seuil :
  - éligible si la note sûre l'atteint ;
  - non éligible si la note possible ne l'atteint pas ;
  - incertain entre les deux.

  Les pièces manquantes et à auditer sont classées par points en jeu.

### 4. Le lien aux pièces administratives

La fiche d'un avis ouvre « Contrôle avant un dépôt » avec la date limite et les pièces exigées de
l'avis ; le calcul reste `moteur.administratif.echeances.controle`. C'est `avis` qui appelle
`administratif`, jamais l'inverse, et l'écran reste utilisable sans avis (ADR 0010 § 1).
L'assemblage du dossier en PDF filigrané, la fin d'AD07, demande une dépendance : ADR à part.

### 5. Premier avis d'essai : UNICEF, puis SOMAPEP

L'avis UNICEF LRPS-MLI-2026-9206428 (DP, dépôt le 28/10/2026 sur UNGM, offre déposée) est
saisi le premier sur `test`, pour trois raisons :

- le résultat attendu existe déjà : la simulation du 27/10 ;
- son critère de références (contrôleur principal, dix dernières années, 2 points par
  référence, plafond 25) se calcule avec ce qui est déjà en base : nature, domaine, rôle,
  année, intitulé, attestations ;
- il touche les trois parties du module : pièces, références et experts.

L'avis SOMAPEP 09/2026/001 vient ensuite (`docs/design.md` § 1, `docs/phase0-collecte.md`). Son
critère « ouvrages de recharge de nappe » passe par les types d'ouvrages des références, et le
chantier 4 est en pause. Il sera comparé au rapport SIGMA du 06/10/2026.

### 6. Hors de cet ADR

- Serveur `/mcp/` et pont du poste (identité du pont) : ADR à part avant AV09.
- Assemblage du dossier, CV au format des bailleurs (ADR 0012 § 5), veille (`veille/`),
  extraction des TDR (`extraction/`, règle 5 de `CONTEXT.md`), offres passées
  (`DossierSoumis`).

## Justification

- Le barème en données (`docs/design.md` § 4) : un nouvel avis ne demande aucun changement de
  code, seulement une saisie.
- Le moteur sans base se teste en millisecondes, sur les cas UNICEF et SOMAPEP, et l'écran comme
  Claude Desktop donneront la même note (`docs/design.md` § 3.2).
- Les deux notes : les 702 pièces de `test` sont à auditer. Les compter comme prouvées
  gonflerait la note, les ignorer la ferait tomber à zéro (UNICEF : 29 contrats avec
  attestation, aucune auditée). Le verdict « incertain » dit ce qu'il reste à auditer pour
  conclure.
- Les écrans avant le MCP : le porteur cherche les avis dans l'application, et la validation
  humaine (règle 3) se fait à l'écran. Le moteur étant commun, les outils MCP viendront à peu
  de frais.

## Conséquences

Positives :

- Les avis apparaissent dans `suivi-test` dès AV03, et la note dès AV04.
- Le contrôle des pièces au jour du dépôt se fait depuis l'avis : AD07 est fermé, sauf
  l'assemblage.
- Aucune nouvelle dépendance.

Négatives, assumées :

- Les notes dépendent de la collecte en pause : sans l'audit des pièces, beaucoup de verdicts
  resteront « incertains » ; sans le chantier 4, un critère par type d'ouvrage ne trouve rien.
- Tant que `GI-Offres` est vide, seule la direction saisit les avis.
- `docs/design.md` et `docs/schema-donnees.md` sont à mettre à jour avec AV01 et AV02 (noms du
  moteur, deux clés du filtre, règle de la `Selection`).

## Contre-argument conservé

Les outils MCP auraient pu venir d'abord, sans écran : la simulation UNICEF du 27/10 a été faite
par Claude à partir de la base de `test`, et l'ADR 0001 (condition 1) voulait un outil MCP
avant toute autre fonctionnalité. Avec `simuler_avis` seul, Claude rapprocherait le barème, et
le porteur lirait la réponse dans Claude Desktop.

**Reconsidérer cette décision si** :

- un barème ne s'exprime pas avec les quatre modes (points par tranche, critère éliminatoire) :
  nouveau mode, nouvel ADR ;
- les références dépassent quelques milliers, ou les mots-clés ratent trop de références :
  recherche plein texte PostgreSQL dans `services.py`, avant le moteur ;
- Claude Desktop devient l'usage principal (ADR 0001).
