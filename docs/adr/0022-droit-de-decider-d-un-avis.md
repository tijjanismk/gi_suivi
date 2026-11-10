# ADR 0022 — Droit de décider de répondre à un avis : la direction ou sa délégation

- **Statut** : accepté par le porteur le 06/11/2026 (proposé le 05/11/2026)
- **Date** : 2026-11-05
- **Décideur** : le porteur
- **Complète** : ADR 0006 et 0007 (droits par les groupes AD), ADR 0021

## Contexte

Le porteur a décidé le 05/11/2026 que seule la direction, ou la personne à qui elle délègue,
décide de répondre ou non à un avis. Aujourd'hui, `GI-Direction` et `GI-Offres` modifient un
avis, statut compris. Les droits viennent des groupes AD, lus par l'application (ADR 0006) :
pas de comptes ni de rôles maison (règle 7 de `CONTEXT.md`). Sur `AD-SERVEUR`, rien d'existant
ne se modifie ; créer un groupe est un ajout.

## Options

| | A. Groupe AD de délégation | B. Délégation saisie dans l'application | C. Tout `GI-Offres` |
|---|---|---|---|
| Apprentissage | nul : comme les autres groupes | un écran et une table de plus | nul |
| Exploitation | ajouter ou retirer une personne du groupe dans l'AD | saisir chaque délégation, avec ses dates | nulle |
| Maturité | le mécanisme de tous les droits | à écrire | existe |
| Agent de code | un réglage, un test | modèle, écran, règles de dates | rien |
| Plus gros risque | la délégation n'est ni datée ni motivée hors de l'AD | des droits tenus en dehors de l'AD | contraire au choix du porteur |

## Décision

Un groupe AD `GI-Decision-Avis` (réglage `GROUPE_DECISION_AVIS`) pour la délégation : ses
membres décident comme la direction, et chaque décision note la qualité de son auteur
(« direction » ou « délégation »). Les membres du groupe consultent les avis ; ils ne reçoivent
aucun autre droit. Le groupe est à créer dans l'AD par le porteur ; tant qu'il est vide, seule la
direction décide.

## Justification

- Tous les droits de l'application passent déjà par l'AD : une délégation de plus se donne et se
  retire au même endroit, par la même personne.
- La qualité notée sur chaque décision suffit à l'audit pour savoir qu'elle a été prise par
  délégation.
- Une délégation saisie dans l'application (B) crée des droits hors de l'AD, ce que la règle 7
  écarte.

## Conséquences

Positives :

- Aucun écran nouveau ; la délégation suit la personne, pas un poste.

Négatives, assumées :

- L'acte de délégation (qui délègue, depuis quand, jusqu'à quand) n'est pas dans l'application :
  il reste à écrire dans le système qualité (fiche de fonction ou note de délégation signée).
- Retirer quelqu'un du groupe ne retire rien aux décisions qu'il a déjà prises : c'est voulu.

## Contre-argument conservé

Une délégation datée et motivée dans l'application (B) serait la preuve la plus complète pour
l'audit, sans document à part.

**Reconsidérer cette décision si** : l'auditeur exige la délégation datée dans l'outil, ou les
délégations deviennent temporaires et fréquentes (absences, intérims).
