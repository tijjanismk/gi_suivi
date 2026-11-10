# ADR 0021 — Historique des décisions « on répond ou pas » d'un avis

- **Statut** : accepté par le porteur le 05/11/2026 (choix de l'historique)
- **Date** : 2026-11-05
- **Décideur** : le porteur
- **Complète** : ADR 0013 (application `avis`) ; tâche AV12
- **Numéro** : 0018 à 0020 sont pris (sauvegarde hors site, vocabulaire des ouvrages par pays,
  page des adresses du contrat) ; rédigé le 05/11 sous le numéro 0019, renuméroté au report sur `main`

## Contexte

L'ISO 9001 (§ 8.2.3) demande de revoir les exigences d'un client avant de s'engager et de garder
la trace de cette revue. Pour un avis, la revue aboutit au passage du statut à « on répond »
(`go`) ou « on ne répond pas » (`no_go`). Aujourd'hui, seul le statut change : rien ne dit qui a
décidé, quand, pourquoi, ni sur quelle note.

L'avis porte depuis AV02 trois champs `decision_par`, `decision_le` et `motif_decision`
(migration `avis/0001_avis`). Aucun écran ne les remplit : les deux premiers sont en lecture
seule dans l'administration, le motif n'y est que modifiable à la main. Une décision peut être
revue (« on répond », puis « on ne répond pas » après lecture des TDR) ; le porteur veut garder
toutes les décisions, pas seulement la dernière (05/11/2026).

## Options

| | A. Trois champs sur l'avis | B. Table des décisions | C. Journal des accès |
|---|---|---|---|
| Apprentissage | nul | faible : un modèle, une migration | nul |
| Exploitation | nulle | nulle | nulle |
| Maturité | celle de Django | celle de Django | existe (`suivi.JournalAcces`) |
| Agent de code | trivial | simple | simple |
| Plus gros risque | une décision revue efface la précédente : la preuve disparaît | deux vérités si les trois champs restent | ni motif ni note ; mêlé aux consultations |

## Décision

Une table `avis.DecisionAvis` : une ligne par décision, jamais modifiée ni supprimée.

- Champs : `avis`, `decision` (`go` ou `no_go`), `motif` (obligatoire), `par`, `qualite`
  (direction ou délégation, ADR 0022), `le`, `statut_avant`, et la note de la dernière
  simulation à ce moment (`note_sure`, `note_possible`, `simulee_le`), vide s'il n'y en a pas.
- Le statut ne passe à `go` ou `no_go` que par une décision : le formulaire de l'avis et
  l'administration le refusent.
- On décide depuis « reçu », « en analyse », « on répond » ou « on ne répond pas » ; pas après
  le dépôt. Une décision identique au statut en cours est refusée.
- Les trois champs de l'avis sont retirés (migration `avis/0006_historique_des_decisions`). Un
  `motif_decision` non vide est recopié dans les observations de l'avis : on ne fabrique pas une
  décision dont on ne connaît ni l'auteur ni la date.

Aucune dépendance nouvelle.

## Justification

- La preuve demandée par l'ISO est la décision elle-même, avec son motif : la perdre au premier
  changement d'avis (option A) la rend fausse.
- Une ligne par décision suit la règle « un modèle, une responsabilité » ; l'avis garde son
  statut, la table garde le pourquoi.
- La note figée montre sur quoi on a décidé, même si la note bouge ensuite (attestations
  auditées, critères corrigés).
- Le journal des accès sert à savoir qui a vu quoi ; il ne porte ni motif ni note.

## Conséquences

Positives :

- Sur la fiche de l'avis, la décision en cours et les précédentes, avec qui, quand, pourquoi.
- Le passage à « on répond » n'a plus qu'un chemin, qui exige un motif.

Négatives, assumées :

- Une table de plus, et deux écrans (formulaire, administration) qui refusent désormais un
  statut qu'ils acceptaient.
- Revenir à « en analyse » par le formulaire reste possible : la décision précédente demeure dans
  l'historique, sans ligne qui dise qu'on l'a rouverte.

## Contre-argument conservé

Les trois champs existaient déjà : les remplir aurait suffi pour un premier audit, sans
migration de structure.

**Reconsidérer cette décision si** : l'audit demande une trace de chaque changement de statut
(dépôt, résultat), auquel cas un historique des statuts remplacerait celui des seules décisions.
