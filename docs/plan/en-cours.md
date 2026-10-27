# En cours — note de passation

Réécrite en entier à la fin de chaque session (consigne dans `CLAUDE.md`).
Vingt lignes au plus. Le récit long est dans `docs/plan/journal.md`, l'état
des tâches dans `docs/plan/taches.md` ; ici, seulement ce que la prochaine
session doit savoir pour reprendre sans refaire.

---

**Date :** 2026-10-27 au soir (session sur le serveur, clone `C:\GIC\travail\gi_suivi`)
**Tâche :** module avis AV01 à AV09 (ADR 0013), domaines de la présentation et recodage des VRD (ADR 0014), deuxième page du contrat (ADR 0015). Collecte (C1 à C9) en pause depuis le 27/10 : son reste est ci-dessous.
**Branche :** `main`, dernier commit de code `82eb078` (outils MCP), CI #160 verte, installé sur `test` le 27/10 à 17:29.

**Fait :** module avis sur `test` : moteur (`moteur/avis/`, note sûre et note possible), avis, barème saisi en champs avec aperçu, simulation (choix forcer / exclure avec motif), pièces exigées jugées à la date limite, experts demandés (années depuis le premier diplôme quand la carrière manque), propositions à valider, 9 outils MCP en fonctions (`avis/outils_mcp.py`, critère `brouillon`). Avis d'essai UNICEF LRPS-MLI-2026-9206428 saisi (script rejouable `C:\GIC\Claude outputs\UNICEF\av07_unicef.py`) : 26 références de contrôle retenues (Word : 29), note possible 25/25, sûre 0 (attestations non auditées) ; TVA périmée 13 j avant le dépôt, non-faillite du 16/10 valide ; postes : contrôleur principal 14 experts complets, QHSE 1 (BAMADIO Abdel Kader), forages 8, génie civil 11. Six domaines (AEP, RUR, RTE, HYD, BAT, ENV) et 38 sous-domaines ; 5 VRD recodés (GIC-RTE-CTR-013/014, GIC-RTE-ETC-001, GIC-AEP-ETC-011, GIC-BAT-ETU-012) sur le partage, dans `missions.csv`, `recodages.csv` et sur `test` ; VRD et AQA retirés. Certificat de non-faillite du 16/10 (photo) dans `PIECES\NON-FAILLITE`, noté dans `depots.csv`, enregistré sur `test` (valable au 16/01/2027).

**Reste :** AV07 : verser les TDR (annexe B, points 9.1, 11, 12) dans le dossier de l'avis, saisir le reste du barème et le seuil (la RFP dit 70 au plus et 70 au moins), auditer les attestations ; AV09 : montage `/mcp/` et pont du poste (ADR 0016, à décider) ; AV03 : parcours Playwright, mesure des 15 minutes ; AV10 SOMAPEP attend C4 ; proposer la liste des références à marquer RUR en domaine secondaire ; coder les 3 références AEP nouvelles du dossier `D:\AMI\Références 27-10-2026` et vérifier deux montants absents du registre (ENABEL LCIANK 30 215 500 ; CR Sikasso 22 AEP lot 3, 9 982 000) ; scan de l'original du certificat de non-faillite (« Nouveau scan de la version en cours ») ; attestation TVA du bureau. Collecte : auditer les 702 pièces ; 35 références à chercher ; points des 30 experts « à vérifier », diplômes de 9 experts, DUT de SIDIBE ; extrait RCCM, liste des moyens, jour de l'attestation OICM ; incohérences en Word à revoir avec le porteur le 28/10.

**Bloqué :** écrans jamais vus depuis un poste (Kerberos ne passe pas depuis le serveur : 401 « Negotiate incomplet ») ; la CI se lit dans le navigateur intégré. Tâche « démarrages hebdo » en échec (code 1), antérieure à ce travail.

**À ne pas refaire :** lancer `Tout-en-un.ps1` avec `*>&1` (un avis de `psql` devient une erreur) ; `-ExecutionPolicy Bypass` (refusé) ; `makemigrations` contre la base de `test` (utiliser `DATABASE_URL=postgres://aucun:aucun@127.0.0.1:1/aucune`, une à deux minutes d'attente) ; mettre un CSV de données dans Git ; relancer `Construire-Missions.ps1` (renumérote tout, ADR 0014) ; l'OCR de `D:\` ; fouiller `D:\AMI` et `D:\OFFRES` ; `Start-Sleep` pour attendre.

**Décisions à prendre :** ADR 0016 (dépendance `mcp`, pont du poste) ; doublons du classeur (16 de même montant, CARE ×3, Wara…), GIC-BAT-ETC-003, GIC-AEP-CTR-023 / GIC-HYD-CTR-034, montants PIGO lots 6 et 7, 7 documents hors registre ; points des experts ; présentation et carte OICM exigées par défaut ou non ; GIC-Prod.
