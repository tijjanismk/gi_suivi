# ADR 0012 — Le vivier des experts et leurs affectations aux références

- **Statut** : proposé le 22/10/2026 (développement sans le serveur, à la demande du porteur)
- **Date** : 2026-10-22
- **Complète** : `docs/schema-donnees.md` (experts), `docs/phase0-collecte.md` (chantier 5),
  document « Règles des références, des experts et des CV » (21/10/2026, sections 6 à 8),
  ADR 0008 et 0011

## Contexte

Les TDR exigent des experts clés (l'AMI SOMAPEP en demandait sept), avec un nombre d'années
d'expérience et de missions comparables. Le chantier 5 a rangé 78 personnes dans
`EXPERTS\<NOM Prénom>` avec le registre `EXPERTS\_registre\experts.csv` (colonne Actif) ; il
reste le plus précieux : les **affectations**, qui feront les CV « à partir des affectations
réelles » et compteront les références de chaque expert.

## Décision

### 1. Une application `experts`

- `Expert` : nom, prénoms, statut (interne, externe, ancien), catégorie (ingénieur, technicien
  supérieur, technicien), fonction, spécialité, domaines (M:N `referentiel.Domaine`), début de
  carrière (année), nationalité, langues, disponible, dossier sur le partage
  (`EXPERTS\<NOM Prénom>`), accord écrit pour présenter son CV (externes), notes. Actif = non
  dans le registre : statut ancien et non disponible.
- `Diplome` : intitulé, établissement, pays, année, niveau (bac+2 à bac+8), justificatif.
- `Affectation` : expert, **mission** (une `references.Mission` existante : on ne peut citer
  qu'une mission du bureau), poste, du, au, temps plein ou partiel, hommes-jours, **preuve**
  (contrat, annexe, rapport ou attestation qui cite l'expert ; obligatoire).
- `ExperienceExterne` : employeur, poste, lieu, du, au, description, types d'ouvrages.

### 2. Les règles d'intégrité (règles des CV, section 8)

- Une affectation cite toujours une référence existante ; une référence absorbée renvoie au code
  gardé (l'écran propose le code gardé).
- Une affectation n'est enregistrée qu'avec sa preuve ; créer, modifier ou retirer une
  affectation est journalisé, et réservé à la direction.
- Deux affectations à temps plein qui se chevauchent sont signalées sur la fiche de l'expert
  (`moteur/experts/controles.py`), de même qu'une fin avant le début.
- Les années d'expérience se calculent depuis le début de carrière ; jamais saisies.

### 3. Les écrans

« Experts » (menu Offres) : le vivier filtré (statut, catégorie, spécialité, domaine,
disponibles) ; la fiche d'un expert (diplômes, affectations, expériences hors du bureau,
alertes) avec ses formulaires ; « Experts affectés » sur la fiche d'une référence. Import du
registre : `manage.py experts_importer experts.csv --simuler`.

### 4. Justificatifs et diplômes (27/10/2026)

La fiche d'un expert liste les fichiers de son dossier `EXPERTS\<NOM Prénom>` (sous-dossiers
compris), rangés d'après le nom en CV, diplôme, attestation ou autre, et les ouvre ; le partage
est lu, jamais écrit (règle 4, mêmes fonctions que l'ADR 0010). Un diplôme enregistré a pour
justificatif le chemin de son scan. Les diplômes s'importent par `manage.py experts_diplomes`
(`--simuler` d'abord) depuis un tableau établi à la main : les 61 scans des experts au vivier ont
été lus à l'œil (l'OCR seul lit mal spécialités et sessions). Retenu : un diplôme par document ;
une copie en double n'est pas reprise (la copie certifiée l'emporte) ; un brevet de technicien
(BT2) n'a pas de niveau « bac+ » ; une attestation de réussite sans diplôme le dit dans
l'intitulé. Les deux DUT de SIDIBE Nasser Hassane (même numéro, sessions 2016 et 2020) ne sont
pas importés : à vérifier sur l'original.

### 5. Hors de cet ADR

La production des CV au format d'un bailleur (format de fichier, bibliothèque, signature) fera
l'objet d'un ADR à part, après le choix des formats par la direction.

## Options écartées

| Option | Pourquoi non |
|---|---|
| Missions du CV en texte libre | On pourrait citer une mission que le bureau n'a pas faite (règles, section 8) |
| Années d'expérience saisies | Elles se contredisent d'un CV à l'autre ; le calcul les rend cohérentes |
| Affectation sans preuve, à confirmer plus tard | Les affectations non prouvées finiraient dans un CV déposé |

## Conséquences

- Application `experts`, migration `0001_experts` ; aucune nouvelle dépendance.
- `moteur/experts/` testé sans base (années d'expérience, chevauchements).
