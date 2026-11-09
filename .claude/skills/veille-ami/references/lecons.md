# Leçons des exécutions passées

Un piège par ligne, daté, avec ce qu'il faut faire. Ajouter les nouveaux à la fin.

- **16/10/2026** : trois AMI urgents du Niger n'étaient que sur la liste globale BAD, absents des
  listes par pays. Toujours faire la lecture 2 (liste globale).
- **09/11/2026** : quatre AMI forts (Burkina, Niger) n'apparaissaient qu'à la deuxième lecture de
  l'API Banque mondiale (réplique périmée). Toujours relire avec un autre suffixe `&l=`.
- **BAD** : après une rafale de 6 requêtes simultanées, toute la rubrique « procurement » a
  répondu en erreur 4xx pendant plus de 45 minutes. Lots de 6 au plus, avec une pause.
- **WebFetch** : refuse les URL de plus de 240 caractères environ, garde une URL 15 minutes en
  cache, ne rend que les 20 premières pages d'un PDF (`offset` n'y change rien).
- **Burkina** : la rubrique « Prestations intellectuelles » du quotidien est souvent après la
  page 20 (page 39 observée). Si elle n'est pas lue, écrire « couverture incomplète du Burkina »,
  jamais « rien au Burkina ».
- **Mali** : le site de la DGMP a déjà redirigé ailleurs (centif.ml). Le signaler, comme une
  absence de publication depuis 15 jours.
- **Niger** : un HCOP scanné sans texte est « non lisible », pas « sans AMI ».
- **Shell** : pas d'accès Internet direct (proxy, DNS) ; ne pas contourner WebFetch avec curl ou
  Python.
