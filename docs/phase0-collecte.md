# Phase 0 — Collecte et inventaire

Objectif : disposer, avant la première ligne de code, d'un patrimoine de
références **complet, dédoublonné, codé et rangé**, et d'un inventaire fiable
de tout ce qui existe ailleurs (missions en cours, experts, avis et offres
passés, pièces administratives). Rien de cela n'exige l'application ; tout
cela la rendra utile dès le premier jour.

## Principes

1. **Rassembler, coder, inventorier, réclamer — pas nettoyer.** La
   normalisation fine (dates, durées, orthographe des lieux et des clients)
   se fera dix fois plus vite dans les écrans de revue de l'application.
   En phase 0, on ne corrige un champ que s'il bloque l'identification de la
   mission.
2. **Une seule source de vérité par chose.** Le partage pour les fichiers,
   le registre (classeur Excel unique, décrit ci-dessous) pour l'inventaire.
   Pas de copies locales, pas de listes parallèles.
3. **Un contrat = une expérience = un code.** Une étude et le suivi-contrôle
   d'un même marché forment une seule référence (nature ETC). Deux fichiers
   identiques sous deux codes : on garde un code, on note l'autre comme
   « absorbé ». Un code attribué n'est jamais réutilisé.
4. **On note ce qu'on voit, pas ce qu'on suppose.** Une attestation « de
   services faits » n'est pas une attestation « de bonne exécution » ; un
   avenant n'est pas la page de garde du contrat. Le registre a des colonnes
   pour le dire.
5. **Durée bornée : six semaines.** La phase 0 ne vise pas la perfection ;
   ses critères de fin sont chiffrés (dernière section). Ce qui n'est pas fini
   à six semaines passe dans l'application avec le statut « à vérifier ».

## Gouvernance

