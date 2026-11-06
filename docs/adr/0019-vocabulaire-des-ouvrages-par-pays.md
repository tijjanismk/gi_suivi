# ADR 0019 — Vocabulaire des ouvrages par pays : une table de termes

- **Statut** : accepté par le porteur le 06/11/2026
- **Date** : 2026-11-06
- **Décideur** : le porteur, sur proposition de l'assistant
- **Remplace** : ADR 0011 § 3, pour les seuls synonymes des types d'ouvrages (le tableau
  `TypeOuvrage.synonymes`)
- **Complète** : ADR 0011 (types d'ouvrages), ADR 0013 § 3 (mots-clés normalisés),
  `docs/schema-donnees.md` (referentiel), règle 3 de `CONTEXT.md`

## Contexte

Le même ouvrage porte des noms différents selon le pays. La collecte du 06/11/2026 (321 avis lus
dans neuf pays, puis 1 325 AMI de la Banque mondiale comptés automatiquement ; livrables dans
`Claude outputs\vocabulaire-avis\`, hors Git) le mesure :

- l'AES malienne s'appelle mini-AEP ou PEA au Niger, AEPS ou PEA au Burkina, mini adduction
  d'eau potable au Cameroun ;
- le CSCOM s'appelle CSI au Niger et au Cameroun, CSPS au Burkina, poste de santé au Sénégal ;
- le SHPA s'appelle station de pompage pastorale (SPP) au Niger, forage pastoral en Mauritanie.

Le thésaurus actuel (ADR 0011 § 3) range ces termes dans `TypeOuvrage.synonymes`, un tableau
de textes sans pays, sans état et sans preuve. Trois faits de la collecte montrent que cela ne
suffit plus :

1. **Un terme n'est vrai que dans son pays, et parfois que dans un type de texte.** PPM veut
   dire « petit périmètre maraîcher » dans les références maliennes du bureau, mais « plan de
   passation des marchés » dans 47 AMI ; OF (ouvrage de franchissement, Burkina) attrape le
   « of » de 166 textes anglais ; USP (unité de soins périphérique, Togo) sort des liens web.
2. **Un même terme peut mener à deux types.** mini-AEP est aujourd'hui synonyme d'AEP ; trois
   pays l'emploient pour des ouvrages de la taille d'une AES.
3. **Des termes viendront de machines** : la liste de la collecte (63 synonymes proposés, à
   valider par le porteur), Claude par le MCP, et bientôt la lecture des avis eux-mêmes. La règle
   3 veut qu'ils attendent une validation humaine ; un tableau n'a pas de salle d'attente.

Contraintes : développeur unique, administration Unfold (ADR 0005), PostgreSQL 18, aucune IA
côté serveur (règle 5), `moteur/` sans Django (règle 1). Le pays est un texte libre dans
`Avis.pays` et `Mission.pays` (pas de table des pays). La comparaison tolérante (pluriel, tiret,
accents) est en cours dans une tâche à part et sera une fonction pure de `moteur/`.

## Options

| | A. Garder le tableau `synonymes` | B. Table `referentiel.Terme` | C. Tableau d'objets JSON dans `TypeOuvrage` |
|---|---|---|---|
| Apprentissage | nul | faible : un modèle, une migration, une page d'administration | faible |
| Exploitation | ajouts à la main dans l'administration | valider ou rejeter dans une liste filtrée | édition d'un JSON dans un champ |
| Maturité | en place | modèle Django ordinaire, comme `Proposition` | JSON non contraint, sans clé étrangère |
| Pour un agent de code | trivial | simple : requêtes et tests ordinaires | requêtes JSON plus fragiles |
| Plus gros risque | faux positifs dans les avis (PPM, OF), aucune trace de qui a validé, rien pour les termes proposés | migration des synonymes actuels ; un filtre `q_ouvrage` un peu plus long | un champ fourre-tout, contraire aux conventions de `CONTEXT.md` |

Écartées sans tableau : un thésaurus par pays (neuf copies des types d'ouvrages, impossibles à
tenir d'accord) ; la recherche plein texte PostgreSQL (ne règle ni le pays ni la validation,
reste possible plus tard pour la vitesse).

## Décision

Les termes qui mènent à un type d'ouvrage deviennent des lignes d'une table
`referentiel.Terme`, chacune avec son pays, sa portée, son état et sa preuve ; seuls les termes
validés servent aux filtres et à la lecture des avis. Aucune dépendance nouvelle : Django et
PostgreSQL sont déjà en place (ADR 0001), rien n'est à vérifier en version.

### 1. La table

| Champ | Sens |
|---|---|
| `type_ouvrage` | FK `TypeOuvrage`, protégée. Un terme peut exister pour deux types (mini-AEP). |
| `terme` | Tel qu'il s'écrit dans les avis : accents, tiret, casse du sigle (`AEPS`, `poste d'eau autonome`). |
| `cle` | Le terme normalisé par la fonction de `moteur/` ; unique avec `type_ouvrage` et `pays`. |
| `pays` | Texte, comme `Avis.pays` ; vide = tous les pays. |
| `portee` | `partout` (références du bureau et avis) ou `references` (intitulés des références du bureau seulement : PPM). |
| `statut` | `propose`, `valide`, `rejete`. |
| `origine` | `reprise` (ancien synonyme), `collecte`, `saisie`, `claude`, `avis` (rattaché depuis un avis). |
| `source_url`, `nb_avis` | La preuve : un avis qui l'emploie, et combien d'avis l'emploient quand il est proposé. |
| `propose_par`, `propose_le`, `decide_par` (FK utilisateur), `decide_le`, `motif` | Comme `avis.Proposition`. |

Le libellé et le sigle entre parenthèses du type restent reconnus comme aujourd'hui.

### 2. La comparaison

Une seule fonction pure de `moteur/` (la tâche en cours) normalise le texte et le terme :
pluriel en s ou x, tiret égal à espace, accents et apostrophes ignorés, liens web retirés.
**Un terme écrit tout en capitales (un sigle) ne se compare qu'en capitales** : `PEA` trouve
« 12 PEA », pas « pea » ; `OF` ne trouve plus « of ». Pour une référence, servent les termes
validés de portée quelconque, sans pays ou du pays de la mission ; pour un avis, les termes
validés de portée `partout`, sans pays ou du pays de l'avis.

### 3. Les usages

- `references.services.q_ouvrage` (filtre de la liste des références) et
  `avis.services.vocabulaire_pour` (servi aux outils MCP) lisent la table au lieu du tableau.
  Le filtre des critères (`moteur/avis/filtres.py`) compare aujourd'hui les types saisis sur la
  mission ; s'il doit un jour lire aussi l'intitulé, il passera par ces termes.
- Les outils MCP peuvent proposer un terme (`statut = propose`, `origine = claude`), jamais le
  valider.
- Les termes que le porteur marque « oui » dans `synonymes-a-valider.csv` entrent par une
  commande d'import (`origine = collecte`, `statut = valide`, `decide_par` = le porteur) : sa
  décision dans le fichier est la validation humaine.
- Plus tard, l'écran d'un avis montrera les types reconnus et les termes inconnus (sigles
  définis entre parenthèses), à rattacher d'un clic ; la veille par l'API de la Banque mondiale,
  qui touche au serveur (accès réseau, tâche planifiée), fera l'objet de son propre ADR.

### 4. La reprise

Migration `referentiel/0007_termes` : création de la table, puis chaque synonyme actuel devient
un terme `valide`, sans pays, de portée `partout`, d'origine `reprise`. Le tableau
`TypeOuvrage.synonymes` est retiré par une migration suivante, une fois que plus aucun code ne le
lit. Les nouveaux types que la collecte propose (centre de santé, école, magasin de stockage,
périmètre maraîcher…) s'ajoutent sans migration de schéma (ADR 0011 § 3).

## Justification

1. Règle 3 : un terme venu d'une machine attend dans la table, avec son origine et sa preuve,
   jusqu'à ce qu'une personne le valide ; la trace dit qui et quand.
2. Les faux positifs mesurés (PPM, OF, USP) ne se corrigent qu'avec le pays, la portée et la
   comparaison des sigles en capitales ; sans eux, la lecture automatique des avis serait fausse.
3. Règle 1 : la comparaison reste dans `moteur/`, la table n'apporte que des données.
4. « Un modèle = une table = une responsabilité ; pas de champ fourre-tout » écarte l'option C.
5. Périmètre tenu : un modèle ordinaire, sur le patron de `Proposition`, sans dépendance ni
   écran nouveau au départ (l'administration suffit).
6. Le vocabulaire grandit avec chaque avis traité, dans tous les pays du bureau, sans multiplier
   les types d'ouvrages.

## Conséquences

Positives :

- Les avis du Niger, du Burkina ou du Cameroun trouvent les références maliennes du bureau par
  leurs propres mots, et seulement dans le bon pays.
- Chaque terme dit d'où il vient, qui l'a validé et sur combien d'avis il s'appuie.
- La veille, la lecture des TDR et Claude disposent d'un seul endroit où proposer.

Négatives, assumées :

- Une table, deux migrations (création et reprise, puis retrait du tableau), une page
  d'administration, et deux fonctions à reprendre (`q_ouvrage`, `vocabulaire_pour`), avec les
  outils MCP qui affichent les synonymes.
- `q_ouvrage` devient une union de conditions par pays : plus longue à lire et à tester.
- Le pays est un texte libre : « Guinée » et « Guinee » seraient deux pays. Les valeurs de
  `pays` des termes devront reprendre exactement celles des avis et des missions (liste fermée
  dans le formulaire, ou normalisation à l'enregistrement).
- Le porteur a une file de plus à valider.

## Contre-argument conservé

Avec une soixantaine de synonymes, le tableau actuel suffit : on les ajoute à la main dans
l'administration, on écarte les sigles dangereux (PPM, OF) et on accepte quelques faux positifs.
Ce serait vrai si l'application ne devait lire que les intitulés des références du bureau. Elle
va lire des avis de neuf pays, par la veille et par les propositions, et c'est là que les sigles
courts se trompent (47 avis pour PPM, 166 pour OF) : sans pays ni portée, il faudrait soit les
refuser partout, soit les accepter partout.

## Conditions de reconsidération

- Après six mois, moins de dix termes ont un pays ou une portée `references` : la table n'apporte
  rien que le tableau ne faisait ; revenir à un tableau.
- La lecture automatique des avis (veille, propositions) est abandonnée : la portée et le pays
  perdent leur raison d'être.
- Les termes dépassent quelques milliers ou la comparaison devient lente sur les références :
  passer à la recherche plein texte PostgreSQL, sans changer la table.
- Une table des pays apparaît dans l'application : `pays` devient une clé étrangère.
