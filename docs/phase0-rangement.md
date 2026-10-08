# Phase 0 — Rangement du partage GIC

Établi sur l'inventaire complet du 06/10/2026 (5 596 documents, 6 partages).
Source de vérité : **ce qui est sur le serveur**. Le travail de codification
fait hors serveur (CSV des 238 missions, 213 PDF assemblés) sert de modèle de
nommage, pas de source de fichiers.

## 1. Constats qui dictent le rangement

| Constat | Chiffre | Conséquence |
|---|---|---|
| Copies exactes | 3 409 fichiers sur 5 596 (920 contenus, 13,5 Go) | Chaque réponse à un avis embarque sa copie des listes et des CV. On range **une** source et on arrête de copier |
| Deux listes de références | `ESPACE DE TRAVAIL\Références actualisées mai 2026` (122) et `OFFRES\Références version arrangée août 2026` (98) | Désigner la liste maîtresse (section 3) |
| Attestations et contrats dans les offres | 115 attestations dans `OFFRE-2026`, 62 pièces de contrat dispersées | Les justificatifs se reconstruisent en les extrayant des offres déposées |
| CV en cinq endroits | 590 fichiers, 396 copies | `ETUDES\Les experts de GI Conseil 2026` (157 CV) devient le vivier |
| Avis déjà structurés | `AMI-2026\<pays>\<mois AAAA>\<avis>\` | Cette structure est conservée telle quelle dans `AVIS` |
| Dossiers de projet | `ETUDES\*`, `SUIVI-CONTROLE\*` | Racines de classement de GI-SUIVI, renommées avec un code |

## 2. Correspondance ancien → nouveau

**Décision du porteur (08/10/2026) : on ne touche à rien de ce qui existe sur le
serveur.** Les anciens partages, leurs droits, leurs fichiers et les disques
restent tels quels, sans gel, sans déplacement, sans suppression — même si cela
duplique des données. Le rangement **ajoute** `D:\GIC` par copie, c'est tout ;
l'application d'avis (phase suivante) travaillera dans `D:\GIC` et laissera
elle aussi les anciens partages intacts.

| Source (D:\) | Destination (D:\GIC\) | Mode |
|---|---|---|
| `OFFRES\Références de GI-Conseils-Version arranger-Aout 2026\…` | `REFERENCES\01_SOURCES\2026-08_version-arrangee\` | copie |
| `ESPACE DE TRAVAIL\Références actulisés 2026-Mai 2026\` | `REFERENCES\01_SOURCES\2026-05_actualisees\` | copie |
| `ESPACE DE TRAVAIL\*.pdf, *.docx` (contrats isolés, attestation de services faits) | `REFERENCES\03_A_CLASSER\` | copie |
| `AMI\AMI-2026\<pays>\<mois>\<avis>\` | `AVIS\<pays>\<AAAA-MM>\<avis>\` | copie, structure conservée, mois converti (`Août 2026` → `2026-08`) |
| `AMI\TOUTES LES NOUVELLES AMI-2026\` | `AVIS\_a_trier\` | copie |
| `OFFRES\OFFRE-2026\<avis>\` | `AVIS\<pays>\<AAAA-MM>\<avis>\OFFRE\` quand l'avis correspondant existe, sinon `AVIS\_offres-sans-avis\<avis>\` | copie ; rapprochement à la main |
| `OFFRES\Rapport-Facture`, `OFFRES\ADRS Rapports Finaux` | `MISSIONS_EN_COURS\_a_rattacher\` | copie |
| `ETUDES\Les experts de GI COnseil 2026\` | `EXPERTS\` (un dossier par personne, à faire à la main depuis la copie) | copie dans `EXPERTS\_import\` |
| `OFFRES\CV-Diplôme`, `AMI\Diplôme-CV` | `EXPERTS\_import\` | copie, dédoublonnée par contenu |
| `ETUDES\Bargondaga`, `ETUDES\Dossier ORM revu 30-06-2026`, `ETUDES\Memoires techniques ORM`, `ETUDES\Etudes 2026`, `ETUDES\DAO+TDR+Vf corrigé` | `MISSIONS_EN_COURS\<code>_<nom>\` | copie, puis codification (section 4) |
| `SUIVI-CONTROLE\*` | `MISSIONS_EN_COURS\<code>_<nom>\` | copie, puis codification ; fusionner les deux dossiers « Sanankoro Djitoumou » |
| `FINANCES\les contrats signés` | `MISSIONS_EN_COURS\<code>\01_CONTRAT\` (rattachés à la main) | copie dans `MISSIONS_EN_COURS\_contrats-a-rattacher\` |
| `FINANCES\FACTURES` | reste dans `FINANCES` (hors périmètre GIC) | — |
| `ETUDES\Météo`, `ETUDES\Test dessinateur`, `AMI\...\Dossier CIETRA SARL` | `_ANCIEN\` | copie |
| `ALASSANE`, `DICKO`, `OUSMANE IBRAHIM` | hors périmètre : action A15 (disque externe remis à l'intéressé, puis `UTILISATEURS\<login>`) | — |
| `SoftConcepts` (C:) | hors périmètre : action A13 (droits) | — |

Le script `scripts\exploitation\Rangement-GIC.ps1` exécute les lignes
« copie » de ce tableau, en simulation d'abord (`-Simuler`), puis pour de
vrai, avec un journal par ligne.

## 3. Désigner la liste maîtresse des références

Les deux listes se comparent avant de choisir :

1. Compter les fiches par domaine dans chacune (le script l'affiche).
2. Pour trois missions connues (Sémé, Lattakaf, Kodougou), ouvrir la fiche
   dans les deux versions et noter laquelle est la plus complète et la plus
   récente.
3. Demander à la personne qui a produit la version d'août 2026 ce qu'elle a
   changé par rapport à mai.

Décision attendue : la version d'août 2026 est maîtresse (c'est la plus
récente et elle a servi aux dernières offres), la version de mai sert de
contrôle. La décision est notée dans `docs/adr/0003-decisions-suivi.md`,
section « Références ». Les fiches Word de la liste maîtresse sont ensuite
**codées** : chaque fiche reçoit son code GIC dans son nom
(`GIC-HYD-ETU-004_APD-micro-barrage-Seme.docx`), selon le CSV existant quand
la mission y figure, selon la série suivante sinon.

## 4. Reconstruire les justificatifs depuis le serveur

Pour chaque fiche de référence codée :

1. Chercher dans `1_fichiers.csv` (types `attestation`, `contrat / pieces`)
   les scans qui portent le nom du client, du lieu ou du projet. Les 115
   attestations d'`OFFRE-2026` sont le gisement principal.
2. Copier le scan dans `REFERENCES\02_JUSTIFICATIFS\<code>\` sous son nom
   normalisé : `GARDE.pdf`, `SIGNATURE.pdf`, `ATTESTATION.pdf`, ou le PDF
   complet du contrat en `CONTRAT_COMPLET.pdf` à découper.
3. Noter dans le registre (`Pieces`) ce qui est présent, de quelle nature,
   et ce qui manque.

Les fichiers Word intitulés « Pièce justificatif.docx » (18 copies) sont des
pages de présentation des pièces, pas les pièces elles-mêmes : ils vont en
`03_A_CLASSER` pour vérification, puis probablement en `_ANCIEN`.

## 5. Codifier les missions en cours

Les dossiers d'`ETUDES` et de `SUIVI-CONTROLE` deviennent
`MISSIONS_EN_COURS\<code>_<nom-court>\`. Le code suit la règle existante
(domaine, nature, numéro suivant dans la série). Proposition à valider par
l'arbitre métier :

| Dossier actuel | Code proposé | Nom court |
|---|---|---|
| `ETUDES\Bargondaga` | à déterminer (HYD ou AQA, ETU) | `Bargondaga` |
| `ETUDES\Dossier ORM revu 30-06-2026` + `Memoires techniques ORM` | un seul code (ETU) | `ORM` |
| `ETUDES\Etudes 2026` | à éclater : plusieurs missions ? | — |
| `SUIVI-CONTROLE\suivi travaux hydraulique PCRSS` | CTR | `PCRSS-hydraulique` |
| `SUIVI-CONTROLE\suivi des travaux PRCSS Niger` | CTR | `PCRSS-Niger` |
| `SUIVI-CONTROLE\suivi des travaux d'installation d'une usine` | CTR | `usine` |
| `SUIVI-CONTROLE\Suivi contrôle Sanankoro Djitoumou` (×2) | CTR, fusionnés | `Sanankoro-Djitoumou` |
| `SUIVI-CONTROLE\suivi-travaux action kkro` | CTR | `ACTION-Koulikoro` |

Ces codes sont aussi les premières racines de GI-SUIVI : l'agent les lira
dans le nom du dossier.

## 6. La règle nouvelle, à diffuser avec le rangement

Une réponse à un avis ne contient plus de copie des listes de références ni
du vivier de CV. Elle contient les **pièces sélectionnées pour cet avis**,
copiées depuis `REFERENCES\02_JUSTIFICATIFS` et `EXPERTS` au moment du dépôt.
Les listes et les CV ne se modifient qu'à un seul endroit. L'application
automatisera cette sélection ; d'ici là, c'est une discipline, et c'est elle
qui fera disparaître les doublons.

## 7. Ordre des opérations

1. `05-Partage-GIC.ps1` : le partage et ses droits existent (fait après P04).
2. `Rangement-GIC.ps1 -Simuler`, lecture du journal, corrections de la table.
3. `Rangement-GIC.ps1` : copie réelle (quelques Go, moins d'une heure).
4. ~~Anciens partages passés en lecture seule~~ — **abandonné** (décision du
   08/10) : les anciens partages restent exactement comme ils sont ;
   `-GelerAnciens` est désactivé dans le script.
5. Désignation de la liste maîtresse (section 3), codification des fiches
   **dans `D:\GIC` seulement**.
6. Reconstruction des justificatifs (section 4), registre tenu à jour.
7. ~~Après six semaines : anciens partages déplacés dans `_ANCIEN`, partages
   SMB supprimés~~ — **abandonné** : rien n'est déplacé ni supprimé.