| Rôle | Qui | Charge estimée |
|---|---|---|
| Pilote | vous | 2 jours / semaine |
| Arbitre métier (doublons, nature des missions, types d'ouvrages) | un ingénieur senior désigné par la direction | 2 h / semaine |
| Réclamations auprès des clients | assistant(e) de direction ou vous | selon le nombre |
| Point d'avancement | direction + pilote | 30 min / semaine, sur le registre |

Le registre est le seul support des points d'avancement. On n'y discute pas
des champs ; on y compte des lignes qui changent d'état.

## Le registre

Un classeur `REGISTRE_PHASE0.xlsx` à la racine du partage, un onglet par
chantier. Colonnes imposées par onglet dans chaque section ci-dessous. Les
états sont des listes fermées pour pouvoir compter. Le registre sera importé
tel quel dans l'application à la fin de la phase 0 : ses onglets
correspondent aux tables de `docs/schema-donnees.md`.

## Chantier 1 — Le partage

Créer l'arborescence cible et y déplacer l'existant. Rien n'est supprimé
avant la fin de la phase ; l'ancien rangement est déplacé dans `_ANCIEN\`.

```
\\SERVEUR\GIC\
├── REFERENCES\
│   ├── 00_REGISTRE\                 REGISTRE_PHASE0.xlsx, exports du tableur d'origine
│   ├── 01_SOURCES\                  les 20 fichiers Word d'origine, intacts, jamais modifiés
│   ├── 02_JUSTIFICATIFS\            un dossier par code : GIC-HYD-ETU-043\
│   │   └── GIC-HYD-ETU-043\
│   │       ├── GARDE.pdf
│   │       ├── SIGNATURE.pdf
│   │       ├── ATTESTATION.pdf
│   │       ├── CONTRAT_COMPLET.pdf  (facultatif : le contrat entier s'il existe)
│   │       └── _assemble_v1.pdf     (l'ancien PDF assemblé, conservé)
│   └── 03_A_CLASSER\                scans non identifiés, à arbitrer
├── MISSIONS_EN_COURS\
│   └── GIC-xxx-xxx-nnn\             code attribué dès la signature
│       ├── 01_CONTRAT\              contrat, OS, avenants
│       ├── 02_LIVRABLES\
│       └── 03_CLOTURE\              PV de réception, attestation demandée / reçue
├── AVIS\
│   └── AAAA\<reference-avis-courte>\
│       ├── AVIS.pdf, TDR.pdf
│       └── OFFRE\                   ce qui a été déposé, tel que déposé
├── EXPERTS\
│   └── NOM_Prenom\                  CV.docx, CV_signe.pdf, diplomes\, attestations\
├── ADMINISTRATIF\
│   └── AAAA\                        RCCM, NIF, statuts, agrément, quitus, INPS, OICM, moyens
└── VEILLE\
    └── sources.xlsx                 flux RSS, sites, boîtes mail surveillés
```

Règles : noms de dossiers sans accents ni espaces ; un code par dossier de
référence ; on ne renomme jamais un fichier source Word ; le partage est en
lecture seule pour tous sauf le pilote et l'assistante pendant la phase 0.

**Livrable** : arborescence en place, ancien rangement déplacé, droits
posés. **Critère** : plus aucun justificatif hors de `02_JUSTIFICATIFS`.

## Chantier 2 — La liste maîtresse des missions

Le point de départ est `missions_2026.csv` (238 lignes extraites des Word)
et le tableur d'origine (262 lignes annoncées). Il faut une seule liste.

Étapes :

1. Exporter le tableur d'origine en CSV ; le comparer au CSV des Word par
   montant puis par intitulé. Les 24 lignes présentes dans l'un et pas dans
   l'autre sont arbitrées une à une : mission réelle oubliée, doublon, ligne
   vide, mission d'un autre bureau.
2. **Chasse aux doublons**, en trois passes : (a) même montant et même
   client ; (b) intitulés très proches (le pilote trie la liste par client
   puis par année et lit) ; (c) pour chaque PDF assemblé, vérifier que le
   numéro de contrat ou de PO n'apparaît pas dans un autre PDF. Les quatre
   doublons repérés sur SOMAPEP (ETC-001/ETC-003, ETU-012/ETC-006,
   AQA-ETU-001/AQA-ETU-003, ETU-033/ETU-046) sont les premiers traités.
3. Pour chaque doublon : un code **conservé** (le plus ancien attribué ou
   celui dont le justificatif est le meilleur), les autres marqués
   « absorbé par GIC-… ». La nature devient ETC si l'un était étude et
   l'autre contrôle du même marché.
4. Attribuer un code à toute mission qui n'en a pas, selon la règle existante
   (domaine, nature, numéro séquentiel suivant dans la série).
5. Marquer la **nature** (ETU / CTR / ETC) et la **catégorie** de chaque
   mission : ce sont les deux champs dont dépendent tous les filtres, et
   l'arbitre métier les valide.

Onglet `Missions` : `code`, `statut_code` (nouveau / existant / absorbé),
`absorbe_par`, `intitule_court`, `client`, `annee`, `nature`, `categorie`,
`montant`, `source_word`, `numero_source`, `observations`.

**Livrable** : la liste maîtresse. **Critère** : 100 % des missions ont un
code unique et une nature validée ; zéro doublon connu non arbitré.

## Chantier 3 — Les justificatifs

Les 213 PDF assemblés sont découpés et audités ; les pièces manquantes sont
réclamées.

Étapes :

1. **Découper** chaque PDF assemblé en pièces séparées dans le dossier du
   code (chantier 1). Les 141 PDF de trois pages se découpent en lot
   (page 1 → GARDE, 2 → SIGNATURE, 3 → ATTESTATION) puis se vérifient ; les
   autres se découpent à la main. Script fourni dans `scripts/import/` quand
   le dépôt existera ; d'ici là, un découpage manuel est acceptable.
2. **Auditer** chaque pièce, en ouvrant le fichier, avec quatre questions :
   est-elle présente ? lisible (texte, cachets, signatures nets) ? de la
   bonne nature ? cohérente avec les deux autres (même contrat, même
   numéro, même montant) ?
3. **Qualifier** la nature exactement : page de garde du contrat / page de
   garde d'un avenant / autre ; attestation de bonne exécution / de bonne
   fin / de services faits / PV de réception / autre.
4. **Réclamer** les pièces manquantes ou faibles. Priorité par valeur
   d'usage : missions récentes (≥ 2015), catégories qui reviennent dans les
   avis (bas-fonds, micro-barrages, PIV, AEP, EIES), clients encore joignables.
   Une lettre type par client, listant toutes les missions concernées, signée
   par la direction. Suivi dans le registre : à demander → demandé (date) →
   relancé → reçu / refusé.

Onglet `Pieces` : `code`, `type` (garde / signature / attestation),
`presente`, `nature_exacte`, `lisible` (oui / moyen / non), `coherente`
(oui / non / doute), `reclamation` (sans objet / à demander / demandé le /
relancé le / reçue le / refusée), `contact_client`, `observations`.

**Livrable** : pièces découpées et auditées, lettres de réclamation parties.
**Critère** : 100 % des missions auditées ; au moins 80 % des missions des
catégories prioritaires avec trois pièces de la bonne nature ; toutes les
pièces manquantes ont un état de réclamation.

## Chantier 4 — Quantités et types d'ouvrages

C'est ce qui permettra de répondre à « bas-fonds d'au moins 30 ha » ou
« ouvrages de recharge de la nappe ». On commence par les 71 missions qui
mentionnent une retenue, une digue, un barrage ou un seuil, puis les
bas-fonds et PIV, puis le reste.

Pour chaque mission, l'ingénieur renseigne à partir du contrat ou du
rapport :

- les **quantités** : superficie aménagée (ha), longueur (km), nombre de
  forages, nombre de sites ou d'ouvrages, capacité (m³) — seulement celles
  qui existent, avec la page du document où elle est lue ;
- les **types d'ouvrages** parmi une liste fermée établie au départ avec
  l'arbitre métier (seuil d'épandage, micro-barrage, digue filtrante, retenue
  collinaire, surcreusement de mare, bas-fond aménagé, PIV, forage, AEP,
  piste, bâtiment, assainissement…) ; plusieurs par mission possible ;
