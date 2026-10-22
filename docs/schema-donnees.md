# Schéma de données

Conventions : noms en français sans accents, `Decimal` pour montants et
points, tout modèle métier hérite de `ModeleTrace` (`cree_le`, `modifie_le`,
`cree_par`, `modifie_par`). Les champs marqués *(plus tard)* sont prévus dans
le schéma mais non exploités au MVP.

## referentiel

| Table | Champs clés | Notes |
|---|---|---|
| `Domaine` | `code` (3 lettres, unique : HYD, AEP, ENV, BAT, RTE, AQA, VRD), `libelle`, `ordre` | Les 7 domaines du code de référence. |
| `Categorie` | `domaine` FK, `cle` (slug unique), `libelle`, `exige_quantite` (type de quantité attendu, nullable) | Ex. `bas-fonds`, `perimetres-irrigues`, `mares`, `aep`, `pistes`. |
| `TypeOuvrage` | `cle`, `libelle`, `famille` (texte : « mobilisation des eaux de surface », « recharge de nappe », « hydraulique villageoise »…), `synonymes` (tableau de textes) | Le thésaurus. Une mission porte plusieurs types. La recherche « recharge de nappe » trouve `micro-barrage` par sa famille. |
| `Localite` | `nom`, `niveau` (pays / region / cercle / commune / village), `parent` FK self, `cle`, `variantes` (tableau) | Hiérarchie du Mali ; les variantes absorbent les orthographes (`Koulikoro`, `KOULIKORO`, `Klkoro`). |
| `Client` | `nom` unique, `sigle`, `type` (etat / collectivite / projet / ong / prive / bailleur), `pays` | Maître d'ouvrage. |
| `Bailleur` | `nom` unique, `sigle` | BM, BAD, GIZ, UE… |
| `TypeQuantite` | `cle` (`superficie_ha`, `longueur_km`, `nb_forages`, `capacite_m3`, `nb_sites`…), `libelle`, `unite` | Rend les quantités extensibles sans migration. |

## references

