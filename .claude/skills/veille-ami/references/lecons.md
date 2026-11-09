# Leçons des exécutions passées

Chaque point ci-dessous a coûté du temps ou failli faire manquer un AMI. Les relire avant de commencer.

## Données périmées : pourquoi trois lectures
- **16/10/2026** – trois AMI urgents du Niger (PASEPAR-MR ×2, PIDZPT, datés des 05 et 08/10) figuraient sur la liste globale anglaise de la BAD à 8h05 mais pas sur la liste pays française tid=360 à 8h20 (402 avis) ; ils n'y sont apparus que l'après-midi (405 avis).
- **09/11/2026** – la première lecture de l'API Banque mondiale (08:15) a été servie par une réplique périmée : totaux inférieurs de 1 à 25 avis selon le pays, et aucun avis postérieur au 28/10 pour le Mali, le Niger, le Burkina et le Sénégal. La relecture avec `&l=3` à 08:50 a fait apparaître quatre AMI de pertinence forte (contrôle de périmètres irrigués PATA-BF Dionkélé 2 000 ha et Samendéni 3 760 ha ; EIES/PAR des OME du PISEN ×2), dont un fermant le lendemain. Toujours comparer les totaux et le premier id entre lectures ; tout écart est à ouvrir.

## Accès aux sites
- **BAD** : six requêtes simultanées sur la rubrique « procurement » ont déclenché un blocage (erreur client 4xx) de toute la rubrique et des pages de documents pendant plus de 45 minutes, FR et EN, avec ou sans paramètres ; seuls la page d'accueil et `/fr/documents` sans paramètre répondaient encore. Espacer les requêtes (lots ≤ 6, quelques secondes entre les lots) et, en cas de blocage, réessayer une requête isolée toutes les 6-10 minutes sans insister davantage.
- **WebFetch** refuse une URL de plus d'environ 240 caractères ; raccourcir les gabarits (voir sources.md) plutôt que d'abandonner la source.
- **WebFetch** ne restitue que les 20 premières pages d'un PDF, et `offset` ne permet pas d'aller au-delà. Le shell n'a pas d'accès Internet (proxy 403) : impossible de télécharger le PDF autrement. Conséquence : la rubrique « Prestations intellectuelles » des quotidiens du Burkina reste illisible → couverture incomplète à déclarer, pas « rien au Burkina ».
- **WebFetch** refuse de refaire une URL qui vient d'échouer ; changer un paramètre inoffensif (`&l=2`, `&l=3`…) relance vraiment la requête.
- **DGMP Mali** peut rediriger vers un autre site (centif.ml le 09/11/2026) : suivre la redirection une fois pour le constater, puis déclarer la source non accessible.
- Les ARMP du Sénégal, du Togo et de la Guinée interdisent la lecture (robots) ; celle de Mauritanie charge ses listes en JavaScript ; celles de Côte d'Ivoire, du Bénin et du Gabon ne listent pas les AMI des autorités contractantes. Les consigner tel quel, sans les retenter indéfiniment.
- La veille ne tourne pas dans le cloud ni depuis le serveur : l'outil `creer_proposition` ne
  répond que sur un poste du domaine où le pont MCP est installé.

## Lecture des avis
- Les métadonnées de l'API Banque mondiale (heure limite, contact, organisation) divergent parfois du `notice_text` (ex. : 12/11 vs 13/11 ; contact d'un autre projet). Retenir la date la plus prudente et signaler l'incohérence dans Observations.
- Le titre d'un avis BM dit « consultant » même quand le texte vise des cabinets : lire le `notice_text` avant d'écarter pour « consultant individuel ».
- La BAD affiche la date de l'avis, pas celle de sa mise en ligne : un avis daté d'il y a 10 jours peut être apparu hier ; la date limite se lit dans le PDF.
- Au Niger, les HCOP contiennent surtout des décisions du CRD et des plans prévisionnels ; les vrais AMI ouverts sont peu nombreux et en début de numéro. Les décisions CRD renseignent utilement sur les restrictions (ex. : cabinets d'architecture exclus du suivi-contrôle de bâtiments par le projet Niger-LIRE).
- Au Cameroun (armp.cm), les AMI « suivi-contrôle HIMO » du PADFA II visent des consultants individuels ; les AMI MINTP/CPR-FC sur projets BAD visent des firmes.

## Propositions (VE01, VE02)
- « Nouveau » = absent de l'application : `creer_proposition` répond `deja_connu` pour un avis
  déjà là (avis ou proposition, même rejetée). Un avis ancien vu seulement à une relecture
  est quand même proposé : le dire dans le compte rendu, la veille précédente a pu le manquer.
- Ni Excel ni e-mail (décision du porteur, 09/11/2026) : le compte rendu reste dans la
  conversation, les avis arrivent sur l'écran « Propositions ».

## Exécution du 09/11/2026 (première veille vers l'application)
- **Navigateur intégré** : l'API Banque mondiale se lit en `fetch` depuis une page de
  projects.worldbank.org (12 pays en un appel) ; les listes BAD se lisent en `fetch` +
  `DOMParser` depuis une page d'afdb.org (même origine), lots de 6 à 15 requêtes espacées de
  2 s : aucun blocage.
- **PDF de la BAD** : WebFetch reçoit 403 sur `sites/default/files/...pdf`. Les lire depuis le
  lecteur du site (`/sites/all/libraries/pdf.js/web/viewer.html?file=...`) : `fetch` du PDF
  en `Uint8Array`, puis `PDFViewerApplication.open(octets)` et `getTextContent()` page par
  page (`open(url)` échoue : « Réponse inattendue du serveur »).
- **HCOP du Niger** : lisibles en entier avec pdf.js chargé depuis cdnjs (`import()` du
  module) sur une page d'arcop.ne ; le n°554 (09-15/11) n'avait aucun AMI de bureau d'études
  dans ses appels à concurrence.
- **DGMP Mali** : `?q=node/66` affiche toujours la CENTIF ; **DGCMEF Burkina** : aucun
  quotidien depuis le n°4514 du 21/10/2026.
- **Avis déjà traités hors de l'application** (PATA-BF, PISEN, décision du porteur du
  07/11) : ne pas en faire des propositions ; les citer dans le compte rendu.
