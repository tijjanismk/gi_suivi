# ADR 0017 — Retrait du développement rural : cinq domaines

- **Statut** : accepté par le porteur le 30/10/2026
- **Date** : 2026-10-30
- **Décideur** : le porteur
- **Remplace** : ADR 0014 § 2 (le développement rural en domaine secondaire)
- **Complète** : ADR 0014 § 1 (domaines de la présentation)

## Contexte

L'ADR 0014 a fait des six domaines de la présentation du bureau ceux de l'application, dont le
développement rural (RUR), nouveau, sans série de codes, prévu en domaine secondaire des
références qui le recoupent (pistes, hydraulique villageoise, aménagements, bâtiments ruraux).
Le 30/10/2026, le porteur a décidé de retirer le développement rural des références : il en
reste cinq. Au même jour, sur `test`, RUR ne porte aucune référence (ni en principal ni en
secondaire), aucun expert, aucun critère d'avis, et aucune référence n'est rangée dans un de ses
sous-domaines.

## Décision

- Cinq domaines : AEP, RTE, HYD, BAT, ENV, aux libellés de l'ADR 0014.
- RUR et ses sept sous-domaines (pistes rurales, infrastructures hydro-agricoles,
  infrastructures d'élevage, points d'eau, hydraulique villageoise et pastorale, énergie,
  équipements socio-collectifs) sont **supprimés, sans être reportés** dans un autre domaine
  (choix du porteur). Les types d'ouvrages SHVA et SHPA restent : ce sont des ouvrages, pas des
  domaines.
- Migration `referentiel/0006_retrait_developpement_rural`. Comme pour VRD (ADR 0014), le
  domaine reste tant qu'une référence, un expert ou une catégorie de référence le porte.
- La liste des références à marquer RUR (ADR 0014 § 2) n'est plus à faire.

## Justification

- Le domaine ne servait à rien encore : le retirer maintenant ne coûte ni recodage ni
  reprise de données ; plus tard, il aurait fallu défaire des marques de domaine secondaire.
- Le développement rural recoupe les autres domaines : un avis qui le vise se décrit par leurs
  sous-domaines (pistes : RTE ; hydraulique villageoise : AEP ; aménagements : HYD).

## Conséquences

Positives :

- Le référentiel colle aux domaines que le bureau revendique dans ses références.

Négatives, assumées :

- Un avis de développement rural se filtre par plusieurs domaines au lieu d'un.

## Contre-argument conservé

Répartir les sous-domaines de RUR dans les autres domaines (pistes rurales sous RTE, points
d'eau sous AEP…) aurait gardé ces libellés de la présentation pour classer les références.

**Reconsidérer cette décision si** : la présentation du bureau garde le développement rural et
un avis le note comme domaine à part entière.
