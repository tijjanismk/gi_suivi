from django.urls import path

from experts.vues import ecrans

app_name = "experts"
urlpatterns = [
    path("", ecrans.vivier, name="vivier"),
    path("nouveau", ecrans.modifier, name="nouveau"),
    path("affecter", ecrans.affecter, name="affecter"),
    path(
        "affectation/<int:affectation_id>/retirer",
        ecrans.retirer_affectation,
        name="retirer_affectation",
    ),
    path("<int:expert_id>/", ecrans.fiche, name="fiche"),
    path("<int:expert_id>/modifier", ecrans.modifier, name="modifier"),
    path("<int:expert_id>/diplome", ecrans.ajouter_diplome, name="diplome"),
    path("<int:expert_id>/experience", ecrans.ajouter_experience, name="experience"),
    path("<str:quoi>/<int:element_id>/retirer", ecrans.retirer_element, name="retirer"),
]