- les **livrables** produits : APS, APD, DAO, EIES, NIES, suivi-contrôle.

Onglet `Quantites` : `code`, `type_quantite`, `valeur`, `unite`, `source`
(contrat p. X / rapport / estimation). Onglet `Ouvrages` : `code`,
`type_ouvrage`, `livrables`.

**Livrable** : les deux onglets remplis. **Critère** : 100 % des missions
des domaines HYD et AQA ont au moins un type d'ouvrage ; 100 % des missions
de catégories qui exigent une surface (bas-fonds, PIV, maraîchers) ont leur
superficie ou la mention « non trouvée ».

## Chantier 5 — Les experts

Le vivier : personnel actuel, anciens mobilisables, externes habituels.

Pour chaque personne : un dossier dans `EXPERTS\`, le CV à jour (Word),
le CV signé s'il existe, les diplômes scannés, et surtout la liste de ses
**affectations** : sur quelle mission (code), à quel poste, de quand à
quand. C'est le lien le plus difficile à reconstituer et le plus précieux :
il fera les CV « à partir des affectations réelles » et comptera les
références par expert comme l'exigent les TDR.

Méthode : partir des CV existants (ils listent des missions) et retrouver
le code de chaque mission dans la liste maîtresse ; compléter avec la
mémoire des intéressés pour les cinq dernières années.

Onglet `Experts` : `nom`, `prenoms`, `statut` (interne / externe / ancien),
`specialite`, `niveau_diplome`, `debut_carriere`, `cv_a_jour` (oui / non),
`diplomes_scannes` (oui / partiel / non). Onglet `Affectations` : `expert`,
`code_mission`, `poste`, `du`, `au`.

**Livrable** : dossiers experts et affectations. **Critère** : 100 % du
personnel technique actuel avec CV et affectations des 5 dernières années ;
les 7 profils clés les plus souvent demandés (chef de mission hydraulicien,
hydrogéologue, géotechnicien, topographe, socio-économiste,
environnementaliste, SIG) ont au moins un candidat identifié.

## Chantier 6 — Les missions en cours

Chaque mission en cours reçoit son code dès maintenant et son dossier dans
`MISSIONS_EN_COURS\`. On y range immédiatement le contrat signé (page de
garde et de signature scannées aujourd'hui, pas dans trois ans), l'ordre de
service, les avenants. On note la date de fin prévue et le nom de la personne
chez le client qui signera l'attestation.

Règle à instaurer dès cette phase : **l'attestation de bonne exécution se
demande au PV de réception**, avec un modèle fourni par le bureau au client
pour qu'elle porte les mentions utiles (objet exact, montant, délai, numéro
de contrat, « bonne exécution »).

Onglet `En_cours` : `code`, `intitule_court`, `client`, `contact_signataire`,
`debut`, `fin_prevue`, `garde_scannee`, `signature_scannee`,
`attestation_prevue_le`.

**Critère** : 100 % des missions en cours codées, avec contrat scanné.

## Chantier 7 — Les avis et offres passés

On range et on inventorie ; on ne saisit rien en base pour l'instant.

Pour chaque avis auquel le bureau a répondu (viser les cinq dernières années
d'abord) : un dossier `AVIS\AAAA\<ref>\` avec l'avis, les TDR et l'offre telle
que déposée. Dans le registre, une ligne avec le résultat quand on le connaît
— c'est la base de prix et de taux de succès de demain.

Onglet `Avis_passes` : `annee`, `reference_avis`, `type` (AMI / DP / AO),
`maitre_ouvrage`, `bailleur`, `objet_court`, `date_depot`, `resultat`
(gagné / perdu / sans suite / inconnu), `montant_propose`, `note_obtenue`,
`rang`, `attributaire`, `code_mission_si_gagne`, `chemin`.

**Critère** : cinq dernières années inventoriées ; chaque avis gagné relié à
son code de mission.

## Chantier 8 — Les pièces administratives du bureau

Le rapport SOMAPEP les montre toutes manquantes au coffre. Elles se
collectent une fois et se renouvellent à date fixe.

Validités corrigées le 22/10/2026 d'après les pièces réelles et les durées données par le
porteur (ADR 0010 § 9). Rappel : 15 jours avant l'expiration.

| Pièce | Validité | Où l'obtenir |
|---|---|---|
| Certificat de situation fiscale (« quitus fiscal ») | date portée sur le document (3 mois en pratique) | Centre des impôts |
| Attestation de déclaration mensuelle de TVA | 1 mois, à redemander après la déclaration du 5 | Direction des impôts |
| Patente | année civile | Centre des impôts |
| Attestation INPS | date limite portée sur le document (six semaines environ) | INPS |
| Certificat de non-faillite | 3 mois | Greffe du tribunal de grande instance |
| Attestation OMH | 1 mois | Office malien de l'habitat |
| Attestation de non-exclusion des marchés publics | 1 an | Autorité des marchés publics (à confirmer) |
| Attestation de non-endettement | 1 an | Trésor public |
| Extrait RCCM récent | 3 mois, quand l'avis le demande | Greffe du tribunal de commerce |
| Immatriculation au RCCM | permanente | Greffe |
| Attestation d'affiliation OICM | 1 an (tableau annuel de l'Ordre) | OICM |
| Agrément (enregistrement API-Mali) | permanent | API-Mali, guichet unique |
| NIF (carte d'identification fiscale) | permanent | DGI |
| Statuts à jour | permanent, jusqu'à modification | Notaire / archives |
| Liste des moyens matériels et logistiques | à revoir tous les 12 mois | interne |
| Note explicative sur les dénominations et NIF successifs du bureau | permanent | interne, à rédiger |

La dernière ligne répond à un problème vu sur les justificatifs : le bureau
y apparaît sous quatre noms, deux NIF et deux adresses (les pièces administratives
lues le 22/10 : six graphies du nom, cinq adresses, un seul NIF 025004950G). Une page signée par
la direction qui retrace ces changements évite une question gênante d'un
évaluateur.

Onglet `Administratif` : `piece`, `date_emission`, `valide_jusqu_au`,
`chemin`, `responsable_renouvellement`.

**Critère** : toutes les pièces présentes et valides, ou avec une date de
demande.

## Chantier 9 — Les sources de veille

Exporter de l'agent Claude actuel la liste de ce qu'il surveille : flux RSS,
sites, pays, mots-clés, boîtes mail. La ranger dans `VEILLE\sources.xlsx`.
Elle sera la première saisie du module `veille/`.

## Critères de fin de la phase 0

La phase est finie, et le développement commence, quand :

1. La liste maîtresse existe, sans doublon connu, 100 % codée et typée
   (chantier 2).
2. 100 % des justificatifs sont découpés et audités ; les réclamations sont
   parties et suivies (chantier 3).
3. Les types d'ouvrages sont renseignés pour tout HYD et AQA ; les
   superficies pour toutes les catégories qui en exigent (chantier 4).
4. Le personnel technique actuel a ses CV et affectations (chantier 5).
5. Les missions en cours sont codées et leurs contrats scannés (chantier 6).
6. Le partage est rangé et le registre est à jour (chantiers 1, 7, 8, 9).

Ou, quoi qu'il arrive, **à six semaines** : ce qui reste entre dans
l'application avec le statut « à vérifier », et l'application devient
l'outil pour finir.

## Ce qui se passe ensuite

Le registre s'importe dans la base par une commande `importer_registre` ;
chaque onglet alimente sa table ; les pièces découpées sont rattachées par
leur chemin. Le premier avis saisi dans l'application sera SOMAPEP 09/2026/001,
et son rapport d'analyse devra être au moins aussi bon que celui produit par
SIGMA le 6 octobre 2026 — avec, en plus, les doublons déjà écartés à la
source, la nature exacte de chaque attestation visible, et les pièces
administratives au coffre.
