from django.urls import path

from suivi.api import rapports
from suivi.api.moi import moi_aujourdhui, racines
from suivi.api.segments import recevoir_segments

app_name = "api"
urlpatterns = [
    # agents et toute personne authentifiée
    path("segments", recevoir_segments, name="segments"),
    path("moi/aujourdhui", moi_aujourdhui, name="moi_aujourdhui"),
    path("racines", racines, name="racines"),
    # direction et consultation seule
    path("rapports/synthese", rapports.synthese, name="rapport_synthese"),
    path("rapports/dossiers", rapports.dossiers, name="rapport_dossiers"),
    path("employes/<int:employe_id>/activite", rapports.activite_employe, name="employe_activite"),
    path("dossiers", rapports.liste_dossiers, name="dossiers"),
    path("aclasser", rapports.a_classer, name="aclasser"),
    path("postes/etat", rapports.etat_postes, name="postes_etat"),
]
