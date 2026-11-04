# En cours — note de passation

Réécrite en entier à la fin de chaque session (consigne dans `CLAUDE.md`).
Vingt lignes au plus. Le récit long est dans `docs/plan/journal.md`, l'état
des tâches dans `docs/plan/taches.md` ; ici, seulement ce que la prochaine
session doit savoir pour reprendre sans refaire.

---

**Date :** 2026-11-04 (session sur le poste, worktree `C:\dev\gic\.claude\worktrees\friendly-wright-9c4968`, commencée le 28/10)
**Tâches :** P08 sauvegarde hors site (ADR 0018, proposé) ; Q01 à Q03 système qualité ISO 9001 (hors dépôt) ; AV11 fusionné le 28/10. Le code n'a pas bougé depuis le 28/10.
**Branches :** `main` à `200ddcc` (AV11 fusionné le 28/10, puis les commits du serveur du 30/10 et du 02/11 : ADR 0017 cinq domaines, filtre type d'ouvrage, rotation par page de `Decouper-PDF.ps1`) ; `dev/P08-sauvegarde-hors-site` (ADR 0018, non poussée) ; `dev/passation-2026-11-04` (cette note ; voir git log).

**Fait :** ADR 0018 rédigé en « proposé » (restic vers un stockage compatible S3, chiffré sur le serveur ; versions vérifiées le 01/11 : restic 0.19.1, PostgreSQL 18 jusqu'au 14/11/2030). Documents qualité sur claude.ai, privés, à partager par le porteur : fiche de mission « Note de conception de l'archivage » (https://claude.ai/artifact/Ku4FeQ6vqPH635ENwy7dUa, et en Word) ; plan d'archivage SAE léger v0.1 (https://claude.ai/artifact/5DAY3QmmJViCKkozYz1Hw8 : rôles, types de documents et durées, archives papier, journal, contrôles) ; politique qualité et cartographie des processus v0.1 (https://claude.ai/artifact/EFnuCfqb6gKaqGBBf6V55w : périmètre, politique à signer, 5 objectifs, 11 processus et pilotes, décision « on répond ou pas », risques), en PDF avec une note d'une page pour M. Dicko. `verifier.ps1` vert le 04/11, mais 8 parcours navigateur sur 9 ignorés (Chromium de Playwright absent).

**Reste :** décision du porteur sur l'ADR 0018 et le fournisseur ; AV12 (qui, quand, pourquoi de la décision « on répond ou pas », trois champs et une migration) ; Q : signature de la politique par Dicko, prénom de Kane, nom du responsable qualité sur la note, procédure de maîtrise de la conception des études (§ 8.3), fiches processus en Word dans `QUALITE\DOCUMENTS` ; installer `main` sur `test` ; `python manage.py migrate` sur la base de dev (migration `referentiel/0006`) ; créer `ADMINISTRATIF\LOGOS` et son `PIED.png` ; AV07, AV09 (ADR 0016), AV03, AV10 (attend C4), collecte (702 pièces, 35 références, points des 30 experts).

**Bloqué :** les parcours navigateur ne tournent plus sur ce poste : le Chromium de Playwright manque depuis sa mise à jour (`playwright install chromium`, un téléchargement à faire avec l'accord du porteur) ; en attendant, Edge sert (`channel="msedge"`). Écrans jamais vus depuis un poste du domaine (Kerberos) ; ce poste n'est pas dans le domaine et `test` n'y est pas joignable.

**À ne pas refaire :** écrire dans les documents qualité les noms d'outils techniques (Kerberos, Django, PostgreSQL) ou le mot « stagiaire » : le porteur les veut neutres, sauf la section « Contraintes techniques » de la fiche de mission ; présenter un service en ligne (Dropbox) comme interdit sans que ce soit décidé ; exporter un document claude.ai lourd en PDF par le connecteur (refusé au-delà de quelques centaines de Ko : refaire la page en HTML et l'imprimer avec Edge) ; donner à une personne deux rôles dont l'un contrôle l'autre sans le noter (le responsable qualité est audité par Allassane Maïga) ; et ce qui figure dans la note du 28/10 : « regroupement » = groupement d'entreprises, migrer la base de dev depuis une worktree, `2>&1` sur les scripts PowerShell.

**Décisions de la session :** SAE léger, pas de certification d'archivage ; plan d'archivage et politique rédigés comme des documents qualité — décision du porteur, 01/11 et 04/11. Stockage en ligne chiffré pour la sauvegarde hors site (ADR 0018, à accepter) — décision du porteur, 01/11. Rôles : Dicko gérant, Ibrahim Bouba directeur technique, Allassane Maïga RAF, O. Hassane offres et archives (suppléant Nasser Sidibé), Ousmane numérisation, Idrissa Maïga pilote du contrôle de travaux, Kane pilote de la clôture et vérificateur des études, le porteur responsable qualité et administrateur du serveur — décision du porteur, 04/11. Pas de VPS — proposée par l'assistant, acceptée le 01/11.

**Hypothèses de l'assistant, à valider :** durées de conservation « proposé » et « à confirmer » du plan d'archivage (10 ans comptables OHADA, 10 ans des dossiers de mission) ; dossiers `QUALITE\DOCUMENTS` et `QUALITE\ENREGISTREMENTS` ; version officielle des documents qualité en Word ou PDF signé dans `QUALITE\DOCUMENTS`.

**Décisions à prendre :** ADR 0018 et son fournisseur ; les six questions du § 9 du plan d'archivage ; les six points du § 8 de la politique qualité ; ADR 0016 ; doublons du classeur, montants PIGO, points des experts, pièces exigées par défaut, GIC-Prod.
