# Workflow Git

Un développeur seul n'a pas besoin de cérémonie, mais il a besoin de deux
choses qu'une équipe lui donnerait gratuitement : un historique lisible et
un moment de relecture avant que le code n'entre dans `main`. Ce workflow
fournit les deux au moindre coût.

## Branches

| Branche | Rôle | Règle |
|---|---|---|
| `main` | Ce qui est déployé ou déployable | On n'y fusionne qu'une branche passée par `scripts\dev\verifier.ps1` ; un commit par tâche |
| `dev/<ticket>-<mot-clé>` | Une tâche du plan | Ex. `dev/S03-segmentation`, `dev/S12-export-excel`. Vit quelques jours au plus |
| `fix/<mot-clé>` | Correction en production | Branche depuis `main`, fusionnée vite |
| `exp/<mot-clé>` | Essai jetable (un prototype, une bibliothèque à évaluer) | Jamais fusionnée telle quelle ; on en tire une branche `dev/` propre ou on la supprime |

Pas de branche `develop`, pas de branches de version : avec une seule
personne et un seul environnement de production, elles n'apportent que des
fusions supplémentaires.

Chaque tâche de `docs/plan/taches.md` correspond à une branche `dev/` et à
un commit dans `main`. Si une tâche ne tient pas en une branche de quelques jours,
c'est qu'elle doit être découpée dans le plan, pas étirée dans Git.

## Commits

Format : `type(portée): résumé à l'impératif, en français, 72 caractères max`.

| Type | Quand |
|---|---|
| `feat` | Une fonctionnalité visible |
| `fix` | Une correction |
| `refactor` | Du code change, le comportement non |
| `test` | Tests seuls |
| `docs` | Documentation, ADR, CONTEXT |
| `chore` | Dépendances, CI, outillage |
| `deploy` | Scripts et configuration de `deploy/` |

Portées : `moteur`, `suivi`, `agent`, `identite`, `avis`, `references`,
`experts`, `mcp`, `ci`, `deploy`, `docs`.

Exemples :

```
feat(moteur): retirer le temps inactif au-delà du seuil depuis la dernière action
fix(agent): relancer l'envoi après un 401 Kerberos expiré
test(moteur): couvrir la fusion Document1 → Courrier.docx
docs(adr): 0003 pont MCP local et identité
```

Un commit = un changement cohérent qui passe les tests. Le corps du message
explique le *pourquoi* quand il n'est pas évident ; le *quoi* est dans le
diff. On commite souvent (plusieurs fois par heure) sur la branche : la
fusion en un seul commit dans `main` (`merge --squash`) tient l'historique
propre.

## Vérifier en local, puis pousser (décision du 07/10/2026)

Pas de pull request : tout se vérifie sur le poste, GitHub garde la copie et
l'historique. La CI GitHub tourne encore à chaque envoi et doit confirmer ce
qui a déjà passé en local.

1. **Travailler sur la branche** `dev/<ticket>-<mot-clé>`, en local.
2. **`.\scripts\dev\verifier.ps1`** : les mêmes contrôles que la CI (ruff,
   migrations, tests moteur et Django sur PostgreSQL, tests de l'agent). On
   ne va pas plus loin tant que la dernière ligne ne dit pas « Tout est vert ».
3. **Relecture à froid** du diff (`git diff main`), après une pause ; revue
   par l'IA dans une nouvelle conversation si le changement est délicat
   (`docs/rituels-ia.md`).
4. **Fusion dans `main` en local**, un commit par tâche :
   `git switch main ; git merge --squash dev/<ticket> ; git commit`.
   `CONTEXT.md` et `docs/plan/taches.md` mis à jour dans ce commit.
5. **Pousser `main`**, après avoir vérifié que le dépôt GitHub est toujours
   privé (il décrit le serveur et le réseau du bureau). La branche locale est
   supprimée.

## Déploiement par Git (décision du 08/10/2026)

Le serveur tient un clone du dépôt privé (`C:\GIC\depot`, jeton GitHub en lecture seule) :
`deploy\installer.ps1 -Env test -Ref main` met l'environnement test au niveau de `main` ;
`-Env prod -Ref vX.Y.Z` exige un tag. Rien n'est copié à la main entre le poste et le serveur ;
ce qui n'est pas dans GitHub n'existe pas pour le serveur. Liste de contrôle :
`docs/exploitation/liste-de-controle-serveur.md`.

**Aucun outil de développement sur le serveur.** Il n'y a ni Tailwind, ni gettext, ni pytest,
ni compilateur : ce qui se construit l'est sur le poste et se commite — `interface/static/css/gic.css`
(`scripts\dev\construire_css.ps1`), `locale/fr/LC_MESSAGES/django.mo`
(`scripts/dev/compiler_traductions.py`), `deploy/requirements.txt`
(`scripts/dev/exporter_dependances.py`, contrôlé par `verifier.ps1`). Le serveur installe les
dépendances en roues binaires seulement. Seul l'agent (exécutable PyInstaller) reste hors Git :
kit zip produit par `agent\preparer-kit.ps1`, copié sur le partage `GIC\deploy\agent\`.

## Versions et déploiement

- Chaque déploiement en production correspond à un tag `vX.Y.Z` sur `main`
  (`v0.3.0` = fin de la phase 4, par exemple). Le tag est posé après
  déploiement réussi, pas avant.
- L'agent a sa propre version, dans `agent/gisuivi_agent/__init__.py` et
  dans le MSI : `agent-vX.Y.Z`. Elle n'avance que quand l'agent change.
- `CHANGELOG.md` à la racine, une section par tag, trois lignes maximum par
  changement, rédigé pour la direction et non pour le développeur.

## Ce qui n'entre jamais dans Git

`.env`, tout fichier contenant un mot de passe ou un chemin personnel, les
exports de données (`*.csv` de missions, `*.xlsx` du registre), les PDF de
justificatifs, les MSI construits (ils vont dans les releases GitHub ou sur
le partage `deploy\`), les dossiers `dist/` et `build/` de PyInstaller.
`.gitignore` les liste ; `pre-commit` refuse un commit qui contiendrait un
secret évident (crochet `detect-secrets` ou expression régulière sur
`password=`).
