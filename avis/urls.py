from django.urls import path

from avis.vues import ecrans

app_name = "avis"
urlpatterns = [
    path("", ecrans.liste, name="liste"),
    path("nouveau", ecrans.modifier, name="nouveau"),
    path("propositions/", ecrans.propositions, name="propositions"),
    path("propositions/<int:proposition_id>", ecrans.proposition, name="proposition"),
    path("logo", ecrans.logo, name="logo"),
    path("<int:avis_id>/", ecrans.fiche, name="fiche"),
    path("<int:avis_id>/modifier", ecrans.modifier, name="modifier"),
    path("<int:avis_id>/fichier/<str:quoi>", ecrans.fichier, name="fichier"),
    path("<int:avis_id>/dossier", ecrans.dossier, name="dossier"),
    path("<int:avis_id>/intercalaires", ecrans.intercalaires, name="intercalaires"),
    path("<int:avis_id>/pieces", ecrans.pieces, name="pieces"),
    path("<int:avis_id>/simulation", ecrans.simulation, name="simulation"),
    path(
        "<int:avis_id>/simulation/enregistrer",
        ecrans.enregistrer_simulation,
        name="enregistrer_simulation",
    ),
    path("<int:avis_id>/simulation/choix", ecrans.choix, name="choix"),
    path("<int:avis_id>/besoin", ecrans.besoin, name="besoin_nouveau"),
    path("<int:avis_id>/besoin/<int:besoin_id>", ecrans.besoin, name="besoin"),
    path("<int:avis_id>/besoin/<int:besoin_id>/retenir", ecrans.retenir, name="retenir"),
    path(
        "<int:avis_id>/besoin/<int:besoin_id>/retirer",
        ecrans.retirer_besoin,
        name="retirer_besoin",
    ),
    path("<int:avis_id>/critere", ecrans.critere, name="critere_nouveau"),
    path("<int:avis_id>/critere/<int:critere_id>", ecrans.critere, name="critere"),
    path(
        "<int:avis_id>/critere/<int:critere_id>/retirer",
        ecrans.retirer_critere,
        name="retirer_critere",
    ),
]
