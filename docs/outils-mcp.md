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
- **Identité.** Chaque appel porte le ticket Kerberos de la session Windows, transmis par le
  pont et validé par le serveur ; les écritures sont attribuées à cette personne.
- **Mêmes fonctions que l'écran.** Chaque outil appelle le `services.py` de son
  application, qui appelle `moteur/`. Aucun calcul dans `outils_mcp.py`.

## Outils du MVP

Écrits et testés le 27/10/2026 (AV09) comme fonctions de `avis/outils_mcp.py`, montés sous `/mcp/` le 06/11/2026 (ADR 0016, voir « Montage et pont » ci-dessous). `enregistrer_brouillon_critere` crée un critère `brouillon`, qui ne compte pas dans la note avant qu'une personne l'enregistre à l'écran.

## Montage et pont (ADR 0016)

- **Serveur.** `config/serveur_mcp.py` enregistre les fonctions de `OUTILS` telles quelles (nom,
  documentation, paramètres) dans le SDK `mcp` 2 (`MCPServer`, l'ancien `FastMCP`), servi en HTTP
  « streamable » sous `/mcp/` par `config/asgi.py`, à côté de Django, dans le même processus
  Uvicorn. Sans état et en réponses JSON : un message = une requête POST. Les fonctions sont
  synchrones (ORM) et appelées par `sync_to_async`. `rechercher_missions` expose les clés du
  filtre une à une. Les outils de lecture sont annoncés en lecture seule à Claude.
- **Identité.** Celle des écrans (ADR 0007) : ticket Kerberos de l'en-tête
  `Authorization: Negotiate`, validé par l'application ; sans ticket, 401. Une requête qui porte
  un en-tête `Origin` (page web) ou un nom d'hôte absent d'`ALLOWED_HOSTS` est refusée.
- **Droits.** Lecture : la consultation des écrans d'avis (`GI-Direction`, `GI-Offres`,
  `GI-Direction-Lecture`) ; écriture (`creer_proposition`, `enregistrer_brouillon_critere`,
  `proposer_terme`) : `GI-Direction` et `GI-Offres`. Un refus est rendu comme les autres erreurs,
  `{"erreur": …}`. Les écritures sont attribuées au login du ticket : le paramètre `par` n'est pas
  montré à Claude, et ignoré s'il l'envoie.
