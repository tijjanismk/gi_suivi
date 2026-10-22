from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from config.vues import sante
from identite.vues import refus_admin
from suivi.vues.moi import mon_activite
from suivi.vues.taches import ma_tache

# L'administration n'a pas de page de connexion : l'utilisateur vient d'IIS.
# Hors GI-Direction, l'admin renvoie vers cette vue, qui refuse au lieu de demander un mot de passe.
admin.site.login = refus_admin
admin.site.site_header = "GI-CONSEILS — administration"

urlpatterns = [
    # Accueil : la journée de chaque personne (demande du porteur, 08/10/2026)
    path("", RedirectView.as_view(pattern_name="suivi:journee", permanent=False)),
    path("suivi/", include("suivi.urls")),
    path("administratif/", include("administratif.urls")),  # pièces administratives (ADR 0010)
    path("sante/", sante, name="sante"),
    path("identite/", include("identite.urls")),
    path("api/", include("suivi.api.urls")),
    path("moi", mon_activite, name="moi"),  # l'icône de l'agent ouvre <url_api>/moi
    path("moi/taches/<int:tache_id>", ma_tache, name="ma_tache"),
    path("admin/", admin.site.urls),
]
