from django.urls import path

from avis.vues import ecrans

app_name = "avis"
urlpatterns = [
    path("", ecrans.liste, name="liste"),
    path("nouveau", ecrans.modifier, name="nouveau"),
    path("<int:avis_id>/", ecrans.fiche, name="fiche"),
    path("<int:avis_id>/modifier", ecrans.modifier, name="modifier"),
    path("<int:avis_id>/fichier/<str:quoi>", ecrans.fichier, name="fichier"),
    path("<int:avis_id>/pieces", ecrans.pieces, name="pieces"),
    path("<int:avis_id>/critere", ecrans.critere, name="critere_nouveau"),
    path("<int:avis_id>/critere/<int:critere_id>", ecrans.critere, name="critere"),
    path(
        "<int:avis_id>/critere/<int:critere_id>/retirer",
        ecrans.retirer_critere,
        name="retirer_critere",
    ),
]