- **Pont du poste.** `agent/pont-mcp.py` (`pont-mcp.exe`, installé avec l'agent dans
  `C:\Program Files\GI-CONSEILS\GiSuivi\`) : Claude Desktop le lance en stdio ; il relaie chaque
  message vers `UrlApi` de l'agent + `/mcp/` (`https://app.giconseils.local/mcp/`, ADR 0009) en
  Negotiate (`requests-negotiate-sspi`), recopie les en-têtes du transport (version, méthode,
  nom de l'outil) et rend une erreur JSON-RPC lisible si le serveur est injoignable ou refuse
  l'identité. `pont-mcp.exe --claude` ajoute l'entrée `gi-conseils` à la configuration de Claude
  Desktop de la session (`agent/LISEZMOI-poste.md`).
- **Roues.** Le SDK et ses dépendances ont des roues binaires pour Python 3.14 sous Windows
  (vérifié le 06/11/2026 sur PyPI : `mcp` 2.3.0 et toute sa chaîne) ; le travail « Roues du serveur »
  de la CI les installe en `--only-binary=:all:` sur Windows à chaque envoi.

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

### `plan_dossier`

Paramètre : `avis_id` (un AMI). Lecture seule, ajouté le 07/11/2026 (AV14). Rend le dossier de
réponse page par page, au modèle des vrais dossiers du bureau (version électronique de SOMAPEP,
reprise pour les AMI PISEN du Niger) : `sommaire` (les rubriques imprimées, A à F, avec ce que
l'application sait de chacune), `compte` (pages par état) et `pages`, chacune
`{page, genre, rubrique, titre, etat, chemin?, motif?, reference?, paysage?, lignes?}`.

- `etat` : `redigee` (composée par l'application : couverture, sommaire, intercalaires, lettre,
  adresse, listes, pages de famille, organigramme), `a_inserer` (un fichier du partage, `chemin`
  relatif à `PARTAGE_GIC`), `perimee` (la version jointe ne vaut plus à la date limite) ou
  `manquante` (avec le `motif`).
- D.1 donne toutes les références du bureau, sauf les absorbées, même sans critère d'expérience
  générale. D.2.x donne un critère d'expérience spécifique chacun (`Critere.experience`, sinon
  déduite du texte ou du mode), avec toutes les références qui y répondent d'après la dernière
  simulation enregistrée (`Selection`), pas seulement celles qui portent les points, sauf celles
  qu'une personne a exclues (règle du porteur, 09/11/2026). Les fiches de référence au format
  Banque mondiale ne sont pas encore au registre : elles sont toutes `manquante`.
- Le calcul est celui de la page « Dossier » (`/avis/<id>/dossier`) : `services.plan_dossier`,
  puis `moteur.avis.sommaire.plan`. Aucun fichier n'est renvoyé.

### `rechercher_experts`

Paramètres : `poste`, `domaines`, `niveau_min`, `annees_experience_min`,
`nb_references_min`, `filtre_references` (même format que le filtre de
critère, appliqué aux affectations de l'expert), `disponibles_seulement`.
Rend `{expert_id, nom, specialite, annees_experience, niveau, nb_references_
correspondantes, statut}`.

### `proposer_filtre_critere`

Paramètres : `texte_critere` (le texte du bailleur, tel quel), `avis_id`
optionnel. **Ne calcule rien** : rend le vocabulaire de la base susceptible
de correspondre (catégories, types d'ouvrages avec leurs familles et leurs
termes validés par pays, ADR 0019 ; les termes proposés à part, sans effet ;
types de quantités) pour que Claude construise un filtre et l'explique à
l'humain. L'humain valide à l'écran. Cet outil est la réponse au problème
« recharge de nappe » ≠ « micro-barrage ».

### `proposer_terme`

Paramètres : `type_ouvrage` (clé), `terme` (tel qu'il est écrit dans l'avis),
`pays` (un pays du bureau, vide pour tous), `source_url`, `nb_avis`, `portee`
(`partout` ou `references`). Crée un `referentiel.Terme` **proposé**, origine
`claude` (ADR 0019) : « AEPS » au Burkina pour l'AES. Une personne le valide
ou le rejette dans l'administration. Un terme qui existe déjà pour ce type et
ce pays est rendu tel quel, avec un avertissement. **Ne valide jamais un
terme.**

### `creer_proposition`

Paramètres : `champs` (objet : reference, objet, type, maitre_ouvrage,
bailleur, date_limite, pays, localites, criteres pressentis), `source_url`,
`fichier_chemin`, `origine` (`claude` par défaut, `veille` pour la veille des
avis, VE02), `forcer`. Crée une `Proposition` à valider. Rend son identifiant
et l'adresse de l'écran de validation. **Ne crée jamais un `Avis`.**

Avant de créer, cherche un avis ou une proposition (même rejetée) qui porte
la même référence, écrite au signe près (« AMI n° 004/2026 » = « ami
N°004-2026 »), dans le même pays quand les deux le disent, ou le même lien.
S'il en trouve un, ne crée rien et rend `deja_connu` (identifiant, adresse,
objet, statut d'une proposition). `forcer=True` crée quand même : seulement
quand l'objet montre un autre avis sous la même référence.

### `enregistrer_brouillon_critere`

Paramètres : `avis_id`, `critere` (code, libellé, mode, points, plafond,
filtre). Enregistre le critère marqué `brouillon` ; l'écran le montre en
attente de confirmation. Permet à Claude de préparer un barème complet que
l'humain relit d'un coup.

## Outils prévus après le MVP

- `assembler_dossier(avis_id)` — produit le PDF paginé, signets, filigrane, en suivant le plan
  de `plan_dossier` (scans insérés à leur place ; ADR et bibliothèque PDF à décider).
- `generer_cv(expert_id, avis_id)` — CV réordonné pour l'avis.
- `proposer_normalisation_mission(code)` — assistance à l'assainissement.
- `rechercher_offres_passees(...)` — bibliothèque des offres soumises.

## Ce que les outils ne font pas, délibérément

- Modifier ou supprimer une mission, une pièce, un expert.
- Changer le statut d'un avis (go / no_go / déposé).
- Lire un fichier du partage pour le renvoyer en entier à Claude : l'outil
  rend le chemin UNC, Claude Desktop ouvre le fichier avec ses propres
  moyens si l'utilisateur le lui demande.
