# ADR 0007 — Le ticket Kerberos est vérifié par l'application, pas par IIS

- **Statut** : décidé le 09/10/2026, après constat sur AD-SERVEUR
- **Date** : 2026-10-09
- **Modifie** : ADR 0002 (identité transmise par IIS via `X-Remote-User`) ; ADR 0001 inchangé
  (toujours aucun mot de passe applicatif, toujours Kerberos seul)

## Contexte

Le schéma prévu : IIS (authentification Windows, Negotiate seul) authentifie, et une règle de
réécriture pose `X-Remote-User = {LOGON_USER}` avant de transmettre à Uvicorn par ARR.
Sur le serveur réel (Windows Server 2025, IIS déjà en service pour RDWeb) :

- en **mode noyau** (par défaut), IIS authentifie bien (journal : `GICONSEILS\ODICKO`) mais
  `LOGON_USER` est **vide** au moment où la règle de réécriture s'exécute → l'application reçoit
  une requête sans identité (« Identité Windows absente ») ;
- en **mode utilisateur**, l'identité serait disponible, mais IIS **refuse les tickets des postes**
  (`401.2`, l'agent comme le navigateur).

Les deux heures de diagnostic (sonde `/api/sante?identite=1`, journaux IIS) ont écarté le proxy,
le certificat, la zone Intranet, les processus survivants.

## Options

| | Garder IIS pour l'authentification | **L'application vérifie le ticket** | HttpPlatformHandler |
|---|---|---|---|
| Principe | trouver un réglage IIS qui rende `LOGON_USER` disponible à la réécriture | IIS laisse passer `Authorization: Negotiate …` ; le service, qui tourne sous `svc-application` (porteur des SPN), valide le ticket par SSPI (`pywin32`) | IIS lance Uvicorn lui-même et transmet un jeton Windows |
| Dépendance | aucune | aucune nouvelle (`pywin32` déjà là, ADR 0006) | module IIS supplémentaire, refonte du service (plus de NSSM) |
| Risque | inconnu : non trouvé après essais | faible : chemin SSPI standard, un seul aller-retour (Kerberos) | moyen : nouvelle architecture de lancement |

## Décision

**L'application valide le ticket** (`identite/negotiate.py`, `IDENTITE_SOURCE = "negotiate"` en
production). Pour `suivi` et `suivi-test`, IIS : anonyme activé, authentification Windows IIS
désactivée ; ARR transmet l'en-tête `Authorization`. Sans ticket, l'application répond `401` avec
`WWW-Authenticate: Negotiate` — le navigateur (site en zone Intranet ou `AuthServerAllowlist`) et
l'agent (`requests-negotiate-sspi`) envoient alors le ticket. **Kerberos seul** : un échange NTLM
(plusieurs allers-retours) est refusé, comme avant.

## Conséquences

- Les règles du blueprint tiennent : pas de page de connexion, pas de mot de passe applicatif,
  identité Windows, groupes AD (ADR 0006).
- Le service **doit** tourner sous `svc-application` (c'est son compte qui détient la clé des SPN
  `HTTP/suivi…`) : `service.ps1` le fait déjà ; un autre compte casserait l'authentification.
- `X-Remote-User` et `IDENTITE_SOURCE = "iis"` restent dans le code pour un autre frontal.
- Les tests simulent l'authentificateur (`IDENTITE_AUTHENTIFICATEUR_NEGOTIATE`) : CI Linux inchangée.
- `/api/sante?identite=1` reste comme sonde de diagnostic de la chaîne IIS → ARR → application.
