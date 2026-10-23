# CLAUDE.md — consignes permanentes pour l'assistant

Ce fichier est lu automatiquement au début de chaque session. Il est court
à dessein : les règles d'architecture, le vocabulaire et les conventions
sont dans `CONTEXT.md` ; l'état du travail est dans `docs/plan/en-cours.md`.
Ne pas y recopier ce qui est ailleurs.

## Début de session

Lire, dans cet ordre, avant toute proposition :

1. `CONTEXT.md` — règles non négociables, conventions, vocabulaire métier.
2. `docs/plan/en-cours.md` — où on en est, ce qui bloque, ce qu'il ne faut
   pas refaire. C'est la mémoire de la session précédente.
3. La ligne de la tâche visée dans `docs/plan/taches.md`.
4. L'ADR le plus récent dans `docs/adr/` s'il touche la tâche.

Puis dire en cinq lignes comment on compte s'y prendre et quels fichiers on
va toucher. Pas de code avant l'accord du développeur. Une session = une
tâche du plan ; si la tâche déborde, on le dit, on ne l'étire pas.

## Pendant la session

- Tests écrits avec le code, pas après. `pytest` sur le module touché avant
  de dire qu'une étape est finie.
- Aucune dépendance, aucun modèle, aucune application nouvelle sans le
  signaler explicitement et proposer un ADR (`docs/rituels-ia.md` § 5).
- `moteur/` n'importe jamais Django. Les vues et les outils MCP ne calculent
  rien eux-mêmes.
- Noms en français sans accents ; `Decimal` pour montants et points ;
  migrations nommées ; un commit = un changement, message
  `type(portée): résumé` (`docs/git.md`).
- Lire seulement les parties de fichiers utiles ; filtrer les sorties
  longues (tests, journaux) plutôt que de les coller entières.
- Ne jamais commiter ni pousser sans qu'on le demande. Ne jamais toucher au
  serveur, à IIS ni à l'agent sans qu'on le demande.

## Fin de session

Quand le développeur dit « on arrête », « fin de session », « on s'arrête là »
ou l'équivalent, faire dans cet ordre, sans attendre d'autre consigne :

1. Lancer `ruff check .` et `pytest` sur les modules touchés ; dire ce qui
   passe et ce qui ne passe pas.
2. Réécrire `docs/plan/en-cours.md` en entier selon son modèle : tâche,
   branche et dernier commit, fait, reste, bloqué (avec ce qui a été essayé
   et ce qui ne l'a pas été), à ne pas refaire, décisions à prendre.
   Vingt lignes au plus. Les lignes « Bloqué » et « À ne pas refaire » sont
   les plus importantes.
3. Mettre à jour l'état de la tâche dans `docs/plan/taches.md`.
4. Si une décision d'architecture a été prise, rédiger l'ADR tout de suite
   (format de `docs/adr/0001`), plutôt que de le noter « à écrire ».
5. Proposer le message de commit au format de `docs/git.md`, sans commiter.

La prochaine session repartira d'une conversation neuve et ne saura que ce
qui est dans ces fichiers.

## Commandes utiles (poste de développement, PowerShell)

```powershell
.\scripts\dev\verifier.ps1          # les mêmes contrôles que la CI ; « Tout est vert » attendu
ruff check . ; ruff format --check .
pytest                              # unitaires et intégration (PostgreSQL requis)
pytest -m e2e                       # parcours de bout en bout, Chromium
python manage.py migrate            # après chaque nouvelle migration, sur la base de dev
.\scripts\dev\construire_css.ps1    # après un changement de gabarit ou de classes gic:
python scripts\dev\compiler_traductions.py
```

Serveur de dev : `python manage.py runserver 127.0.0.1:8010 --noreload`
(cache des gabarits : redémarrer après un changement de gabarit).
