# ADR 0008 — Une référence = un contrat signé ; un code, un domaine principal

- **Statut** : décidé par le porteur (règle « un contrat = une référence », 21/10/2026) ; les
  domaines secondaires (§ 3) sont proposés, à valider par la direction
- **Date** : 2026-10-22
- **Complète** : `docs/schema-donnees.md` (references), `docs/phase0-collecte.md` (chantier 2),
  document « Règles des références, des experts et des CV » (21/10/2026), règle 2 de `CONTEXT.md`

## Contexte

Le portefeuille compte 238 fiches extraites des Word et 262 lignes dans le tableur d'origine.
L'analyse de l'AMI SOMAPEP (06/10/2026) a montré qu'une commission ne compte une expérience
qu'une fois, et que le portefeuille contient des doublons : quatre fiches décrivaient un contrat
déjà retenu, et ENV-ETU-020 et HYD-ETU-032 portent le même intitulé que HYD-ETU-033 (Samé
Ouolof). Un contrat codé dans deux domaines donne deux fiches : c'est un doublon de référence,
qui peut faire écarter une offre. La note du 19/10 relève 31 missions à regrouper et 7 cas
douteux.

## Décision

### 1. Une référence = un contrat signé

`references.Mission` est un contrat signé ; une ligne par contrat, un code par contrat.

| Cas | Règle |
|---|---|
| Contrat qui couvre plusieurs domaines | Une référence ; domaine principal dans le code, les autres enregistrés à côté (§ 3) |
| Contrat qui mêle études et contrôle | Une référence, nature ETC |
| Avenant | Reste dans la référence du contrat d'origine |
| Contrat en groupement | Une référence, avec le rôle de GI-CONSEILS (seul, chef de file, membre) et sa part |
| Plusieurs lots attribués par des contrats séparés | Une référence par contrat signé |
| Contrat qui couvre plusieurs sites | Une référence ; les sites dans la fiche |
| Dossier qui regroupe plusieurs contrats | Une référence par contrat signé |

### 2. Le code : attribué une fois, jamais modifié

`GIC-<domaine>-<nature>-<numéro>` (règle 2 de `CONTEXT.md`). Le modèle refuse tout changement de
code une fois enregistré ; on corrige les champs `domaine` et `nature`, pas le code.

### 3. Domaine principal et domaines secondaires (proposé)

Le domaine principal est celui qui pèse le plus dans l'objet ou le montant du contrat ; en cas de
doute, la direction tranche. Les autres domaines du contrat sont enregistrés dans
`Mission.domaines_secondaires` ; une recherche par domaine trouve aussi les références où il est
secondaire. Jamais deux codes pour un contrat.

### 4. Doublons : détectés par le moteur, arbitrés par une personne

`moteur/references/doublons.py` propose des paires suspectes, selon les passes du chantier 2 :
même montant et même client ; intitulés très proches ; même numéro de contrat. Rien n'est
fusionné sans décision : l'écran « Doublons à arbitrer » (direction) présente chaque paire, avec
ses raisons, et enregistre la décision (`DecisionDoublon`) : même contrat, en gardant l'un des
deux codes, ou contrats différents (la paire ne revient plus).

Pour un même contrat, le code gardé est celui que la direction choisit (par défaut le plus ancien
attribué) ; l'autre fiche est « absorbée par » le code gardé (`Mission.absorbee_par`), jamais
supprimée. Si l'une était une étude et l'autre un contrôle du même marché, la nature du code
gardé devient ETC.

### 5. Import de la liste maîtresse

La liste maîtresse (chantier 2, onglet `Missions`) s'importe par `manage.py
references_importer <fichier.csv>` : colonnes `code`, `statut_code` (nouveau / existant /
absorbé), `absorbe_par`, `intitule_court`, `client`, `annee`, `nature`, `categorie`, `montant`,
`source_word`, `numero_source`, `observations`. L'import est idempotent par code, ne modifie
jamais un code existant et marque chaque mission « importée » (`statut_verification`) : la
vérification reste humaine (règle 3). `--simuler` affiche ce qui serait fait.

### 6. Codification initiale (décision du porteur, 23/10/2026)

Aucun code n'existait dans le classeur d'août 2026 (un onglet par domaine, sans code). Les codes
sont attribués une fois pour toutes par `scripts\exploitation\Construire-Missions.ps1` : une
série par domaine et nature, numérotée dans l'ordre chronologique de signature (le plus ancien a
le plus petit numéro ; date exacte, puis année seule, puis sans date, l'ordre du classeur
départageant). Les doublons gardent chacun leur code et s'arbitrent ensuite dans l'application
(§ 4). Résultat : `REFERENCES\00_REGISTRE\missions.csv`, 268 missions, importées sur test le
23/10 (`statut_code` nouveau). Le script ne sert plus qu'à reconstruire ce fichier si le classeur
est corrigé avant la mise en production : après, un code ne change plus.

## Options écartées

| Option | Pourquoi non |
|---|---|
| Un code par domaine pour un contrat multi-domaines | Deux références pour un contrat : doublon, offre exposée au rejet |
| Domaines secondaires dans le code (`GIC-HYD+AQA-…`) | Le code est immuable ; un domaine corrigé changerait le code |
| Fusion automatique des doublons détectés | Faux positifs (deux lots d'un même programme, deux contrats du même client) ; règle 3 |
| Supprimer la fiche absorbée | On perdrait la trace des anciennes offres qui la citaient |

## Conséquences

- Deux applications : `referentiel` (domaines, catégories, clients, bailleurs) et `references`
  (missions, décisions de doublon). Les quantités, types d'ouvrages, localités et justificatifs
  viennent avec les chantiers 3 et 4.
- Le chantier 2 se fait dans l'application : import, arbitrage des doublons, codes attribués.
