# ADR 0020 — La page des adresses du contrat, à la place de la « deuxième page »

- **Statut** : accepté par le porteur le 07/11/2026
- **Date** : 2026-11-07
- **Décideur** : le porteur, sur proposition de l'assistant
- **Remplace** : ADR 0015 (la deuxième page du contrat), en partie : la pièce reste exceptionnelle,
  son sens, son nom et sa recherche changent
- **Complète** : ADR 0008 (une référence = un contrat), ADR 0011 (justificatifs), ADR 0013 § 3
  (pièces requises par un critère)

## Contexte

L'ADR 0015 a ajouté une quatrième pièce, exceptionnelle : « la deuxième page du contrat (objet,
montant, durée) ». Le porteur a précisé le 07/11/2026 que les avis qui la demandent veulent en
fait **la page où figurent les adresses des parties** (le client et le consultant), et que, sur
certains contrats, ces adresses sont déjà sur la première page. C'est l'une des raisons pour
lesquelles les contrats complets ont été scannés (lots du gérant, 30/10 au 05/11).

Lecture des 155 contrats complets rangés dans `REFERENCES\02_JUSTIFICATIFS` (OCR des pages 1 à 4,
classement vérifié à l'œil sur des exemples de chaque cas, 07/11/2026 ; résultat dans
`C:\GIC\Claude outputs\Contrats\Page des adresses\Ou sont les adresses dans les contrats
(07-11-2026).csv`) :

| Où sont les adresses des deux parties | Contrats |
|---|---|
| Page 1, la page de garde (préambule « entre… d'une part… d'autre part », ou bloc « Passé entre » / « Les parties ») | 56 (36 %) |
| Page 2 (préambule) | 65 (42 %) |
| Page 3 | 16 (10 %) |
| Page 4 | 5 (3 %) |
| Nulle part : les parties sont nommées sans adresse (Kidal), ou le client n'est que « représenté par » et l'adresse du bureau est dans l'acte d'engagement (IPRO-IRRIGAR Sikasso) | 13 (8 %) |

Dans 32 contrats, la garde porte l'adresse du bureau seule : celle du client est plus loin. Les
108 autres références n'ont pas de contrat complet scanné ; leur garde dira ce qu'elle dira.

Trois constats en découlent :

1. Ce n'est pas « la deuxième page » : c'est la page des adresses, en page 1, 2, 3 ou 4 selon le
   contrat.
2. Pour un tiers des contrats, la page de garde **est** la page des adresses. La copier sous un
   autre nom est interdit (un contenu = un exemplaire dans `D:\GIC`, décision du 21/10) et
   impossible (l'empreinte d'une pièce est unique dans la base).
3. Pour une référence sur douze, aucune page ne porte les deux adresses : un avis qui l'exige ne
   doit pas la marquer « manquante » à chaque fois, comme si on avait oublié de la chercher.

## Décision

