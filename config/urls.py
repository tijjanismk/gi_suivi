from django.contrib import admin
from django.urls import include, path

from config.vues import sante
from identite.vues import refus_admin

# L'administration n'a pas de page de connexion : l'utilisateur vient d'IIS.
# Hors GI-Direction, l'admin renvoie vers cette vue, qui refuse au lieu de demander un mot de passe.
admin.site.login = refus_admin
admin.site.site_header = "GI-CONSEILS — administration"

urlpatterns = [
    path("sante/", sante, name="sante"),
    path("identite/", include("identite.urls")),
    path("api/", include("suivi.api.urls")),
    path("admin/", admin.site.urls),
]
