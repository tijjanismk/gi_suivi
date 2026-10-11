from django.urls import path

from suivi.vues import a_classer, direction, export, gestion, journee, taches

app_name = "suivi"
urlpatterns = [
    path("journee/", journee.journee, name="journee"),
    path("journee/<int:employe_id>/", journee.journee_personne, name="journee_personne"),
    path("export.xlsx", export.classeur, name="export_excel"),
    path("a-classer/", a_classer.a_classer, name="a_classer"),
    path("a-classer/rattacher", a_classer.rattacher_groupe, name="a_classer_rattacher"),
    path("gestion-dossiers/", gestion.gestion_dossiers, name="gestion_dossiers"),
    path("gestion-dossiers/<int:dossier_id>/valider", gestion.valider, name="gestion_valider"),
    path("gestion-dossiers/<int:dossier_id>/modifier", gestion.modifier, name="gestion_modifier"),
    path("taches/", taches.taches, name="taches"),
    path("taches/creer", taches.creer, name="taches_creer"),
    path("taches/<int:tache_id>/modifier", taches.modifier, name="taches_modifier"),
    path("", direction.vue_ensemble, name="vue_ensemble"),
    path("dossiers/", direction.dossiers, name="dossiers"),
    path("personnes/", direction.employes, name="employes"),
    path("personnes/<int:employe_id>/", direction.employe, name="employe"),
    path("postes/", direction.postes, name="postes"),
]
