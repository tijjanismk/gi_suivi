# ADR 0009 — Adresse de l'application : app.giconseils.local

- **Statut** : accepté par le porteur le 05/11/2026
- **Date** : 2026-11-05
- **Décideur** : le porteur
- **Numéro** : 0009 était gardé depuis octobre pour ce renommage (prévu alors sous le nom
  `gic.giconseils.local`) ; le porteur a retenu `app`.

## Contexte

L'application s'appelait GI-SUIVI à l'origine, et ses adresses en gardent la trace :
`suivi-test.giconseils.local` (environnement test, site IIS `suivi-test`, port 8001) et
`suivi.giconseils.local` (production, site `suivi`, port 8000). Depuis, elle porte aussi les
références, les experts, les pièces administratives et les avis : « suivi » ne la décrit plus.
Au 05/11/2026, seul l'environnement test tourne (service `GIC-Test`) ; c'est lui que le bureau
utilise. La production n'a pas de service (décision GIC-Prod en attente).

Ce qui dépend du nom d'hôte :

- Django refuse (400) un nom absent d'`ALLOWED_HOSTS`, lu dans le `.env` du serveur ; les
  origines CSRF en sont tirées (`config/settings/prod.py`). IIS transmet le nom demandé
  (ARR, `preserveHostHeader`).
- Kerberos : le navigateur demande un ticket pour `HTTP/<nom>` ; le SPN doit être sur
  `svc-application`, qui valide le ticket (ADR 0007). Le code ne dépend pas du nom.
- TLS : certificat **auto-signé** (pas d'autorité de certification sur AD-SERVEUR), approuvé
  **poste par poste** par le kit de l'agent et la GPO « GI-Suivi - Agent ». Un nouveau nom
  impose un nouveau certificat, donc une nouvelle diffusion.
- L'agent envoie à `https://suivi-test.giconseils.local` (`url_api` de sa configuration,
  publiée par la GPO) ; le pont MCP des postes vise la même adresse (ADR 0016).

## Décision

1. L'environnement **test** prend l'adresse **`https://app.giconseils.local`**. La production
   garde `suivi.giconseils.local` jusqu'à la décision GIC-Prod. Les noms des sites IIS, des
   services, des dossiers et des bases ne changent pas.
2. Le porteur quitte `suivi-test.giconseils.local` (« je veux quitter suivi-test », 05/11/2026).
   Il **reste servi comme alias** (liaison IIS, SPN, DNS, `ALLOWED_HOSTS`) le temps de la bascule,
   puis il est **retiré** : d'abord l'enregistrement DNS seul, au plus tôt une semaine après la
   publication de la GPO (le retrait se défait en une commande et les postes restés en arrière se
   voient dans « État des postes ») ; ensuite le SPN, les liaisons IIS et la ligne du tableau.
3. Les noms d'hôte ne sont écrits qu'à un endroit : `deploy/noms-hotes.ps1` (nom principal en
   premier, puis les alias). `installer.ps1`, `verifier.ps1`, `serveur/06-DNS-SPN.ps1` et
   `serveur/08-Python-IIS.ps1` le lisent ; `tests/test_noms_hotes.py` le contrôle.
4. `installer.ps1` **complète** `ALLOWED_HOSTS` dans un `.env` conservé : il ajoute les noms du
   tableau qui manquent, il n'en retire aucun.
5. Certificat : `08-Python-IIS.ps1 -AutoSigne` ne réutilise un certificat que s'il couvre tous
   les noms ; sinon il en crée un pour `app`, `suivi-test` et `suivi`. Le nouveau certificat
   n'est attaché qu'aux noms qui n'en ont pas : les anciens gardent le leur jusqu'à
   `-RemplacerCertificat` (inutile pour `suivi-test`, qui sera retiré ; gardé pour la production).
6. L'agent passe sur `url_api` = `https://app.giconseils.local` (`agent/config-pilote.json`).
   Une seule publication de la GPO porte le nouveau certificat et cette configuration, avec le
   même kit 0.2.4 (`creer-gpo-agent.ps1 -Config`) : chaque poste, à son redémarrage, approuve le
   certificat puis envoie à `app`, sans état intermédiaire. Un poste pas encore redémarré envoie
   toujours à `suivi-test`. Le kit ajoute `app` à la zone Intranet local (la stratégie
   `AuthServerAllowlist` couvre déjà `*.giconseils.local`).
7. Les actions sur l'AD et le DNS (enregistrement A, SPN) et la diffusion du certificat sont
   faites par le porteur. La procédure est au § 6 de `docs/exploitation/liste-de-controle-serveur.md`.

## Justification

- Garder l'ancien nom en alias rend la bascule sans coupure : l'agent de chaque poste continue
  d'envoyer pendant que le certificat se diffuse, au rythme des redémarrages.
- Publier le certificat et l'adresse ensemble évite une seconde vague de redémarrages, et un
  poste n'envoie jamais à `app` sans approuver son certificat (même installation).
- Retirer d'abord le seul DNS donne un contrôle réel (un poste resté en arrière cesse d'envoyer et
  garde ses mesures dans son tampon) qu'on défait en une commande, avant de toucher à l'AD et à IIS.
- Ne pas attacher le nouveau certificat aux anciens noms évite le seul vrai risque : un poste qui
  ne l'approuve pas encore perdrait l'agent (erreur TLS) et l'accès à l'application.
- Un seul tableau de noms évite qu'un script reste sur l'ancien nom (c'était quatre copies).
- Renommer les sites IIS, les services ou les dossiers n'apporte rien à l'utilisateur et
  toucherait des tâches planifiées, des droits et des journaux qui marchent.

## Conséquences

Positives :

- L'adresse donnée au bureau ne dépend plus du premier module.
- Ajouter ou retirer un nom ne touche qu'une ligne de `noms-hotes.ps1`, puis les scripts
  rejouables (06, 08, installer).

Négatives, assumées :

- Pendant la bascule (une à deux semaines), deux adresses mènent au même environnement, et deux
  certificats sont en service (l'ancien pour `suivi-test` et `suivi`, le nouveau pour `app`).
- Le serveur ne note pas l'adresse par laquelle chaque agent envoie : le contrôle avant le retrait
  passe par la coupure du seul DNS (étape 8 de la liste de contrôle).
- Le nom principal de test s'appelle `app` alors que la production s'appelle encore `suivi` :
  à revoir avec la décision GIC-Prod.
- Le premier `installer.ps1` après la fusion tourne avec l'ancienne copie du script si le dépôt
  du serveur n'a pas été mis à jour avant (`git fetch` puis `checkout`) : la liste de contrôle le
  rappelle.

## Contre-argument conservé

Donner tout de suite `app` à la production et `app-test` au test aurait évité un second
renommage au démarrage de la production, au prix d'une adresse que personne n'utilise encore
et d'un enregistrement DNS et d'un SPN de plus.

**Reconsidérer cette décision si** : la production démarre (le nom `app` devrait alors la
désigner), ou si une autorité de certification interne arrive (un certificat générique pour
`*.giconseils.local` ferait de chaque nouveau nom une simple ligne DNS et SPN).
