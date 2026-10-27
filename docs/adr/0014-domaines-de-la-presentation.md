# ADR 0014 — Les six domaines de la présentation ; recodage des cinq références VRD

- **Statut** : accepté par le porteur le 27/10/2026
- **Date** : 2026-10-27
- **Décideur** : le porteur, sur proposition de l'assistant
- **Remplace** : —
- **Complète** : ADR 0008 (§ 3 domaines secondaires, § 6 codification initiale), ADR 0011 (types
  d'ouvrages), `docs/schema-donnees.md` (referentiel)

## Contexte

Les 268 codes du 23/10/2026 (ADR 0008 § 6) suivent les onglets du classeur d'août 2026 : sept
domaines dans le référentiel (HYD, AEP, ENV, BAT, RTE, AQA, VRD), dont six portent des
références (HYD 132, AEP 52, BAT 34, ENV 27, RTE 18, VRD 5) ; AQA n'a jamais eu de libellé ni de
référence.

Le 27/10/2026, le porteur a rappelé que la présentation du bureau (`ADMINISTRATIF\PRESENTATION`)
donne les domaines d'intervention, et qu'il faut coder avec eux : approvisionnement en eau et
assainissement, développement rural, infrastructures de transport, aménagements hydro-agricoles,
bâtiments civils et industriels, environnement. Il a fourni la liste complète de leurs
sous-domaines et demandé d'y ajouter ce qui manque (adductions d'eau sommaires, ponts,
barrages…).

