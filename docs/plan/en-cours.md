# En cours — note de passation

Réécrite en entier à la fin de chaque session (consigne dans `CLAUDE.md`).
Vingt lignes au plus. Le récit long est dans `docs/plan/journal.md`, l'état
des tâches dans `docs/plan/taches.md` ; ici, seulement ce que la prochaine
session doit savoir pour reprendre sans refaire.

---

**Date :** 2026-10-26 (session sur le serveur, clone `C:\GIC\travail\gi_suivi`)
**Tâche :** C2 (codification définitive) puis C3 (justificatifs) ; C5 en partie (experts sur `test`) ; C8 (pièces administratives sur `test`)
**Branche :** `main` (dernier commit de code : `a12b646`, CI #138 verte, installé sur `test`, migration `administratif.0003` appliquée)

**Fait :** `REFERENCES\00_REGISTRE\missions.csv` : 268 codes définitifs, par série et dans l'ordre chronologique (`Construire-Missions.ps1`, ADR 0008 § 6), importés sur `test`. C3 : pièces trouvées par OCR de `D:\` (`Reperer-Justificatifs.ps1`), vues sur planches, 702 pièces découpées (recadrées, redressées : `Decouper-PDF.ps1 -Recadrer -Redresser`) dans `REFERENCES\02_JUSTIFICATIFS\<code>\` et notées dans `decoupages.csv`. `references_rattacher` (+ `--partielles`) sur `test` : 217 références à 3 pièces, 28 partielles, 23 sans pièce ; 702 pièces « à auditer » ; la liste montre les pièces rattachées et le reste à auditer (« 3 / 3 · 3 à auditer », filtres « à auditer » et « pièce manquante » ; `58149af`), le porteur audite à l'écran. Fiches Word d'incohérences (références sans codes, CV) dans `C:\GIC\Claude outputs\Incoherences`. 57 experts complets (CV + diplôme, sans point en suspens) importés sur `test`. CI : `test_etat_postes` tombait tous les lundis (`conftest.py`, 5 jours). C8 : `administratif_importer` (ADR 0010 § 11) : 19 pièces enregistrées sur `test` d'après `C:\GIC\Claude outputs\Administratif\import-pieces-2026-10-26.csv` (registre au 26/10 : 14 valides ou permanentes, TVA et non-faillite expirées) ; types PRESENTATION et CARTE-PRO-OICM ; présentation compactée (`Compacter-PDF.ps1`, 324 Mo → 2,5 Mo, page 8 en double retirée, original dans `ADMINISTRATIF\PRESENTATION\_original`). Livrables dans `C:\GIC\Claude outputs\C3-justificatifs` : `References-incompletes.docx` (35 à chercher, 16 doublons à confirmer, 7 hors registre), `plan-decoupe.csv`, `planches\`, `outils\` (scripts de rapprochement, découpe, rangement, Word), `index\` (index OCR, 67 Mo).

**Reste :** auditer les 702 pièces à l'écran depuis un poste ; le porteur cherche les 35 références du Word dans les archives, puis découpe, rangement et `references_rattacher --partielles` ; verser dans `scripts\exploitation` les outils utiles de `outils\` ; libellé « incomplète(s) laissée(s) » faux avec `--partielles` ; 18 experts après les décisions du directeur ; diplômes non importés (pas de code) ; pièces administratives : demander l'attestation TVA du mois et un nouveau certificat de non-faillite, lire le jour exact de l'attestation OICM (01/07/2026 supposé), refaire la liste des moyens, extrait RCCM manquant.

**Bloqué :** écrans `references` et `experts` jamais vus (Kerberos ne passe pas depuis le serveur, à vérifier depuis un poste). Lire la CI : navigateur intégré, session GitHub du porteur (pas de `gh`, Chrome non relié).

**À ne pas refaire :** l'OCR de `D:\` (index gardés dans `outils\..\index`) ; fouiller `D:\AMI` et `D:\OFFRES` (931 PDF relus en entier le 26/10 : rien de neuf, mêmes compilations « FINI ») ; pousser sans lire la CI ; `@("x", 25..27)` en PowerShell (le `..` avale la virgule) ; `Start-Sleep` pour attendre (refusé : attendre dans le navigateur).

**Décisions à prendre :** doublons du classeur (16 de même montant, CARE ×3, Wara, viviers…) ; GIC-BAT-ETC-003 = GIC-BAT-ETU-005 + GIC-BAT-CTR-011 ; GIC-AEP-CTR-023 / GIC-HYD-CTR-034 même contrat ? ; montants PIGO lots 6 et 7 ; 7 documents hors registre ; points des experts ; présentation et carte OICM exigées par défaut ou non (écran « Types de pièces ») ; GIC-Prod.
