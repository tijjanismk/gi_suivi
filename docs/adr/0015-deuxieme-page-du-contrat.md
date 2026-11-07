# ADR 0015 — La deuxième page du contrat, quatrième justificatif exceptionnel

- **Statut** : accepté par le porteur le 27/10/2026 ; **remplacé en partie par l'ADR 0020** le 07/11/2026 (la pièce est la page des adresses des parties, pas la deuxième page ; on la repère pour tous les contrats)
- **Date** : 2026-10-27
- **Décideur** : le porteur, sur proposition de l'assistant
- **Remplace** : —
- **Complète** : ADR 0011 (justificatifs), ADR 0013 § 3 (pièces requises par un critère)

## Contexte

Une référence se prouve par trois pièces : la page de garde, la page de signature et
l'attestation de bonne exécution (ADR 0011). Le porteur a signalé le 27/10/2026 que certains
avis demandent, exceptionnellement, une quatrième pièce : la deuxième page du contrat (objet,
montant, durée). Ni le modèle ni le moteur ne la connaissaient, et le chantier 3 ne l'a pas
découpée.

## Décision

- Un type de justificatif de plus, `deuxieme_page` (« deuxième page du contrat ») ; le fichier
  normalisé est `DEUXIEME-PAGE.pdf` dans `REFERENCES\02_JUSTIFICATIFS\<code>\` (« 2e page » est
  aussi reconnu dans un nom de fichier). Migration `references/0003_piece_deuxieme_page`.
- Une référence reste **complète** avec ses trois pièces : la deuxième page n'entre pas dans
  `TYPES_ESSENTIELS`, ni dans les compteurs de la liste des références.
- Un critère d'avis peut l'exiger : `pieces_requises` accepte `deuxieme_page`, et l'écran du
  critère propose « les trois pièces et la 2e page du contrat ». Le moteur la traite comme les
  autres (prouvée, à auditer, manquante) et la classe dans les pièces en jeu.
- On ne la cherche pas pour toutes les références : seulement pour celles qu'un avis qui
  l'exige retient, d'après les pièces en jeu de sa simulation.

## Justification

- La demande est rare : en faire une quatrième pièce obligatoire rendrait incomplètes les 217
  références qui ont aujourd'hui leurs trois pièces.
- Le filtre du critère porte déjà la liste des pièces requises (ADR 0013) : l'exception se dit
  avis par avis, sans code nouveau dans le moteur.

## Conséquences

Positives :

- Un avis qui exige la deuxième page montre tout de suite les références qui ne l'ont pas, avec
  les points qu'elles portent.

Négatives, assumées :

- Les deuxièmes pages se rangent au fil des avis, pas en une campagne : la première fois, la
  recherche se fait sous la pression de la date limite.

## Contre-argument conservé

Découper les deuxièmes pages de toutes les références en une fois (les contrats complets sont
déjà sur le partage) éviterait de les chercher avant un dépôt.

**Reconsidérer cette décision si** : les avis qui l'exigent deviennent fréquents ; un bailleur
en fait une règle générale.
