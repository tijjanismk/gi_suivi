# En cours — note de passation

Réécrite en entier à la fin de chaque session (consigne dans `CLAUDE.md`).
Vingt lignes au plus. Le récit long est dans `docs/plan/journal.md`, l'état
des tâches dans `docs/plan/taches.md` ; ici, seulement ce que la prochaine
session doit savoir pour reprendre sans refaire.

---

**Date :** 2026-10-23 (session sur le serveur, clone `C:\GIC\travail\gi_suivi`)
**Tâche :** C5 — identités des experts « à vérifier » tranchées sur leurs CV et diplômes (données de `D:\GIC`) ; incident du redémarrage de GIC-Test
**Branche :** `main` (dernier commit : `d2d6abb`) ; non commités : `deploy/service.ps1`, cette note, `taches.md`, `journal.md`

**Fait :** colonne `Personne` → `Dossier` dans `EXPERTS\_registre\experts.csv` et `fichiers-experts.csv` (ce que lit `experts_importer`) ; 17 décisions d'après les dates de naissance des diplômes (3 fusions, 5 dossiers renommés au nom du diplôme, 3 catégories revues, « Technicien DEF+4 » → « Technicien » + colonne `Niveau`) ; 75 personnes ; 32 déplacements par `Deplacer-GIC.ps1` ; fiche « Revue des experts — 23/10/2026 » (doc claude.ai, privée tant que le porteur ne la partage pas). Redémarrage du serveur : GIC-Test ne démarrait plus ; corrigé sur le service et dans `deploy/service.ps1` (démarrage différé, trois relances).

**Reste :** reporter les choix du directeur dans `experts.csv` (`Decision`, `A_verifier`), puis importer X01 sur `test` ; 17 fichiers hors sujet dans `REFERENCES\03_A_CLASSER\depuis-experts`, à ranger avec C6 et C7 ; `suivi.GICONSEILS.LOCAL` (prod) répond 502 : aucun service GIC-Prod n'existe encore.

**Bloqué :** l'import X01 n'a pas été lancé (ni ruff ni pytest sur le serveur ; `manage.py` sur `test` non demandé) : seule sa lecture du registre a été rejouée en PowerShell (colonne trouvée, catégories reconnues, aucune paire nom + prénoms en double). Les deux DIAKITE Adama gardent leur précision entre parenthèses dans les prénoms (`separer_nom`) : pas corrigé, c'est du code.

**À ne pas refaire :** relire les CV des 17 experts (tout est dans `experts.csv`) ; soupçonner le mot de passe de `svc-application` si GIC-Test ne démarre pas après un redémarrage : le serveur est contrôleur de domaine, le service partait une seconde après Netlogon (événement 7038) ; retirer à la main une autre capture d'un même diplôme (`Rangement-GIC.ps1` la recopierait) ; écrire un script PowerShell accentué sans BOM (PS 5.1 casse les noms).

**Décisions à prendre :** les 11 points de la fiche (CV DIAKITE né en 1987 ou 1993, scan du diplôme OUMAROU, titre « Docteur » de LAWSON…) ; clé des homonymes dans `experts_importer` (le dossier plutôt que nom + prénoms ?) ; retrait des captures en double d'un même diplôme.
