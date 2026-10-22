from django.urls import path

from administratif.vues import controle, depot, registre, types

app_name = "administratif"
urlpatterns = [
    path("", registre.registre, name="registre"),
    path("deposer", depot.deposer, name="deposer"),
    path("controle", controle.controle, name="controle"),
    path("types/", types.types, name="types"),
    path("types/ajouter", types.modifier_type, name="type_ajouter"),
    path("types/<str:code>/modifier", types.modifier_type, name="type_modifier"),
    path("version/<int:version_id>/fichier", registre.fichier, name="fichier"),
    path("version/<int:version_id>/retirer", registre.retirer, name="retirer"),
    path("<str:code>/", registre.fiche, name="fiche"),
    path("<str:code>/demande", registre.noter_demande, name="demande"),
]
