# Workflow Git

Un développeur seul n'a pas besoin de cérémonie, mais il a besoin de deux
choses qu'une équipe lui donnerait gratuitement : un historique lisible et
un moment de relecture avant que le code n'entre dans `main`. Ce workflow
fournit les deux au moindre coût.

## Branches

| Branche | Rôle | Règle |
|---|---|---|
| `main` | Ce qui est déployé ou déployable | Protégée : pas de push direct, CI verte obligatoire, une pull request par changement |
| `dev/<ticket>-<mot-clé>` | Une tâche du plan | Ex. `dev/S03-segmentation`, `dev/S12-export-excel`. Vit quelques jours au plus |
| `fix/<mot-clé>` | Correction en production | Branche depuis `main`, fusionnée vite |
| `exp/<mot-clé>` | Essai jetable (un prototype, une bibliothèque à évaluer) | Jamais fusionnée telle quelle ; on en tire une branche `dev/` propre ou on la supprime |

Pas de branche `develop`, pas de branches de version : avec une seule
personne et un seul environnement de production, elles n'apportent que des
fusions supplémentaires.

Chaque tâche de `docs/plan/taches.md` correspond à une branche `dev/` et à
une pull request. Si une tâche ne tient pas en une branche de quelques jours,
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
diff. On commite souvent (plusieurs fois par heure) ; on nettoie avant la
pull request si l'historique est brouillon (`git rebase -i`), jamais après.

## Pull request en solo

La pull request est le moment où l'on cesse d'écrire et où l'on relit. Elle
sert à ça, pas à attendre l'approbation de quelqu'un.

1. **Ouvrir la PR** dès que la branche existe, en brouillon, avec le ticket
   en titre (`S03 — Segmentation des observations`). La description reprend
   les critères d'acceptation du ticket sous forme de cases à cocher.
2. **Revue par l'IA, dans une nouvelle conversation** (voir
   `docs/rituels-ia.md`, prompt de revue de code) : on colle le diff, on lit
   les remarques, on corrige ce qui mérite de l'être, on note dans la PR ce
   qu'on a écarté et pourquoi.
3. **Relecture à froid** : le lendemain si possible, ou après une pause.
   Lire le diff dans GitHub, pas dans l'éditeur : l'œil change.
4. **CI verte**, cases à cocher cochées, `CONTEXT.md` mis à jour si
   l'architecture ou l'état du projet ont changé.
5. **Squash and merge** vers `main` : un commit par tâche dans `main`, au
   message propre. La branche est supprimée automatiquement.

Pour les corrections urgentes (`fix/`), les étapes 2 et 3 peuvent être
raccourcies, mais la PR existe toujours : c'est elle qui laisse la trace.

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
