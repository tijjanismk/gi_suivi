from django.urls import path

from suivi.vues import direction

app_name = "suivi"
urlpatterns = [
    path("", direction.vue_ensemble, name="vue_ensemble"),
    path("dossiers/", direction.dossiers, name="dossiers"),
    path("personnes/", direction.employes, name="employes"),
    path("personnes/<int:employe_id>/", direction.employe, name="employe"),
]
