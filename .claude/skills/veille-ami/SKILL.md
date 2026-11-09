---
name: veille-ami
description: Veille des avis à manifestation d'intérêt (AMI / REOI / SMI) pour GI-Conseils (bureau d'études malien : eau et assainissement, routes et pistes, aménagements hydroagricoles, bâtiments, environnement EIES/PGES/PAR) sur 12 pays d'Afrique de l'Ouest et du Centre, à partir de l'API Banque mondiale, des listes BAD, de la DGMP Mali, de l'ARCOP Niger, de la DGCMEF Burkina et des ARMP nationales. Chaque AMI retenu arrive dans l'application gi_suivi comme une proposition d'avis à valider (outil MCP creer_proposition, origine « veille ») ; ni Excel ni e-mail. Utiliser ce skill dès que l'on parle de veille AMI, d'avis de manifestation d'intérêt à trouver, de sourcing d'opportunités Banque mondiale ou BAD, de l'HCOP Niger, de la revue des marchés publics du Burkina ou de la DGMP Mali, même sans le mot « veille », et pour toute exécution planifiée de la veille.
---

# Veille des AMI (VE01)

La veille trouve les AMI ouverts et les fait **arriver dans l'application** : une proposition
d'avis par AMI retenu, à valider par une personne du bureau sur l'écran « Propositions »
(`/avis/propositions/`). C'est la règle 3 de `CONTEXT.md` : la veille ne crée jamais un avis.
**Pas d'Excel, pas d'e-mail** : recevoir les avis dans l'application suffit (décision du porteur,
09/11/2026).

Exécution souvent planifiée, sans personne devant l'écran : faire des choix raisonnables, les
écrire, et toujours finir, même quand une source est en panne. Répondre en français.

## 0. Avant de commencer

- L'outil MCP `creer_proposition` (serveur gi-conseils, pont du poste, `docs/outils-mcp.md`) doit
  être là. **Sans lui, s'arrêter** et le dire : la veille ne sert à rien hors de l'application.
  Il ne répond que sur un poste du domaine où le pont est installé, jamais depuis le cloud ni
  depuis le serveur (Kerberos).
- Lire `references/sources.md` (adresses, gabarits, états observés) et `references/lecons.md`
  (pièges déjà rencontrés).
- Pas de WebSearch dans l'organisation : WebFetch, et le navigateur intégré s'il est là.

## 1. Périmètre

