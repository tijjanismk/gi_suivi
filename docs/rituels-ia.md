# Rituels de travail avec l'IA

Un développeur seul assisté par l'IA a un avantage (une capacité de
production élevée) et un risque (personne pour lui dire qu'il se trompe).
Ces rituels gardent l'avantage et traitent le risque : ils séparent
l'assistant qui *écrit avec vous* de l'assistant qui *vous relit*, et ils
forcent l'écriture des décisions.

## 1. Démarrer une session de travail

Une session = une tâche du plan, dans une conversation neuve. Fournir, dans
cet ordre :

1. `CONTEXT.md` (toujours ; avec Claude Code, `CLAUDE.md` est lu tout seul)
2. `docs/plan/en-cours.md`, la note de passation de la session précédente
3. Le ticket visé, copié depuis `docs/plan/taches.md`
4. Les fichiers directement concernés (le module à modifier, son test)
5. Pour une tâche de `moteur/` : la section correspondante de
   `docs/suivi-transposition-python.md` ; pour un écran : la capture de la
   maquette ; pour le déploiement : `docs/exploitation.md`
6. L'ADR le plus récent s'il touche la tâche

Puis le message d'ouverture :

```
Tâche : <id> — <titre>. Critères d'acceptation ci-dessus.
Commence par me dire en cinq lignes comment tu comptes t'y prendre et
quels fichiers tu vas toucher. N'écris pas de code avant mon accord.
Écris les tests avec le code, pas après. Ne propose aucune dépendance,
aucun modèle, aucune application nouvelle sans le signaler explicitement.
```

Fin de session : dire « on arrête ». L'assistant lance les vérifications,
réécrit `docs/plan/en-cours.md` (fait, reste, bloqué, à ne pas refaire,
décisions à prendre), met à jour l'état du ticket dans `taches.md`, rédige
l'ADR s'il y a eu une décision, et propose le message de commit (consigne
dans `CLAUDE.md`). On relit la note avant de fermer : c'est tout ce que la
session suivante saura. On ne compte pas sur `/compact`, qui résume avec
perte ; on repart d'une conversation neuve qui relit les fichiers.
Ce qui vaut d'être retenu durablement va à sa place : un piège qui
reviendra dans `CONTEXT.md` § Pièges durables, une décision dans un ADR,
le récit daté en bas de `docs/plan/journal.md`. `CONTEXT.md` reste sous
150 lignes.

## 2. Quand ouvrir une nouvelle conversation pour une revue critique

La conversation qui a écrit le code est la plus mal placée pour le juger :
elle en connaît les intentions et pardonne ce qui n'est pas dit. On ouvre
donc une **conversation vierge**, sans l'historique, à ces moments :

- avant chaque pull request (revue de code, prompt ci-dessous) ;
- à la fin de chaque phase du plan, et avant toute décision d'ADR (critique
  d'architecture, prompt ci-dessous) ;
- quand on a passé plus de deux heures sur un problème sans avancer : on
  décrit le problème à neuf, sans montrer ce qu'on a tenté, et on compare ;
- quand une suggestion de l'IA semble trop belle (une bibliothèque qui règle
  tout, une simplification radicale) : on la soumet à une autre conversation
  en demandant ce qui pourrait mal tourner.

Dans la conversation de revue, on ne défend pas le code. On lit, on note, on
tranche ensuite, seul.

## 3. Prompt de revue de code (prêt à l'emploi)

Fournir `CONTEXT.md`, le ticket et le diff complet de la branche
(`git diff main...dev/<id>`), puis :

```
Tu es un relecteur senior qui n'a pas participé à l'écriture de ce code et
qui n'a aucune raison d'être aimable. Le contexte du projet est dans
CONTEXT.md ; le but de ce changement est le ticket ci-dessus.

Relis le diff et réponds dans cet ordre, sans compliments :

1. Le changement fait-il ce que le ticket demande ? Cite chaque critère
   d'acceptation et dis s'il est couvert, partiellement couvert ou absent.
2. Bogues et cas limites : où ce code se trompe-t-il ? Donne pour chacun un
   exemple concret d'entrée qui le fait échouer.
3. Tests : quels comportements importants ne sont pas testés ? Quels tests
   testent la bibliothèque plutôt que notre code ?
4. Règles du projet (CONTEXT.md) : y a-t-il un import de Django dans
   moteur/, un calcul dans une vue ou un outil MCP, une dépendance nouvelle,
   un modèle ou un champ non prévu dans schema-donnees.md, un nom anglais là
   où le vocabulaire métier impose le français ?
5. Sécurité et données : identité prise ailleurs que dans l'en-tête de
   confiance ? requête sans filtre sur l'utilisateur ? chemin construit à
   partir d'une entrée externe ? donnée personnelle journalisée inutilement ?
6. Lisibilité : les trois endroits les plus difficiles à comprendre pour
   quelqu'un qui reprendrait ce code dans deux ans.
7. Ce que tu supprimerais : code mort, abstraction prématurée, option que
   personne n'a demandée.

Termine par un verdict en une ligne : fusionner / fusionner après
corrections mineures / ne pas fusionner, et la liste des corrections
bloquantes.
```

