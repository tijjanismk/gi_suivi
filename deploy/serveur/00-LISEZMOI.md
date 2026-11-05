# Scripts serveur — AD-SERVEUR

Cette série rend le serveur reconstructible : chaque étape est un script,
numéroté dans l'ordre d'exécution, qu'on relance sans risque (il ne refait
pas ce qui est déjà fait). Tous s'exécutent en PowerShell 5.1, en
administrateur, **depuis la console du serveur**. Chacun écrit un journal
dans `D:\SAUVEGARDES\journaux\`.

| Script | Tâche du plan | Ce qu'il fait | Avant de lancer |
|---|---|---|---|
| `01-Sauvegarde-Systeme.ps1` | P01 | Sauvegarde complète unique vers D: ; avec `-Planifier`, met en place les trois protections quotidiennes (système → D:, données D: → C:, clichés) | Rien |
| `02-Restreindre-RDP-Local.ps1` | P02 | Bureau à distance limité au réseau local, NLA | 01 fait |
| `03-Mises-a-jour.ps1` | P03 | Applique les mises à jour Windows, programme les suivantes | 01 fait ; fenêtre hors heures de bureau ; redémarrage à prévoir |
| `04-Comptes-et-groupes.ps1` | P04 | OU `GIC`, six groupes, compte de service, comptes d'administration nominatifs | Liste des membres validée par la direction |
| `05-Partage-GIC.ps1` | P06 | `D:\GIC`, arborescence, partage, droits par groupe | 04 fait |
| `06-DNS-SPN.ps1` | S07, S08 | Enregistrements DNS et SPN `HTTP/<nom>` sur le compte de service, pour chaque nom de `..\noms-hotes.ps1` (`app`, `suivi-test`, `suivi`) ; n'ajoute que ce qui manque | 04 fait |
| `07-PostgreSQL.ps1` | S07 | Installe PostgreSQL 18 (ou -Version 17), crée rôle et bases, pare-feu | Installateur EDB téléchargé |
| `08-Python-IIS.ps1` | S07 | Installe Python 3.14, configure IIS (Negotiate seul, ARR, sites), pare-feu | Installateurs Python, URL Rewrite et ARR téléchargés ; mémoire ≥ 16 Go pour la production |

Les scripts d'installation de l'application sont dans le dossier parent
(`installer.ps1`, `service.ps1`, `taches.ps1`, `sauvegarde_pg.ps1`,
`verifier.ps1`, voir `deploy/LISEZMOI.md`). Le serveur reçoit le code par
`git` et n'a **aucun outil de développement** : Git pour Windows, Python,
PostgreSQL, IIS, NSSM, rien d'autre.

## Conventions

- Avant la première exécution d'un script téléchargé : `Unblock-File .\xx.ps1`
  puis `Set-ExecutionPolicy -Scope Process Bypass -Force`.
- Chaque script accepte `-WhatIf` quand il modifie l'annuaire ou les droits :
  il affiche alors ce qu'il ferait sans le faire.
- Les secrets générés (mots de passe du compte de service, de PostgreSQL)
  sont écrits dans `C:\GIC\secrets\`, lisibles seulement par les
  administrateurs et le compte de service. Ils ne sont jamais affichés deux
  fois ni envoyés par courriel.
- Après chaque script réussi : relancer `01-Sauvegarde-Systeme.ps1` pour
  avoir un point de retour récent, et noter la date dans
  `docs/exploitation.md`.

## Ce que ces scripts ne font pas

Retirer des rôles (A16), changer la mémoire (A17), configurer le routeur
(A12), sortir les copies personnelles du serveur (A15) : ce sont des
décisions ou des gestes physiques, pas des scripts.
