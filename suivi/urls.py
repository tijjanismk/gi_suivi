from django.urls import path

from suivi.vues import direction, gestion

app_name = "suivi"
urlpatterns = [
    path("gestion-dossiers/", gestion.gestion_dossiers, name="gestion_dossiers"),
    path("gestion-dossiers/<int:dossier_id>/valider", gestion.valider, name="gestion_valider"),
    path("gestion-dossiers/<int:dossier_id>/modifier", gestion.modifier, name="gestion_modifier"),
    path("", direction.vue_ensemble, name="vue_ensemble"),
    path("dossiers/", direction.dossiers, name="dossiers"),
    path("personnes/", direction.employes, name="employes"),
    path("personnes/<int:employe_id>/", direction.employe, name="employe"),
]