On corrige ce qui est juste, on écrit dans la PR ce qu'on a écarté et
pourquoi. Une remarque écartée sans raison écrite reviendra.

## 4. Prompt de critique d'architecture (prêt à l'emploi)

Fournir `CONTEXT.md`, `docs/design.md` ou `docs/suivi-transposition-python.md`,
les ADR, et l'arborescence réelle (`tree /F` ou `find`), puis :

```
Tu es un architecte logiciel chargé d'auditer ce projet avant qu'il n'aille
plus loin. Tu n'as pas participé aux choix et tu dois supposer qu'ils
peuvent être mauvais. Le projet est maintenu par une seule personne, pour
des années, sur l'infrastructure décrite.

Réponds dans cet ordre :

1. Les trois décisions les plus risquées de cette architecture, et pour
   chacune : ce qui se passe concrètement si elle est fausse, et quel signe
   précoce permettrait de s'en apercevoir.
2. Ce qui est plus compliqué que nécessaire pour ce bureau, cette équipe et
   ce volume de données. Ce que tu supprimerais ou reporterais.
3. Ce qui manque : la question que personne ne s'est posée (données,
   sécurité, exploitation, humain).
4. Les endroits où le code réel s'écarte du design écrit, d'après
   l'arborescence et les fichiers fournis.
5. La dette que tu accepterais consciemment aujourd'hui, et celle que tu
   refuserais.
6. Si tu devais parier : qu'est-ce qui cassera en premier en production, et
   à quelle échéance ?

Sois concret, cite les fichiers, ne reformule pas le design. Pas de
compliments, pas de « globalement solide ».
```

Le résultat alimente un ADR (si une décision change) ou la liste des
risques de `design.md` (si une décision est confirmée mais surveillée).

## 5. Quand écrire un nouvel ADR

Un ADR est écrit **avant** la mise en œuvre, en une page, dès que l'une de
ces conditions est vraie :

- on ajoute, remplace ou retire une technologie (bibliothèque structurante,
  service, format de stockage) ;
- on change une règle de `CONTEXT.md` ;
- on crée une nouvelle application Django ou un nouveau module de `moteur/` ;
- on prend une décision qu'on aurait du mal à expliquer dans six mois (un
  compromis, un contournement, une dette acceptée) ;
- la direction tranche quelque chose qui engage la conception (racines,
  convention, rétention, groupes) ;
- la critique d'architecture (§ 4) a fait changer d'avis.

Format fixe (voir `0001` et `0002`) : contexte, décision, justification,
conséquences positives et négatives, contre-argument conservé, conditions de
reconsidération. Un ADR ne se modifie pas après acceptation ; on en écrit
un nouveau qui le remplace et on met à jour le statut de l'ancien.

Numérotation : on prend le **numéro suivant libre** au moment d'écrire,
on n'en réserve pas d'avance (les réservations du début, 0003 à 0005,
ont été prises par d'autres décisions). Seule exception en cours : `0009`,
gardé pour le renommage `gic.giconseils.local`. Prochain libre : `0013`.
Sujets encore sans ADR : décisions de la direction pour GI-SUIVI (P05),
pont MCP local et identité, aucune IA côté serveur au MVP (règle 5 de
`CONTEXT.md`).

## 6. Ce que l'IA ne décide pas

Elle propose, le développeur décide : le périmètre d'un ticket, l'ajout
d'une dépendance, la structure d'une table, ce qui se déploie et quand, et
tout ce qui touche aux personnes (qui voit quoi, ce qui est collecté, ce
qui est écrit dans la note à l'équipe). Quand l'IA « décide » à la place du
développeur, c'est que le ticket était mal cadré ; on corrige le ticket.
