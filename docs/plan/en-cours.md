# En cours — note de passation

Réécrite en entier à la fin de chaque session (consigne dans `CLAUDE.md`).
Vingt lignes au plus. Le récit long est dans `docs/plan/journal.md`, l'état
des tâches dans `docs/plan/taches.md` ; ici, seulement ce que la prochaine
session doit savoir pour reprendre sans refaire.

---

**Date :** 2026-10-23 (session sur le serveur, clone `C:\GIC\travail\gi_suivi`)
**Tâche :** C5 (experts tranchés sur leurs CV) ; incident du redémarrage ; CI réparée ; `test` mis à jour
**Branche :** `main` (dernier commit : `6e5d822`, CI #130 verte) ; cette note, `taches.md` et `journal.md` attendent leur commit

**Fait :** registre `EXPERTS\_registre\experts.csv` : colonne `Dossier` (lue par `experts_importer`), 17 décisions d'après les dates de naissance des diplômes, 75 personnes ; fiche « Revue des experts — 23/10/2026 » pour le directeur (doc claude.ai privée tant que le porteur ne la partage pas). GIC-Test en démarrage différé avec trois relances (`deploy/service.ps1`). CI : `administratif/demo.py` créait `_perimees\…` comme un seul nom sous Linux (`6e5d822`). `test` sur `main` (`6e5d822`) par `installer.ps1 -Env test -Ref main` : 9 migrations, 16 types de pièces, 7 domaines, 12 types d'ouvrages ; `app_precedent` = `ba7efd8`. Import à blanc des experts sur `test` : 75 créés, 0 erreur.

**Reste :** reporter les choix du directeur dans `experts.csv`, puis `experts_importer` pour de vrai sur `test` ; construire l'onglet `Missions` de la liste maîtresse (C2) à partir de `REFERENCES\01_SOURCES\2026-08_version-arrangee\Liste génerale de références -Août 2026.xlsx` (un onglet par domaine, aucun code), puis `references_importer --simuler` ; le porteur ajoute lui-même Administrateur à `GI-Direction` (`Add-ADGroupMember`) ; GIC-Prod n'existe pas (`suivi.giconseils.local` → 502).

**Bloqué :** les nouveaux écrans ne s'ouvrent pas depuis le serveur : l'application exige Kerberos (ADR 0007) et les requêtes du contrôleur de domaine partent en NTLM (journal « Negotiate incomplet ») ; le navigateur intégré non plus. Le porteur a vérifié `/administratif/` depuis un poste (Administrateur, consultation seule). `references` et `experts` pas encore vus depuis un poste.

**À ne pas refaire :** relire les CV des 17 experts ; soupçonner le mot de passe de `svc-application` après un redémarrage (contrôleur de domaine, événement 7038) ; rediriger `2>&1` sur `installer.ps1` dans PowerShell 5.1 (les avertissements de `check --deploy` deviennent des erreurs fatales) ; tester les écrans depuis le serveur ; écrire un script PowerShell accentué sans BOM ; mettre des accents graves dans une chaîne PowerShell entre guillemets doubles.

**Décisions à prendre :** les 11 points de la fiche des experts ; clé des homonymes dans `experts_importer` (le dossier plutôt que nom + prénoms ?) ; codification des missions (C2, ADR 0008) ; création de GIC-Prod ; membres des groupes `GI-Offres` et `GI-Administratif` (AD inchangé depuis le 21/10).
