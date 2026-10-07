# ADR 0004 — Agent : un service lance et relance l'agent dans chaque session

- **Statut** : appliqué sur le poste pilote le 07/10/2026, à valider par le développeur
- **Date** : 2026-10-07
- **Modifie** : ADR 0002, conséquence « supervision multi-session » (variante par défaut)

## Contexte

L'ADR 0002 retenait par défaut une tâche planifiée « à l'ouverture de session »
qui lance l'agent, et un service qui se borne à surveiller et à relancer cette
tâche. Deux limites sont apparues en écrivant G06 :

- une tâche planifiée attachée à un groupe (« tous les utilisateurs ») ne se
  relance pas de façon fiable dans une session donnée depuis un service ;
- son « redémarrer en cas d'échec » ne joue pas quand le processus est tué :
  la vérification n° 8 de `agent/CONTROLE.md` (agent tué → relancé en moins
  d'une minute) ne pouvait pas passer.

## Décision

Un seul mécanisme : le service `GiSuivi` (LocalSystem, démarrage automatique,
même exécutable que l'agent lancé avec `--service`). Toutes les 15 s, il liste
les sessions actives (verrouillées comprises, déconnectées exclues) et lance
l'agent là où il manque, **avec le jeton de l'utilisateur de la session**
(`WTSQueryUserToken` + `CreateProcessAsUser`) : l'agent ne tourne jamais en
LocalSystem ni avec des droits élevés. Pas de tâche planifiée.

Garde-fous qui vont avec :

- un mutex par session (`Local\GiSuivi-Agent`) : un second agent dans la même
  session s'arrête aussitôt (deux agents compteraient chaque minute deux fois) ;
- l'exécutable lancé par le service est dans `%ProgramFiles%`, non modifiable
  par l'utilisateur (sinon, remplacer l'exe donnerait du code en LocalSystem) ;
- installation, mise à jour et désinstallation arrêtent l'agent par le message
  de fin de session : il écrit ses segments en attente avant de s'arrêter.

## Mesures sur le poste pilote (07/10/2026)

- Agent tué → relancé en 12 s.
- Service : 29 Mo de mémoire privée. Le Gestionnaire des tâches montre deux
  processus `gisuivi-agent.exe` (le service en session 0, l'agent dans la
  session) : le point de contrôle de l'ADR 0002 doit compter les deux
  (environ 65 Mo à eux deux, sous les 80 Mo).

## Conséquences

- L'ouverture de session (CONTROLE n° 6) et l'agent tué (n° 8) passent par le
  même chemin, testé une fois.
- Un délai de 0 à 15 s entre l'ouverture de session et l'apparition de l'icône.
- Si le service est arrêté par un administrateur, plus rien ne relance l'agent :
  c'est voulu (désinstallation, maintenance).