Cinq séries de codes recouvrent déjà cinq de ces domaines. Restent les cinq références VRD
(onglet « Assainissement » du classeur : deux routes, un quai, un assainissement urbain, un
bâtiment), une série AQA vide, et le développement rural, qui n'a pas de série. Les codes ne sont
pas encore en production : l'ADR 0008 § 6 permet de les reconstruire avant. Mais 702 pièces sont
rangées sous `REFERENCES\02_JUSTIFICATIFS\<code>\` et rattachées sur `test` par leur chemin.

## Décision

### 1. Six domaines, aux libellés de la présentation

| Code | Domaine | Sous-domaines (catégories) |
|---|---|---|
| AEP | Approvisionnement en eau et assainissement | puits modernes et puits-citernes ; forages équipés de PMH ; forages équipés d'électropompe ; adductions d'eau sommaires (AES) ; systèmes solaires d'adduction d'eau ; adductions et réseaux de distribution d'eau potable ; stations de pompage et de traitement d'eau ; latrines ; traitement des déchets liquides et solides ; assainissement (routier, pluvial, caniveaux et collecteurs) |
| RUR | Développement rural (nouveau) | pistes rurales ; infrastructures hydro-agricoles ; infrastructures d'élevage ; points d'eau ; hydraulique villageoise et pastorale (SHVA, SHPA) ; énergie ; équipements socio-collectifs (magasins de stockage, foires, marchés) |
| RTE | Infrastructures de transport | routes en terre ; routes nationales et interurbaines ; voiries ; ponts ; ouvrages de franchissement (dalots, radiers) ; quais fluviaux |
| HYD | Aménagements hydro-agricoles | barrages et retenues d'eau ; bas-fonds et plaines ; périmètres irrigués villageois (PIV) ; périmètres maraîchers (PM) ; mares ; aménagement de bassins versants ; réseaux d'irrigation, de drainage, pistes et ouvrages de protection ; stations de pompage et équipements hydromécaniques |
| BAT | Bâtiments civils et industriels | écoles et salles de classe ; centres de santé ; bureaux et bâtiments administratifs ; magasins et bâtiments industriels |
| ENV | Environnement | études d'impact (EIES, NIES) ; audits et bilans environnementaux ; surveillance et suivi environnementaux |

Les codes à trois lettres existants sont gardés : le code HYD désigne désormais les aménagements
hydro-agricoles, AEP l'eau et l'assainissement, RTE les infrastructures de transport. Les
sous-domaines sont des `referentiel.Categorie` de leur domaine (la catégorie « Assainissement »,
créée sous VRD par l'import, passe sous AEP) ; les ouvrages nommés s'ajoutent aux types
d'ouvrages (ADR 0011) : AES, pont, dalot ou ouvrage de franchissement, SHVA, SHPA. Migration
`referentiel/0005_domaines_presentation`, qui supprime AQA, et VRD dès qu'il ne sert plus.

### 2. Le développement rural en domaine secondaire

Le développement rural recoupe les autres domaines (pistes, hydraulique villageoise,
aménagements hydro-agricoles, bâtiments ruraux). Aucune référence existante n'est recodée en
RUR : on lui ajoute RUR comme domaine secondaire (ADR 0008 § 3), et une recherche ou un critère
par domaine la trouve. La série RUR ne sert qu'aux références nouvelles dont c'est le domaine
principal. La liste des références à marquer RUR est proposée par l'assistant et validée par le
porteur.

### 3. Recodage des cinq références VRD, avant la production

Chacune prend le numéro suivant libre de la série de son domaine ; l'ordre chronologique des
séries vaut pour l'attribution du 23/10, pas pour ces ajouts.

| Ancien code | Nouveau code | Pourquoi |
|---|---|---|
| GIC-VRD-CTR-001 | GIC-RTE-CTR-013 | bretelle de Kogniba (route) |
| GIC-VRD-CTR-002 | GIC-RTE-CTR-014 | route Banankoro-Dioro et voiries |
| GIC-VRD-ETC-001 | GIC-RTE-ETC-001 | quai fluvial de Gao ; AEP en domaine secondaire (caniveaux, collecteurs) |
| GIC-VRD-ETC-002 | GIC-AEP-ETC-011 | assainissement urbain d'Ansongo |
| GIC-VRD-ETU-001 | GIC-BAT-ETU-012 | bureau de mairie et salles de classe |

La table se range avec les registres, `REFERENCES\00_REGISTRE\recodages\2026-10-27-vrd.csv`
(colonnes `Ancien`, `Nouveau`, `Domaine`, `Secondaires`) : les données ne vont pas dans Git. Deux
outils l'appliquent, `--simuler` / `-Simuler` d'abord :

- sur le partage, `scripts\exploitation\Recoder-Missions.ps1` : déplace les fichiers de
  `02_JUSTIFICATIFS\<ancien>\` vers `<nouveau>\` par `Deplacer-GIC.ps1` (journal
  `deplacements.csv`), corrige le code dans `missions.csv` et note chaque recodage dans
  `REFERENCES\00_REGISTRE\recodages.csv` ;
- dans la base, `manage.py references_recoder <table>` : change le code, le domaine principal et
  les domaines secondaires, les chemins des pièces rattachées, journalise, supprime VRD s'il ne
  sert plus. C'est le seul endroit où un code change ; la commande est refusée en production
  (`ENVIRONNEMENT=prod`).

`Construire-Missions.ps1` n'est plus relancé : il renumérote toutes les séries alors que les
codes rangent déjà les pièces. Une correction de code passe désormais par une table de recodage,
avant la production seulement.

## Justification

- Les domaines sont ceux que le bureau présente aux bailleurs : un critère « références en
  infrastructures de transport » se traduit directement en filtre.
- Garder cinq séries évite de renommer 263 codes et de déplacer les 702 pièces ; seules cinq
  références changent, dont quatre ont des pièces.
- Le domaine secondaire existe déjà (ADR 0008 § 3) : il absorbe le recoupement du développement
  rural sans faire deux fiches pour un contrat.

## Conséquences

Positives :

- Le référentiel, les filtres des avis et les écrans montrent les domaines de la présentation.
- Les sous-domaines deviennent des catégories qu'un critère peut demander.

Négatives, assumées :

- Le code HYD se lit « hydraulique » alors qu'il désigne les aménagements hydro-agricoles.
- Les nouveaux numéros des cinq références ne suivent pas l'ordre chronologique de leur série.
- Le recodage touche le partage, le registre et la base : les trois outils doivent tourner
  ensemble, sur l'accord du porteur.

## Contre-argument conservé

Recoder les 268 références avec six codes neufs (EAU, RUR, TRA, AHA, BAT, ENV) aurait rendu
chaque code lisible et aligné exactement sur la présentation, tant que rien n'est en production.

**Reconsidérer cette décision si** : la direction veut des codes lisibles avant la mise en
production ; un bailleur exige un classement par domaine que les séries actuelles ne suivent
pas ; le développement rural devient le domaine principal d'une part importante des références.
