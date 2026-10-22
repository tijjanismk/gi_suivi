# ADR 0010 — Pièces administratives du bureau : registre à échéances, contrôle à la date de dépôt

- **Statut** : proposé le 22/10/2026, à valider par le porteur
- **Date** : 2026-10-22
- **Complète** : `docs/phase0-collecte.md` (chantier 8), `docs/schema-donnees.md`,
  `docs/phase0-rangement.md` (un contenu = un exemplaire, décision du 21/10/2026)
- **Numéro** : 0008 (une référence = un contrat) est sur le poste de développement, 0009 est
  réservé au renommage `gic.giconseils.local` ; celui-ci prend 0010 pour éviter un conflit.

## Contexte

Chaque dossier d'offre joint les pièces administratives du bureau : RCCM, NIF, statuts, quitus
fiscal, attestation INPS, attestation OICM, agrément, liste des moyens, non-faillite selon
l'avis. Plusieurs ne valent que trois mois ; elles se renouvellent à date fixe.

Ce qu'on a constaté :

- le rapport SOMAPEP les montre toutes manquantes au coffre ; le dossier CENOU n'en a aucune ;
- l'analyse du 21/10 n'en reconnaît que 15 par leur nom sur les partages : les autres sont
  recopiées dans chaque réponse, sous des dossiers « 5.Pieces Admin », sans date de validité ;
- une pièce valide aujourd'hui peut être périmée le jour du dépôt : un quitus émis le 05/08
  expire le 05/11, un avis à déposer le 12/11 ne peut pas le joindre ;
- le porteur a décidé le 21/10 qu'il n'y aurait plus de fichier en double dans `D:\GIC`.

Les écrans ont été dessinés le 21/10 (maquettes « Pièces administratives — écrans », style
Unfold bleu de GI-SUIVI) : registre, fiche d'une pièce, dépôt d'une nouvelle version, contrôle
pour un avis, types de pièces.

Les règles du dépôt (`CONTEXT.md`) demandent un ADR pour toute nouvelle application et tout
nouveau modèle.

## Décision

### 1. Une application `administratif`, indépendante du module avis

