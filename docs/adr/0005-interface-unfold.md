# ADR 0005 — Interface : thème Unfold pour l'administration et les écrans direction

- **Statut** : appliqué sur la branche `dev/T01-interface-moderne`, à valider par le développeur
- **Date** : 2026-10-07
- **Complète** : ADR 0002 (huit écrans Django + HTMX, SVG serveur)

## Contexte

L'administration Django brute et le gabarit minimal du socle (S02) ont été jugés
« pas modernes » par le porteur. Le plan prévoit huit écrans direction (T01 à
T09) ; les écrire et les maintenir avec une feuille de style maison, pour un
développeur seul, coûte plus qu'il ne rapporte. Contraintes conservées :
**aucune ressource chargée depuis Internet** (postes sur un réseau fermé),
interface en français, mobile d'abord, impression propre.

## Décision

1. **`django-unfold`** (MIT, version figée `~=0.108.0`) habille l'administration
   et sert de gabarit aux écrans direction : menu latéral par usage, palette
   (bleu GI-CONSEILS), cartes et composants, mode sombre. Les écrans T02 à T09
   s'écrivent dans ses mises en page (`unfold/layouts/*`) et composants
   (`unfold/components/*`), pas dans l'admin lui-même quand ce n'est pas un
   écran de gestion.
2. **Tout est servi localement** : CSS, HTMX, Alpine, polices Inter et icônes
   Material viennent du paquet, via `collectstatic`. Vérifié le 07/10/2026 :
   aucun appel réseau au chargement.
3. **Le français est à nous** : Unfold n'a pas de catalogue français ;
   `locale/fr/LC_MESSAGES/django.po` traduit les textes du thème (74 entrées au
   départ), compilé par `scripts/dev/compiler_traductions.py` (Python pur, pas
   de GNU gettext sous Windows). `.mo` versionné : le serveur n'a pas gettext
   non plus. `scripts/dev/chaines_unfold.py` liste les textes à revoir quand
   Unfold change de version.
4. **CSS propre au projet, si besoin, avec l'outil Tailwind** autonome
   (`tailwindcss-windows-x64.exe`, sur le poste de développement seulement,
   dans `C:\dev\outils\tailwind`, hors dépôt). Il produit un fichier CSS
   versionné ; le serveur ne compile rien. Pas d'outillage Node.

## Conséquences

Positives : des écrans cohérents sans feuille de style maison ; l'admin de
gestion (racines, paramètres, exceptions, dossiers) est tout de suite
présentable ; les composants servent aux huit écrans.

Négatives, assumées :

- Dépendance à un paquet jeune, qui casse parfois entre versions mineures :
  version figée, mise à jour délibérée avec relecture des gabarits surchargés
  (`interface/templates/admin/index.html`) et du catalogue français.
- Les traductions du thème sont à notre charge à chaque montée de version.
- Le CSS d'Unfold est précompilé : une classe Tailwind absente de ses gabarits
  n'existe pas tant qu'on n'a pas compilé notre propre CSS (point 4).
- L'outil Tailwind n'est pas signé Authenticode (c'est le cas de l'éditeur) :
  il reste sur le poste de développement, jamais sur le serveur ni les postes.

## Ce qui ne change pas

Règles de `CONTEXT.md` : identité par IIS (pas de page de connexion — celle
d'Unfold est remplacée par une page de refus), `moteur/` sans Django, graphiques
en SVG rendu côté serveur (Unfold fournit des composants « chart » ; on les
évalue à T02, le SVG serveur reste la référence).
