# ADR 0011 — Justificatifs, ouvrages, livrables et quantités des références

- **Statut** : proposé le 22/10/2026 (développement sans le serveur, à la demande du porteur) ;
  la liste des types d'ouvrages et leurs synonymes sont à valider par l'arbitre métier
- **Date** : 2026-10-22
- **Complète** : ADR 0008, `docs/schema-donnees.md` (references, referentiel),
  `docs/phase0-collecte.md` (chantiers 3 et 4), `docs/phase0-rangement.md` § 4

## Contexte

Une référence ne compte devant une commission que si ses trois pièces sont au dossier et de la
bonne nature : page de garde du contrat, page de signature, attestation du client (AMI SOMAPEP :
une attestation « de services faits » peut être écartée). Les avis filtrent aussi par ce que la
mission a produit et par sa taille : « bas-fonds d'au moins 30 ha », « ouvrages de recharge de
la nappe ». Les chantiers 3 et 4 décrivent ce travail et ses registres (onglets `Pieces`,
`Quantites`, `Ouvrages`) ; l'ADR 0008 les renvoyait à plus tard.

## Décision

### 1. Les justificatifs restent sur le partage

Une pièce est un fichier de `\\AD-SERVEUR\GIC\REFERENCES\02_JUSTIFICATIFS\<code>\`, nommé selon
le rangement (`GARDE.pdf`, `SIGNATURE.pdf`, `ATTESTATION.pdf`, `CONTRAT_COMPLET.pdf`).
L'application lit le dossier, calcule l'empreinte SHA-256 et rattache le fichier à la référence ;
elle ne renomme, ne déplace et ne supprime rien (règle 4, comme l'ADR 0010). Un même contenu ne
se rattache qu'une fois (empreinte unique).

`references.PieceJustificative` : `mission`, `type` (garde, signature, attestation, contrat
complet, avenant, autre), `chemin`, `empreinte`, `taille`, `nb_pages`, et l'audit du chantier 3 :
`nature_exacte` (page de garde du contrat ou d'un avenant ; attestation de bonne exécution, de
bonne fin, de services faits ; PV de réception ; autre), `lisible` (oui, moyen, non),
`coherente` (oui, non, doute), `date_document`, `observations`, `auditee_par`, `auditee_le`.
Une seule garde, une seule signature, une seule attestation par référence ; avenants et autres
pièces en nombre libre. Une pièce rattachée par erreur se détache (le fichier reste).

**Une référence est complète** quand ses trois pièces sont rattachées, lisibles (oui ou moyen)
et cohérentes (oui). C'est le filtre « justificatifs complets » de la liste.

### 2. Les réclamations

`references.Reclamation` suit une pièce manquante ou faible auprès du client : `mission`,
`type`, `etat` (à demander, demandée, relancée, reçue, refusée), `le`, `contact_client`, `note`.
La plus récente par pièce est l'état en cours (chantier 3 : « toutes les pièces manquantes ont
un état de réclamation »).

### 3. Ouvrages, livrables, quantités

Dans `referentiel` : `TypeOuvrage` (liste fermée du chantier 4 : seuil d'épandage,
micro-barrage, digue filtrante, retenue collinaire, surcreusement de mare, bas-fond aménagé, PIV,
forage, AEP, piste, bâtiment, assainissement ; chacun avec sa famille et ses synonymes, pour que
« recharge de nappe » trouve les seuils et micro-barrages), `Livrable` (APS, APD, DAO, EIES,
NIES, suivi-contrôle) et `TypeQuantite` (superficie en ha, longueur en km, nombre de forages,
nombre de sites ou d'ouvrages, capacité en m³). Ajouter un type ne demande pas de migration.

Dans `references` : `Mission.types_ouvrage` et `Mission.livrables` (plusieurs par mission), et
`Quantite` (`mission`, `type`, `valeur` en Decimal, `source` : « contrat p. 4 », « rapport »,
« estimation »), une par type et par mission. Seules les quantités qui existent sont saisies.

### 4. Les écrans

Sur la fiche d'une référence (direction) : « Justificatifs » (fichiers du dossier du code, type
proposé d'après le nom, audit, détachement, réclamation des pièces manquantes) et « Ouvrages et
quantités ». La liste filtre par justificatifs complets ou non, et par type d'ouvrage.

## Options écartées

| Option | Pourquoi non |
|---|---|
| Téléverser les PDF dans l'application | Règle 4 ; l'application n'écrit pas sur le partage |
| Un booléen « vérifiée » par pièce | Le chantier 3 distingue lisibilité, cohérence et nature : une commission juge les trois |
| Quantités en colonnes de `Mission` | Chaque nouveau type demanderait une migration (design § 4) |
| Types d'ouvrages en texte libre | Les filtres d'avis demandent une liste fermée et des synonymes |

## Conséquences

- Migrations `referentiel` (types d'ouvrages, livrables, types de quantités, avec données de
  départ) et `references` (pièces, réclamations, quantités, ouvrages et livrables des missions).
- Les lectures du partage réutilisent les fonctions de `administratif.services` (chemin,
  empreinte, pages).
- Le découpage des PDF assemblés reste `scripts\exploitation\Decouper-PDF.ps1` sur le serveur.
