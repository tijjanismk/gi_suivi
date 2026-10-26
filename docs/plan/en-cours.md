# En cours — note de passation

Réécrite en entier à la fin de chaque session (consigne dans `CLAUDE.md`).
Vingt lignes au plus. Le récit long est dans `docs/plan/journal.md`, l'état
des tâches dans `docs/plan/taches.md` ; ici, seulement ce que la prochaine
session doit savoir pour reprendre sans refaire.

---

**Date :** 2026-10-26 (session sur le serveur, clone `C:\GIC\travail\gi_suivi`)
**Tâche :** C2 (codification définitive) puis C3 (justificatifs) ; C5 en partie (experts sur `test`)
**Branche :** `main` (dernier commit : `fd5f1df`, CI #134 verte, installé sur `test`) ; cette note, `taches.md`, `journal.md`, ADR 0008 et 0011, `Construire-Missions.ps1` et `Reperer-Justificatifs.ps1` attendent leur commit

**Fait :** `REFERENCES\00_REGISTRE\missions.csv` : 268 codes définitifs, par série et dans l'ordre chronologique (`Construire-Missions.ps1`, ADR 0008 § 6), importés sur `test`. C3 : pièces trouvées par OCR de `D:\` (`Reperer-Justificatifs.ps1`), vues sur planches, 702 pièces découpées (recadrées, redressées : `Decouper-PDF.ps1 -Recadrer -Redresser`) dans `REFERENCES\02_JUSTIFICATIFS\<code>\` et notées dans `decoupages.csv`. `references_rattacher` (+ `--partielles`) sur `test` : 217 références à 3 pièces, 28 partielles, 23 sans pièce ; 702 pièces « à auditer ». 57 experts complets (CV + diplôme, sans point en suspens) importés sur `test`. CI : `test_etat_postes` tombait tous les lundis (`conftest.py`, 5 jours). Livrables dans `C:\GIC\Claude outputs\C3-justificatifs` : `References-incompletes.docx` (35 à chercher, 16 doublons à confirmer, 7 hors registre), `plan-decoupe.csv`, `planches\`, `outils\` (scripts de rapprochement, découpe, rangement, Word), `index\` (index OCR, 67 Mo).

**Reste :** auditer les 702 pièces à l'écran depuis un poste ; le porteur cherche les 35 références du Word dans les archives, puis découpe, rangement et `references_rattacher --partielles` ; verser dans `scripts\exploitation` les outils utiles de `outils\` ; libellé « incomplète(s) laissée(s) » faux avec `--partielles` ; 18 experts après les décisions du directeur ; diplômes non importés (pas de code).

**Bloqué :** écrans `references` et `experts` jamais vus (Kerberos ne passe pas depuis le serveur, à vérifier depuis un poste). Lire la CI : navigateur intégré, session GitHub du porteur (pas de `gh`, Chrome non relié).

**À ne pas refaire :** l'OCR de `D:\` (index gardés dans `outils\..\index`) ; fouiller `D:\AMI` et `D:\OFFRES` (931 PDF relus en entier le 26/10 : rien de neuf, mêmes compilations « FINI ») ; pousser sans lire la CI ; `@("x", 25..27)` en PowerShell (le `..` avale la virgule) ; `Start-Sleep` pour attendre (refusé : attendre dans le navigateur).

**Décisions à prendre :** doublons du classeur (16 de même montant, CARE ×3, Wara, viviers…) ; GIC-BAT-ETC-003 = GIC-BAT-ETU-005 + GIC-BAT-CTR-011 ; GIC-AEP-CTR-023 / GIC-HYD-CTR-034 même contrat ? ; montants PIGO lots 6 et 7 ; 7 documents hors registre ; points des experts ; GIC-Prod.