**Domaines** : eau et assainissement (AEP, forages, châteaux d'eau, drainage) ; transport
(routes, pistes rurales, voirie, ouvrages) ; aménagements hydroagricoles (périmètres irrigués,
micro-barrages, périmètres et jardins maraîchers, bas-fonds, mares) ; bâtiments civils et
industriels (écoles, centres de santé, marchés, bâtiments administratifs) ; environnement (EIES,
NIES, PGES, mise en œuvre de PAR, audits E&S).
**Prestations** : études (faisabilité, APS, APD, DAO), maîtrise d'œuvre, contrôle et surveillance
de travaux, assistance à maîtrise d'ouvrage.

**Pays** : priorité 1 Mali, Burkina Faso, Niger ; priorité 2 Sénégal, Côte d'Ivoire, Guinée,
Bénin, Togo, Mauritanie, Guinée-Bissau ; priorité 3 Gabon, Cameroun.

**Retenir** les avis ouverts à des bureaux d'études dont la date limite est aujourd'hui ou plus
tard. **Ne pas proposer** : consultants individuels, audits comptables ou financiers,
informatique, énergie pure, répertoires de fournisseurs (sauf « études et contrôle »), missions
hors domaine (planification budgétaire, communication, formation, foncier…). Les citer seulement
dans le compte rendu final, avec le motif.

**Pertinence** : forte = cœur de métier (contrôle de périmètres irrigués, EIES ou PAR d'ouvrages
hydrauliques, contrôle de routes, d'AEP ou de bâtiments) ; moyenne = accessible en groupement
(aménagement du territoire, diagnostic territorial, plans d'occupation des sols…).

## 2. Règle des trois lectures

Les listes BAD et l'API Banque mondiale servent parfois des copies périmées : une lecture unique
ne prouve rien (le 16/10/2026, trois AMI du Niger n'étaient que sur la liste globale BAD ; le
09/11/2026, quatre AMI forts n'apparaissaient qu'à la deuxième lecture de l'API).

1. **Lecture 1, canal pays** (noter l'heure) : API Banque mondiale des 12 pays (total, premier
   avis, date limite ≥ aujourd'hui) ; listes BAD françaises des 12 pays (page 0, plus page 1 pour
   Mali, Niger, Burkina). Lots de 6 requêtes au plus, quelques secondes entre les lots.
2. **Sources nationales** : DGMP Mali, HCOP et avis de l'ARCOP Niger, quotidiens DGCMEF Burkina
   (rubrique « Prestations intellectuelles »), autres ARMP (voir `references/sources.md`).
3. **Lecture 2, canal global et projets** : liste globale anglaise BAD pages 0 à 5 ; recherche
   par acronyme de projet pour les pays de priorité 1 ; API Banque mondiale relue avec `&l=3`.
4. **Lecture 3**, au moins 16 minutes après la lecture 1 : listes BAD avec `&l=3`, API Banque
   mondiale avec `&l=5`. Tout écart est ouvert et traité.

BAD inaccessible : réessayer une requête isolée toutes les 6 à 10 minutes (varier `&l=`) jusqu'à
45 minutes environ, puis finir avec « couverture BAD nulle ce jour ». Une source lue une seule
fois ou en partie est une limite de couverture, jamais une absence d'AMI.

## 3. Qualifier et proposer

Pour chaque AMI retenu, lire le texte lui-même (`notice_text` de la Banque mondiale, PDF de la BAD
ou de la source nationale) ; une proposition sans document lu n'est pas faite. Puis appeler :

```
creer_proposition(
    champs={
        "reference": "…", "objet": "…", "type": "AMI",
        "pays": "Niger", "maitre_ouvrage": "…", "bailleur": "Banque mondiale",
        "date_limite": "12/11/2026", "heure_limite": "16:00",
        "date_publication": "…", "methode_selection": "SFQC",
        "lieu_depot": "adresse physique", "courriel_depot": "…",
        "observations": "pertinence forte : … ; critères : … ; éligibilité : … ; source : …",
    },
    source_url="lien de l'avis lu",
    origine="veille",
)
```

- Écrire la référence telle qu'elle est dans l'avis. Date limite : la plus prudente quand les
  métadonnées et le texte diffèrent, et le dire dans `observations`.
- `observations` porte ce que la personne qui valide doit voir d'un coup : pertinence et pourquoi,
  critères de présélection chiffrés (missions similaires, ancienneté, agrément), restrictions
  d'éligibilité (ouvert au national, agrément exigé, groupement imposé ou interdit), contact,
  incohérences relevées.
- Une réponse `deja_connu` veut dire que l'avis est déjà dans l'application (avis ou proposition,
  même rejetée) : ne rien refaire. `forcer=True` seulement si l'objet montre un autre avis sous la
  même référence.
- Un nom de maître d'ouvrage ou de bailleur absent du référentiel n'est pas une erreur : il est
  noté dans les observations de l'avis à la validation.

## 4. Compte rendu final

À la fin, un compte rendu court dans la conversation (pas de fichier, pas d'e-mail) :

- propositions créées (pays, référence, date limite, pertinence), la plus urgente en premier ;
- avis déjà connus revus ;
- avis écartés et motif ;
- sources non accessibles et limites de couverture ;
- « 3 lectures BAD / Banque mondiale à HH:MM, HH:MM et HH:MM ».

Ajouter les pièges nouveaux à `references/lecons.md` et les changements d'adresse à
`references/sources.md`, par une branche et une PR comme le reste du dépôt.