| Table | Champs clés | Notes |
|---|---|---|
| `Mission` | `code` unique **immuable**, `domaine` FK, `nature` (ETU / CTR / ETC), `categorie` FK, `intitule`, `client` FK, `bailleur` FK null, `pays`, `localites` M:N, `types_ouvrage` M:N, `date_debut`, `date_fin`, `annee` (indexée, dérivée), `duree_mois` Decimal null, `duree_texte`, `montant` Decimal null, `devise`, `montant_texte`, `effectif`, `descriptif`, `services`, `statut_verification` (importee / a_verifier / verifiee), `source_import` (fichier Word d'origine, numero), `observations` | `annee` et `duree_mois` sont normalisés à l'import ; les versions texte d'origine sont conservées pour audit. **Premier lot (ADR 0008, 22/10/2026)** : en plus, `domaines_secondaires` M:N, `numero_contrat`, `role` (seul / chef de file / membre), `part_bureau`, `intervention` (réalisation / réhabilitation), `statut_code` (existant / nouveau), `absorbee_par` FK self (doublon : jamais supprimée), `source_word`, `numero_source` ; localités, types d'ouvrage, quantités et justificatifs viennent avec les chantiers 3 et 4. |
| `DecisionDoublon` | `mission_a`, `mission_b` (a < b), `meme_contrat`, `gardee` FK null, `raisons`, `note`, `par`, `le` | Une paire tranchée ne revient pas dans « Doublons à arbitrer » (ADR 0008, § 4). |
| `Quantite` | `mission` FK, `type` FK TypeQuantite, `valeur` Decimal, `source` (saisie / extraite / estimee), `extrait_de` (texte source, nullable) | Zéro à N par mission. Contrainte d'unicité (mission, type). |
| `PieceJustificative` | `mission` FK, `type` (garde / signature / attestation / autre), `chemin` (relatif à `PARTAGE_REFERENCES`), `nb_pages`, `date_document` null, `verifiee` bool, `verifiee_par` FK, `verifiee_le`, `observations` | Contrainte : une pièce par type et par mission. Propriété calculée `Mission.pieces_completes` = les trois types présents et vérifiés. |

## experts

| Table | Champs clés | Notes |
|---|---|---|
| `Expert` | `matricule` unique null, `nom`, `prenoms`, `civilite`, `fonction`, `specialite`, `domaines` M:N, `statut` (interne / externe / ancien), `nationalite`, `debut_carriere` (année), `langues`, `disponible` bool, `cv_signe_chemin`, `cv_signe_le`, `notes` | Le vivier : internes et externes mobilisables. `annees_experience` est calculée depuis `debut_carriere`. |
| `Diplome` | `expert` FK, `intitule`, `etablissement`, `pays`, `annee`, `niveau` (bac+2 … bac+8), `justificatif_chemin` | Les TDR exigent des niveaux (BAC+5, BAC+3). |
| `Affectation` | `expert` FK, `mission` FK, `poste`, `du`, `au`, `temps_hj` Decimal null | Les références *de l'expert* sont ses affectations. Génère les CV plus tard. |
| `ExperienceExterne` | `expert` FK, `employeur`, `poste`, `lieu`, `du`, `au`, `description`, `types_ouvrage` M:N | Expérience hors du bureau, pour les CV et le comptage des références par expert. |

## avis

| Table | Champs clés | Notes |
|---|---|---|
| `Proposition` | `origine` (veille / depot_tdr / claude / saisie), `statut` (a_valider / acceptee / rejetee), `source_url`, `fichier_chemin`, `champs_extraits` JSON, `champs_confirmes` JSON, `avis_cree` FK null, `decide_par`, `decide_le`, `motif_rejet` | La file de validation. Tout ce qui est automatique passe par ici. |
| `Avis` | `reference` (du bailleur, indexée), `objet`, `type` (AMI / DP / AO / autre), `statut` (recu / en_analyse / go / no_go / depose / gagne / perdu / sans_suite), `maitre_ouvrage` FK Client, `bailleur` FK, `pays`, `localites` M:N, `date_publication`, `date_limite`, `heure_limite`, `mode_depot`, `lieu_depot`, `courriel_depot`, `methode_selection` (QC / SFQC / SMC…), `seuil_eligibilite` Decimal, `note_maximale` Decimal, `note_simulee` Decimal, `simulee_le`, `fichier_avis_chemin`, `fichier_tdr_chemin`, `decision_par`, `decision_le`, `motif_decision`, `groupement` bool, `observations` | Le cycle de vie complet, de la réception au résultat. |
| `Critere` | `avis` FK, `code` (E.1, C.1…), `reference_avis` (numérotation du bailleur), `libelle`, `ordre`, `mode` (par_mission / anciennete / forfait / manuel), `points_par_mission`, `plafond`, `nb_min_missions`, `annees_seuil`, `points_socle`, `points_par_annee`, `filtre` JSON, `note_manuelle` Decimal null | Le barème en données. Voir format du filtre ci-dessous. |
| `Selection` | `avis` FK, `critere` FK, `mission` FK, `rang`, `retenue` bool, `retenue_par`, `points` Decimal, `pieces_completes` bool, `points_perdus_si_pieces_manquantes` Decimal, `motif` | Résultat matérialisé de `moteur.selection`, modifiable par l'humain (exclure une mission, forcer une autre). |
| `BesoinExpert` | `avis` FK, `poste`, `niveau_min`, `annees_experience_min`, `nb_references_min`, `filtre_references` JSON, `expert_retenu` FK null | Un par expert clé demandé dans les TDR. |
| `DossierSoumis` *(plus tard)* | `avis` FK, `date_depot`, `montant_propose`, `chemin_dossier`, `resultat`, `note_obtenue`, `rang`, `attributaire`, `prix_attributaire` | Les offres passées entrent ici, par import. |

### Format du champ `Critere.filtre`

Un objet JSON dont toutes les clés sont optionnelles ; les conditions se
cumulent (ET). Interprété exclusivement par `moteur.filtres`.

```json
{
  "natures": ["ETU", "ETC"],
  "domaines": ["HYD"],
  "categories": ["bas-fonds", "mares"],
  "types_ouvrage": ["micro-barrage", "seuil", "retenue-collinaire", "digue-filtrante"],
  "familles_ouvrage": ["mobilisation des eaux de surface"],
  "quantites_min": {"superficie_ha": 30},
  "annee_min": 2010,
  "annee_max": 2025,
  "pays": ["Mali", "Burkina Faso"],
  "localites": ["koulikoro", "bougouni"],
  "mots_cles": ["aps", "apd"],
  "pieces_completes_requises": true
}
```

Règles d'interprétation :

- `localites` accepte un cercle ou une région : les missions situées dans
  une localité **descendante** correspondent.
- `types_ouvrage` et `familles_ouvrage` passent par le thésaurus (synonymes
  inclus) ; `mots_cles` est une recherche plein texte PostgreSQL (dictionnaire
  français, sans accents) sur intitulé + descriptif + services.
- `pieces_completes_requises` vaut `true` par défaut quand le barème dit que
  seules les expériences justifiées comptent (cas SOMAPEP et PARCB). Si
  `false`, les missions incomplètes sont listées mais marquées.

### Modes de calcul d'un critère

| Mode | Calcul | Exemple |
|---|---|---|
| `par_mission` | `min(plafond, points_par_mission × nb_missions_retenues)` ; alerte si `nb < nb_min_missions` | SOMAPEP 2.1 : 20 pts × 2, plafond 40 |
| `anciennete` | `points_socle` si années ≥ `annees_seuil`, + `points_par_annee` au-delà, plafonné | SOMAPEP 1 : 30 si ≥ 10 ans, sinon 0 |
| `forfait` | `plafond` si le filtre retient au moins `nb_min_missions`, sinon 0 | « Avoir une agence au Mali » |
| `manuel` | `note_manuelle` saisie | SOMAPEP 3 : organisation, moyens |

## administratif

Pièces administratives du bureau (ADR 0010, décidé le 22/10/2026). Les fichiers restent sur `PARTAGE_GIC`,
sous `ADMINISTRATIF\PIECES\<CODE>\` ; l'application les lit.

| Table | Champs clés | Notes |
|---|---|---|
| `TypePiece` | `code` unique, `libelle`, `organisme`, `regle_validite` (apres_emission / fin_annee / date_du_document / revue_periodique / permanente), `duree_mois` null, `rappel_jours`, `exigee_par_defaut` bool, `dossier`, `responsable` FK Utilisateur null, `ordre`, `actif` | Réglé par la direction ; types de départ = chantier 8. |
| `PieceAdministrative` | `type` FK, `chemin`, `empreinte` (SHA-256) unique, `taille`, `nb_pages`, `numero`, `date_emission`, `valide_jusqu_au` null, `deposee_par`, `deposee_le`, `retiree` bool, `motif_retrait` | Une ligne par version, jamais supprimée. En cours = la plus récente non retirée. |
| `DemandeRenouvellement` | `type` FK, `demandee_le`, `aupres_de`, `par` FK, `relance_prevue_le` null, `note`, `close_le` null | Close par l'enregistrement d'une version émise après la demande. |

Avec le module avis : `avis.PieceExigee` (avis, type) et la trace de la version jointe à
l'assemblage, avec son état à la date limite de dépôt.

## identite

| Table | Champs clés | Notes |
|---|---|---|
| `Utilisateur` | `login_windows` unique, `nom_affiche`, `courriel`, `groupes` (tableau), `expert` FK null, `derniere_activite` | Créé/mis à jour par le middleware depuis `REMOTE_USER`. Pas de mot de passe. |

## Prévu, non créé au MVP

- `veille.Source`, `veille.Element` — collecte RSS / email / sites.
- `projets.Projet`, `projets.Jalon`, `projets.Livrable`, `projets.RapportTerrain` — suivi des missions gagnées ; un `Projet` naît d'un `Avis` gagné et produit une `Mission` à la clôture.
- `temps.Feuille`, `temps.Ligne` — imputation des heures par projet.
- `offres.OffreTechnique`, `offres.OffreFinanciere`, `offres.LigneHonoraires`, `offres.LigneFrais`.

Ces modèles sont nommés ici pour que les clés étrangères futures soient
anticipées (`Avis.projet`, `Mission.projet_origine`), mais aucune table n'est
créée avant que son module soit planifié.
