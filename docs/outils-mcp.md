# Contrat des outils MCP

Les outils sont ce que Claude Desktop voit de l'application. Leur nom, leur
description et leurs paramètres sont lus par le modèle : ils doivent être en
français, précis, avec des exemples. Un outil mal décrit est un outil mal
utilisé.

Principes :

- **Lecture libre, écriture bornée.** Les outils de lecture rendent des
  données ; les outils d'écriture ne créent que des `Proposition` ou des
  brouillons, jamais une mission vérifiée ni un avis validé.
- **Réponses compactes.** Identifiant, code, libellé court, chiffres clés.
  Claude appelle un outil de détail s'il veut tout.
- **Identité.** Chaque appel porte l'identité Windows transmise par le pont ;
  les écritures sont attribuées à cette personne.
- **Mêmes fonctions que l'écran.** Chaque outil appelle le `services.py` de son
  application, qui appelle `moteur/`. Aucun calcul dans `outils_mcp.py`.

## Outils du MVP

Écrits et testés le 27/10/2026 (AV09) comme fonctions de `avis/outils_mcp.py` ; leur montage sous `/mcp/` et le pont du poste attendent la décision de l'ADR 0016 (dépendance `mcp`). `enregistrer_brouillon_critere` crée un critère `brouillon`, qui ne compte pas dans la note avant qu'une personne l'enregistre à l'écran.

### `rechercher_missions`

Recherche des références du bureau par filtre. Paramètres : les clés du
filtre de critère (`docs/schema-donnees.md`), toutes optionnelles, plus
`texte` (recherche plein texte libre) et `limite` (défaut 20).

Rend une liste de `{code, intitule_court, client, annee, nature, categorie,
quantites, pieces_completes, localites}`, triée par pertinence puis année
décroissante, et le nombre total de correspondances.

Exemple d'appel attendu de Claude : « études de micro-barrages ou seuils
depuis 2010 avec les trois pièces » →
`{"natures": ["ETU","ETC"], "types_ouvrage": ["micro-barrage","seuil"],
"annee_min": 2010, "pieces_completes_requises": true}`.

### `detail_mission`

Paramètre : `code`. Rend tous les champs, les quantités, les pièces avec
leur chemin et leur état, les experts affectés, les types d'ouvrages.

### `lister_referentiel`

Paramètre : `table` (`domaines`, `categories`, `types_ouvrage`, `localites`,
`types_quantite`, `clients`, `bailleurs`), `filtre_texte` optionnel. Permet à
Claude d'apprendre le vocabulaire de la base avant de proposer un filtre.

### `simuler_avis`

Paramètre : `avis_id`. Lance `moteur.selection` et `moteur.notation` sur
l'avis et ses critères. Rend par critère : points obtenus, plafond, missions
retenues (code, points, pièces complètes), alertes (`nb_min_missions` non
atteint) ; puis la note totale, le seuil, le verdict (éligible / non
éligible / incertain) et les trois leviers qui rapportent le plus de points.

### `pieces_manquantes`

Paramètres : `avis_id` (ou `codes_missions`). Rend la liste des pièces
absentes ou non vérifiées, classée par points en jeu décroissants, avec la
mission, le type de pièce et où elle devrait se trouver.

### `rechercher_experts`

Paramètres : `poste`, `domaines`, `niveau_min`, `annees_experience_min`,
`nb_references_min`, `filtre_references` (même format que le filtre de
critère, appliqué aux affectations de l'expert), `disponibles_seulement`.
Rend `{expert_id, nom, specialite, annees_experience, niveau, nb_references_
correspondantes, statut}`.

### `proposer_filtre_critere`

Paramètres : `texte_critere` (le texte du bailleur, tel quel), `avis_id`
optionnel. **Ne calcule rien** : rend le vocabulaire de la base susceptible
de correspondre (catégories, types d'ouvrages avec leurs familles et
synonymes, types de quantités) pour que Claude construise un filtre et
l'explique à l'humain. L'humain valide à l'écran. Cet outil est la réponse au
problème « recharge de nappe » ≠ « micro-barrage ».

### `creer_proposition`

Paramètres : `origine` (toujours `claude` depuis le MCP), `champs` (objet :
reference, objet, type, maitre_ouvrage, bailleur, date_limite, pays,
localites, criteres pressentis), `source_url`, `fichier_chemin`. Crée une
`Proposition` à valider. Rend son identifiant et l'adresse de l'écran de
validation. **Ne crée jamais un `Avis`.**

### `enregistrer_brouillon_critere`

Paramètres : `avis_id`, `critere` (code, libellé, mode, points, plafond,
filtre). Enregistre le critère marqué `brouillon` ; l'écran le montre en
attente de confirmation. Permet à Claude de préparer un barème complet que
l'humain relit d'un coup.

## Outils prévus après le MVP

- `assembler_dossier(avis_id)` — produit le PDF paginé, signets, filigrane.
- `generer_cv(expert_id, avis_id)` — CV réordonné pour l'avis.
- `proposer_normalisation_mission(code)` — assistance à l'assainissement.
- `rechercher_offres_passees(...)` — bibliothèque des offres soumises.

## Ce que les outils ne font pas, délibérément

- Modifier ou supprimer une mission, une pièce, un expert.
- Changer le statut d'un avis (go / no_go / déposé).
- Lire un fichier du partage pour le renvoyer en entier à Claude : l'outil
  rend le chemin UNC, Claude Desktop ouvre le fichier avec ses propres
  moyens si l'utilisateur le lui demande.
