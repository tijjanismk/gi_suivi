# ADR 0006 — Lecture des groupes AD par l'API Windows du serveur

- **Statut** : décidé par le porteur le 08/10/2026
- **Date** : 2026-10-08
- **Complète** : ADR 0002 (identité par IIS), ticket S02

## Contexte

IIS authentifie (Negotiate) et transmet le login (`REMOTE_USER`), mais pas les groupes. Les
droits de l'application (direction, consultation seule) dépendent des groupes AD de la personne.
`identite/groupes.py` prévoyait une source à brancher ; sans elle, personne n'a de droits —
l'application se ferme, elle ne s'ouvre pas. Deux options, chacune une dépendance :

| | API Windows (`pywin32`) | LDAP (`ldap3`) |
|---|---|---|
| Fonctionne | sur le serveur, qui est le contrôleur de domaine | partout où l'annuaire est joignable |
| Identifiants | aucun : le service lit l'annuaire local avec sa propre identité | un compte de liaison et son mot de passe dans `.env` |
| Dépendance | Windows seulement (la CI Linux l'ignore) | pure Python |
| Si l'application quitte un jour le DC | il faut passer à LDAP | rien à changer |

## Décision

**`pywin32`** (`win32net.NetUserGetGroups` et `NetUserGetLocalGroups`), dépendance marquée
`sys_platform == "win32"`, lecteur `identite.groupes_windows.groupes_de`, réglage par défaut en
production (`IDENTITE_LECTEUR_GROUPES`). Le login reçu d'IIS (`GICONSEILS\jean`, ou
`jean@giconseils.local`) est ramené au nom de compte avant la requête. Les groupes sont lus à la
première requête puis toutes les 10 minutes (`IDENTITE_GROUPES_VALIDITE_S`) ; si l'annuaire
ne répond pas, les groupes connus sont conservés (jamais élargis).

## Conséquences

- Aucun secret supplémentaire sur le serveur ; rien à configurer au-delà de l'installation.
- Si l'application est un jour déplacée hors du contrôleur de domaine, écrire le lecteur LDAP
  (même signature `login -> list[str]`) et changer un réglage : le reste ne bouge pas.
- Les tests simulent `win32net` : ils tournent sur Linux (CI) comme sur le poste.
