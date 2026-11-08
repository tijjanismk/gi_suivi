# En cours — note de passation

Réécrite en entier à la fin de chaque session (consigne dans `CLAUDE.md`).
Vingt lignes au plus. Le récit long est dans `docs/plan/journal.md`, l'état
des tâches dans `docs/plan/taches.md` ; ici, seulement ce que la prochaine
session doit savoir pour reprendre sans refaire.

---

**Date :** 2026-11-08 (session sur le serveur AD-SERVEUR, dans `C:\GIC`, du 05 au 08/11 ; dépôt touché seulement par des worktrees à part, jamais dans `C:\GIC\travail\gi_suivi` où une autre session fait AV14)
**Tâches :** C2 et C3 (références : doublons tranchés, pièces rattachées, champs du contrat, registre des attestations) ; R09 (ADR 0020 accepté) ; AMI simulés hors application (PISEN Niger abandonné, PATA-BF Burkina). Aucun code de l'application n'a changé.
**Branches :** `main` à `dc45de8` (ADR 0020, PR #4) ; `test` sert `424a70e` (AV09 ; `/api/sante` le 08/11) ; `dev/AV14-dossier-ami` non commitée dans `C:\GIC\travail\gi_suivi` (autre session) ; `dev/passation-2026-11-08` (cette note ; voir git log).

**Fait (données du partage et de la base de test) :** registre `REFERENCES\00_REGISTRE\missions.csv` et base de test alignés : 283 codes, 63 absorbés (colonne `absorbe_par`), **220 références actives, 0 paire sur « Doublons à arbitrer »** ; doublons tranchés sur les contrats scannés en entier, les 43 décisions du 29/10 remplacées (`C:\GIC\Claude outputs\Rapprochement des références (07-11-2026)\Arbitrage des doublons (07-11-2026).csv`). Sur `test` : 790 pièces, 184 références à 3 pièces, **175 pièces à auditer** ; 160 n° de contrat, 13 pays, 81 bailleurs (13 créés, correspondances sûres), 7 rôles écrits dans les contrats. Registre des attestations sur les 220 (`C:\GIC\Claude outputs\Registre des attestations`) : livrée 188, en cours de récupération 24, mission en cours 7, à remplacer 1 (GIC-ENV-ETU-015). Montants de GIC-ENV-ETU-020 et 021 corrigés d'après les contrats ; GIC-HYD-ETU-051 (mare de Sanké) à 45 jours. Plan de fin : `Dernières étapes des références (07-11-2026).pdf` dans le même dossier ; sauvegardes `dumpdata` dans `sauvegarde base test avant arbitrage`, copies du registre `missions_avant_*.csv`.

**Reste :** étapes 4 à 12 de ce PDF : 13 rescans (`exclure-rescan.txt`), puis refaire le registre des attestations ; attestations à récupérer ; 8 références sans garde ou sans signature (AEP-CTR-025, AEP-CTR-026, AEP-ETC-007, AEP-ETC-014, BAT-CTR-019, BAT-ETU-011, HYD-ETU-013, HYD-ETU-038) ; montant de GIC-HYD-CTR-016 (25 M ou 1,8 M) et mois des associés de Sanké ; audit des 175 pièces et vérification des 220 fiches depuis un poste (63 rôles à confirmer ; dates de début et de fin, part du bureau : aucune source sûre) ; fusion d'AV14 ; code de R09 ; installer `main` sur `test`. Avis : PATA-BF dépôt 10/11 et 13/11 à 9 h (lettre à signer, mission pour 3 760 ha, montant de Dourou), Oxfam TD-26/007 le 17/11 à 17 h (avis n° 3 sur `test`).

**Bloqué :** écrans invérifiables depuis le serveur (Kerberos) : à voir depuis un poste du domaine ; `gh` absent du serveur : PR par le navigateur, CI lue sur GitHub.

**À ne pas refaire :** déduire le rôle d'un groupement de « mandataire du groupement » (la formule est dans les modèles de contrat) ; relancer `references_importer` complet sur `test` (il écrase les corrections et ne défait pas une absorption) ; `services.trancher` sur un code déjà absorbé (refusé : `DecisionDoublon` écrite à la main) ; oublier de relire la nature après `trancher` (ETU + CTR devient ETC) ; passer du code à `manage.py shell` par un tube ou par `-c` avec des guillemets (passer par un fichier et `exec(open(...).read())`) ; un here-string vers `git commit -F -` ; `sed` sur un `.ps1` qui contient `\d` ; unifier les adresses et raisons sociales des dossiers d'AMI ; changer de branche dans `C:\GIC\travail\gi_suivi`.

**Décisions de la session :** arbitrage des doublons confié à l'assistant, sur pièces ; écriture directe dans la base de test quand l'application ne sait pas faire, après `dumpdata` et dans une transaction ; AMI en simulation seulement, rien créé dans l'application ; adresses et raisons sociales gardées par usage ; attestation absente = PV, sinon « en cours de récupération », tenu dans un registre ; PISEN abandonné ; ADR 0020 accepté ; Sanké 45 jours — décisions du porteur, 07/11.

**Décisions à prendre :** l'application comme seule source des références (gérant) ; les 63 rôles ; HYD-CTR-016 ; PATA-BF ; 15 références des scans absentes des Excel du bureau et 4 écarts d'attestation ; ADR 0018 ; ce qui restait du 04/11 (Q01 à Q03, AV12).
