# Sources de la veille

Reprises du skill d'origine « veille-ami-gi-conseils » le 09/11/2026. Une adresse qui change
s'écrit ici, pas dans la conversation.

## 1. Banque mondiale – API des avis de passation

Noms de pays exacts (`project_ctry_name_exact`) : Mali, Niger, Burkina Faso, Senegal, Cote d'Ivoire, Guinea, Benin, Togo, Mauritania, Cameroon, Gabon, Guinea-Bissau. Vérifier que `project_ctry_name` correspond dans la réponse.

**Liste courte (≈ 200 caractères, passe la limite WebFetch)** – sans `format=json` (XML, lisible) :
```
https://search.worldbank.org/api/v2/procnotices?rows=30&srt=noticedate&order=desc&project_ctry_name_exact=<Pays>&notice_type_exact=Request%20for%20Expression%20of%20Interest&fl=id,bid_description,noticedate,submission_deadline_date
```
Pour « Burkina%20Faso », « Cote%20d'Ivoire », « Mauritania », « Cameroon », retirer `,project_ctry_name` du `fl` (sinon l'URL dépasse la limite). Ajouter `&l=3`, `&l=5`… pour forcer une relecture hors cache.

**Détail d'un avis (texte complet, critères, dépôt)** :
```
https://search.worldbank.org/api/v2/procnotices?format=json&id=<id>&fl=id,bid_description,project_name,submission_deadline_date,submission_deadline_time,procurement_method_code,contact_organization,contact_email,notice_text
```
Fiche publique : `https://projects.worldbank.org/en/projects-operations/procurement-detail/<id>` (lien à passer en `source_url`).

Depuis une page de projects.worldbank.org, l'API est appelable en JavaScript (fetch) pour traiter les 12 pays d'un coup – uniquement si le navigateur intégré est disponible.

Le champ `contact_organization` / `contact_email` des métadonnées est parfois celui d'un autre projet : privilégier les coordonnées du `notice_text` et signaler l'incohérence.

## 2. BAD – avis de passation

Liste pays française :
```
https://www.afdb.org/fr/projects-and-operations/procurement?title=&tid=<id>&tid_1=All&page=0
```
tid : Mali 350, Niger 360, Burkina Faso 359, Sénégal 340, Côte d'Ivoire 342, Guinée 368, Bénin 328, Togo 331, Mauritanie 335, Cameroun 341, Gabon 367, Guinée-Bissau 383.

Liste globale anglaise : `https://www.afdb.org/en/projects-and-operations/procurement?page=0` (puis page=1 à 5, ≈ 18 avis par page). Attention : la variante avec barre oblique finale et sans paramètre (`…/procurement/`) renvoie une page en cache de février 2020, inexploitable.

Recherche par projet : `…/procurement?title=<acronyme>&tid=<id>&tid_1=All&page=0`.

Projets à interroger au minimum (priorité 1) :
- Niger : PASEPAR-MR, PIDZPT, PASEPA, PREPAAR, PIDACC, P2-P2RS, PARTTM, Kandadji
- Mali : PIDACC, PAAEPAR, PARCB, PBNB
- Burkina Faso : PASEPA-2R, PHEPA, P2-P2RS, PIRCOFAT, PAVAL, PURPA, CU2a, PEPA-MR
Compléter avec les acronymes rencontrés dans les lectures.

Page d'un avis : `https://www.afdb.org/fr/documents/<slug>` ; l'URL directe du PDF est dans le paramètre `file=` du lecteur pdf.js ; WebFetch lit les PDF (20 premières pages).

## 3. Mali – DGMP
`https://www.dgmp.gouv.ml/?q=node/66` (tableau des AMI ; fichiers .docx/.pdf). Le 09/11/2026 l'URL redirigeait en 302 vers `https://centif.ml/?q=node%2F66` (site de la CENTIF, sans tableau) : si cela se reproduit, signaler la source comme non accessible.

## 4. Niger – ARCOP
- Liste des HCOP : `https://www.arcop.ne/documents/hcop` ; PDF : `https://www.arcop.ne/documents/download/<n>` (n°553 = 238, n°552 = 237, n°551 = 236 ; +1 par semaine en général). Les AMI sont en début de numéro, les décisions du CRD à la fin ; le sommaire donne la pagination.
- Appels à candidatures de l'ARCOP elle-même : `https://www.arcop.ne/commande-publique/avis-appels-offres` (PDF via `commande-publique/download/<n>`).

## 5. Burkina Faso – DGCMEF
`https://www.dgcmef.gov.bf/fr/appels-d-offre` liste les Quotidiens de la Revue des marchés publics ; PDF en `http://www.dgcmef.gov.bf/sites/default/files/<AAAA-MM>/Quotidien%20n%C2%B0<numéro>.pdf` (le « n » est tantôt minuscule, tantôt majuscule, parfois suivi d'une espace). Rubrique « Prestations intellectuelles » généralement en pages 35-45 : hors de portée de WebFetch → couverture incomplète à déclarer. Archives : `https://www.dgcmef.gov.bf/index%2Ephp/fr/revue-de-march-s-pour-tous`.

## 6. Autres régulateurs (état observé le 09/11/2026)
| Pays | URL | État |
|---|---|---|
| Mauritanie | https://www.armp.mr/avis, https://www.armp.mr/annonces | /avis n'affiche que des décisions CRD ; /annonces vide (contenu dynamique) |
| Sénégal | http://www.marchespublics.sn | robots_disallowed |
| Côte d'Ivoire | https://www.anrmp.ci → https://arcop.ci/ ; https://arcop.ci/documentation/avis/avis-a-manifestation-dinteret/ | seulement les AMI de l'ARCOP elle-même (anciens) |
| Bénin | https://armp.bj ; https://armp.bj/category/documentation/avis/ | avis réglementaires de l'ARMP (PDF sans texte), pas d'AMI des autorités contractantes |
| Cameroun | https://www.armp.cm/filtres?type=avis&val=12 (+ `&page=2`) ; fiche : https://www.armp.cm/details?type_publication=AMI&id_publication=<id> | lisible et productif (10 AMI par page, avec date limite) |
| Guinée | https://www.armp.gov.gn | robots_disallowed |
| Togo | https://armp.tg | robots_disallowed |
| Gabon | https://www.armp.ga → renvoie vers http://www.lejmp.ga/avis-liste | pas de liste sur le site ARMP |