Les pièces appartiennent au bureau, pas à un avis : elles servent avant même que le module avis
existe (savoir ce qui expire, préparer un dossier à la main). Nouvelle application Django
`administratif`, adresses sous `/administratif/`, menu Unfold groupe **Offres** (Pièces
administratives, Types de pièces ; Avis s'y ajoutera). Mêmes gabarits et composants que les
écrans GI-SUIVI (ADR 0005), même identité (ADR 0007).

### 2. Trois modèles

| Modèle | Champs clés | Règles |
|---|---|---|
| `TypePiece` | `code` unique (`QUITUS-FISCAL`, `RCCM`…), `libelle`, `organisme`, `regle_validite` (`apres_emission` / `fin_annee` / `date_du_document` / `revue_periodique` / `permanente`), `duree_mois` null, `rappel_jours` (30 par défaut), `exigee_par_defaut` bool, `dossier` (relatif à `PARTAGE_GIC`), `responsable` FK `identite.Utilisateur` null, `ordre`, `actif` | Réglé par la direction. Responsable vide = la direction. |
| `PieceAdministrative` | `type` FK, `chemin` (relatif à `PARTAGE_GIC`), `empreinte` (SHA-256, **unique**), `taille`, `nb_pages`, `numero`, `date_emission`, `valide_jusqu_au` null (= permanente), `deposee_par`, `deposee_le`, `retiree` bool, `motif_retrait` | Une ligne par version. Jamais supprimée (`PROTECT`, pas de suppression dans l'admin). Version en cours = la plus récente par `date_emission` parmi les non retirées. |
| `DemandeRenouvellement` | `type` FK, `demandee_le`, `aupres_de`, `par` FK, `relance_prevue_le` null, `note`, `close_le` null | Close automatiquement quand une version émise après la demande est enregistrée. |

Les liens avec les avis viennent avec le module avis, dans l'application `avis` : `PieceExigee`
(avis, type, ajoutée par l'avis ou héritée de `exigee_par_defaut`) et, à l'assemblage, la trace
de la version jointe et de son état à la date de dépôt. Une version remplacée garde ainsi les
dossiers qui l'ont jointe.

### 3. Les fichiers restent sur le partage ; l'application lit, ne touche à rien

Règle 4 de `CONTEXT.md` et § 3.4 de `design.md`. Une pièce se dépose en deux temps :

1. une personne pose le PDF scanné dans `\\AD-SERVEUR\GIC\ADMINISTRATIF\PIECES\<CODE>\` ;
2. l'écran « Déposer une nouvelle version » liste les fichiers de ce dossier pas encore
   enregistrés, calcule leur SHA-256 et propose les dates.

L'application ne renomme, ne déplace et ne supprime aucun fichier. Si un fichier enregistré a
été déplacé à la main (vers `_perimees\`, par exemple), elle le retrouve par son empreinte dans
le dossier du type et met à jour `chemin` en base. `GI-Application` a déjà la lecture sur
`ADMINISTRATIF` (`deploy/serveur/05-Partage-GIC.ps1`).

### 4. Pas de doublon

L'empreinte est unique sur toutes les versions. Un fichier de même contenu qu'une version déjà
enregistrée, ou qu'un autre fichier du dossier, est signalé « doublon » et ne s'enregistre pas.
Une erreur de type se corrige sur la version existante, pas par un nouveau dépôt. C'est la même
règle que le rangement de `D:\GIC` (21/10/2026).

### 5. Les échéances se calculent dans `moteur/`, en Python pur

`moteur/administratif/echeances.py`, sans Django (règle 1) :

- `date_de_fin(regle, date_emission, duree_mois, date_document)` : la date proposée. Trois mois
  après le 05/08 = le 05/11 ; après le 30/11, le 28 ou 29/02 (fin de mois quand le jour
  n'existe pas). `fin_annee` = 31/12 de l'année d'émission ; `date_du_document` = celle portée
  par le document (agrément) ; `permanente` = aucune.
- `etat(version, date_reference, rappel_jours)` : `valide`, `a_renouveler` (échéance dans
  `rappel_jours` ou moins), `expiree`, `manquante`, `permanente`.
- `controle(pieces_exigees, versions, date_limite)` : pour un avis, l'état de chaque pièce
  **à la date limite de dépôt**, avec la marge ou le retard en jours.

La date de fin est proposée, puis confirmée ou corrigée par la personne qui dépose : certains
documents portent leur propre date de validité.

### 6. Le contrôle se fait à la date de dépôt, jamais à la date du jour

Le registre montre l'état au jour ; le contrôle d'un avis, l'état au jour du dépôt. À
l'assemblage du dossier PDF, une pièce périmée ou manquante à cette date est remplacée par une
page en filigrane rouge « PIÈCE PÉRIMÉE » ou « PIÈCE MANQUANTE », comme les pièces de référence
manquantes.

### 7. Rappels sans nouvelle infrastructure

Au premier lot : la carte « Pièces à renouveler » sur l'accueil, le registre, et une commande
planifiée chaque matin `administratif_echeances` (journal ; code de sortie 1 s'il y a une pièce
expirée exigée par défaut), sur le modèle de `suivi_postes_muets`. Le courriel viendra plus
tard, avec son propre ADR (aucun serveur d'envoi n'est configuré).

### 8. Droits : les groupes existants, l'AD inchangé

`GI-Direction` dépose, retire, règle les types et note les demandes ; `GI-Direction-Lecture`
consulte ; décorateurs `groupe_requis` et `consultation_requise` d'`identite`. Aucun changement
dans l'AD (décision du 21/10/2026) : GI-Offres et GI-Administratif, vides aujourd'hui, pourront
recevoir le dépôt plus tard par un simple réglage. Chaque dépôt, retrait et demande est journalisé
comme les actions de la direction dans GI-SUIVI.

### 9. Types de départ

Une migration de données crée les types du chantier 8 : quitus fiscal (3 mois), extrait RCCM
(3 mois), attestation INPS (3 mois), attestation de non-faillite (3 mois, à confirmer),
attestation OICM (fin d'année), agrément technique (date de l'arrêté, rappel 60 jours), liste
des moyens matériels (revue tous les 12 mois), NIF, statuts, note sur les dénominations et NIF
successifs (permanents). Les durées marquées « à confirmer » sont vérifiées auprès des
organismes avant la mise en service ; elles se corrigent ensuite dans l'écran Types de pièces.

## Options écartées

| Option | Pourquoi non |
|---|---|
| Ranger les pièces dans l'application `avis` | Elles servent hors de tout avis, et avant que le module avis existe |
| Téléverser le PDF par le navigateur, stocké en base ou écrit par l'application | Contraire à la règle 4 ; l'application n'a que la lecture sur le partage |
| Contrôler les pièces à la date du jour | Laisse passer un quitus qui expire entre aujourd'hui et le dépôt |
| Calculer la fin de validité sans confirmation | Agrément, attestations : la date est sur le document |
| Historique par `django-simple-history` | Nouvelle dépendance ; une ligne par version suffit |
| Remplacer le fichier d'une version en place | On perdrait ce qui a été joint aux dossiers déjà déposés |

## Conséquences

- Une application (`administratif`), trois modèles, une migration de schéma
  `0001_pieces_administratives` et une de données `0002_types_initiaux` ; aucune nouvelle
  dépendance (`hashlib` de la bibliothèque standard).
- `moteur/administratif/` est testé sans base ; les vues ne calculent rien elles-mêmes.
- Un outil MCP en lecture seule, `pieces_administratives(date_reference)`, s'ajoutera à
  `docs/outils-mcp.md` avec le serveur MCP.
- Collecte initiale (chantier 8) : les 15 fichiers repérés par leur nom, `NON FAILLITE.pdf`
  (copié dans `REFERENCES\03_A_CLASSER\offres`) et les dossiers « 5.Pieces Admin » des avis
  sont triés à la main ; chaque pièce retenue est posée dans son dossier `PIECES\<CODE>\` puis
  enregistrée par l'écran de dépôt.
- Tâches AD01 à AD07 dans `docs/plan/taches.md`, rubrique « Ensuite ».
