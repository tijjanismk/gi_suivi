# Sources de la veille

État au 09/11/2026. Les gabarits exacts (URL de l'API, identifiants `tid` des pays BAD,
acronymes des projets actifs) sont à reprendre du skill d'origine « veille-ami-gi-conseils »
et à compléter ici à chaque exécution : une adresse qui change s'écrit ici, pas dans la
conversation.

## Banque mondiale

- API des avis de passation (JSON) : un appel par pays, `total` et identifiant du premier avis
  notés à chaque lecture ; garder `submission_deadline_date` ≥ aujourd'hui.
- Détail d'un avis : `?format=json&id=<id>&fl=…notice_text`.
- Relectures avec un suffixe différent (`&l=3`, puis `&l=5`) pour passer le cache.
- Gabarit court : _à reprendre_.

## BAD

- Listes françaises par pays : `tid=<id>&page=0` (page 1 aussi pour Mali, Niger, Burkina) ; noter
  « Displaying 1 - 18 of N ». Identifiants `tid` : _à reprendre_.
- Liste globale anglaise, pages 0 à 5.
- Recherche par projet : `title=<acronyme>&tid=<id>`. Projets actifs des pays de priorité 1 :
  _à reprendre, puis compléter avec les acronymes rencontrés_.
- La date affichée est celle de l'avis, pas de sa mise en ligne : lire la date limite dans le PDF
  (paramètre `file=` du lecteur pdf.js de la page).

## Sources nationales

| Pays | Source | Ce qu'on y lit |
|---|---|---|
| Mali | DGMP, tableau `?q=node/66` | .docx et .pdf récents pour la date limite |
| Niger | ARCOP : liste des HCOP (`documents/download/<n>`) et avis d'appels à candidatures | « manifestation d'intérêt », « bureau d'études », « contrôle et surveillance » |
| Burkina Faso | DGCMEF, quotidiens des marchés publics | rubrique « Prestations intellectuelles » |
| Cameroun | armp.cm, pages 1 et 2 | en général lisible et productif |
| Mauritanie, Sénégal, Côte d'Ivoire, Bénin, Guinée, Togo, Gabon | ARMP nationales | essayer, noter l'état (robots refusés, contenu dynamique vide, pas de liste) |