1. **La pièce s'appelle « page des adresses du contrat »** : la page où figurent les adresses du
   client et du consultant, quel que soit son numéro. Valeur `page_adresses` (au lieu de
   `deuxieme_page`) ; fichier normalisé `ADRESSES.pdf` dans `REFERENCES\02_JUSTIFICATIFS\<code>\`
   ; `DEUXIEME-PAGE`, « 2e page » et « adresses » restent reconnus dans un nom de fichier.
   Migration de données nommée : les pièces et les filtres de critère (`pieces_requises`) qui
   portent `deuxieme_page` passent à `page_adresses` (aucune pièce n'en a au 07/11 : 0 fichier
   `DEUXIEME-PAGE.pdf` sur le partage).
2. **Un champ sur la référence** (`references.Mission`), `adresses_contrat`, parce que c'est une
   propriété du contrat (ADR 0008) et non d'un fichier :
   - `garde` : les adresses des deux parties sont sur la page de garde ;
   - `page` : elles sont sur une page à part, rangée comme `ADRESSES.pdf` ;
   - `absentes` : le contrat ne donne pas les deux adresses ;
   - vide : pas encore regardé.
   Migration nommée dans `references`. Le champ se modifie à l'écran de la référence et se
   journalise (qui, quand) comme les autres décisions sur les pièces.
3. **Le moteur** (`moteur/avis/filtres.py`, sans Django) reçoit `adresses_contrat` dans
   `Reference`. Pour un critère qui exige `page_adresses` :
   - `garde` : la pièce est prouvée, à auditer ou manquante **comme la garde** ;
   - `page` : comme la pièce `ADRESSES.pdf` ;
   - `absentes` : manquante, avec le motif « le contrat ne donne pas les adresses » (affiché tel
     quel, pour qu'on ne la cherche pas) ;
   - vide : manquante, motif « page des adresses à repérer ».
4. **La complétude ne change pas** : une référence reste complète avec sa garde, sa signature et
   son attestation (ADR 0011, `TYPES_ESSENTIELS`) ; la page des adresses n'entre pas dans les
   compteurs.
5. **Le dossier AMI** (AV14, `moteur/avis/sommaire.py`) : pour un avis qui l'exige, l'ordre des
   pièces d'une référence devient garde → page des adresses → signature → attestation ; si
   `adresses_contrat` vaut `garde`, rien n'est inséré et le « Ci-jointe » reste celui de la garde
   ; si elle est à part, le « Ci-jointe » cite « page des adresses ».
6. **On les repère tous maintenant, pas avis par avis** (ce qui renverse l'ADR 0015 et retient son
   contre-argument) :
   - le classement du 07/11 donne, pour chacun des 155 contrats, `garde`, la page à découper ou
     `absentes` ; il est **revu à l'œil** avant usage (une liste à valider par le porteur, règle 3
     de CONTEXT.md) ;
   - les 86 pages à part sont découpées des `CONTRAT_COMPLET.pdf` par
     `scripts\exploitation\Decouper-PDF.ps1`, rangées en `ADRESSES.pdf`, journalisées dans
     `decoupages.csv` ;
   - le champ est rempli par un import qui ne touche que lui (pas l'import complet du registre,
     qui écraserait les corrections faites à l'écran) ;
   - pour les 108 références sans contrat complet, on regarde la garde : `garde` si elle porte
     les deux adresses, sinon vide jusqu'au scan du contrat.

## Justification

- Le mot « deuxième page » a déjà trompé : il ferait découper la mauvaise page dans plus d'un
  contrat sur deux.
- Le champ sur la référence évite tout fichier en double et dit, en un mot, pourquoi une pièce
  n'est pas rangée (`garde`, `absentes`) : la recherche ne se refait pas sous la pression d'un
  dépôt.
- Les contrats complets sont sur le partage : repérer une fois coûte moins que chercher à chaque
  avis, ce que l'ADR 0015 admettait déjà dans son contre-argument.

## Conséquences

Positives :

- Un avis qui exige la page des adresses montre tout de suite les références prêtes, celles dont
  le contrat est à scanner et celles dont le contrat n'a pas d'adresse.
- Le dossier AMI n'insère pas deux fois la même page.

Négatives, assumées :

- Deux migrations (le champ ; le renommage de `deuxieme_page`) et un import ciblé.
- 86 pages à découper et un classement à revoir à l'œil.
- `absentes` laisse la référence non prouvée pour ces avis : c'est vrai, et c'est au chef de
  dossier de décider s'il la présente quand même.

## Contre-argument conservé

Garder `deuxieme_page` et ne changer que le libellé éviterait une migration de données. Écarté :
aucune pièce ni aucun critère ne s'en sert encore, c'est le moment le moins cher pour corriger le
nom ; plus tard, il faudrait migrer des pièces réelles.

**Reconsidérer cette décision si** : un avis demande une autre page précise du contrat (objet,
montant) : on ajouterait alors un type, sans revenir sur celui-ci ; ou si les avis demandent le
contrat entier (on joindrait `CONTRAT_COMPLET.pdf`).
