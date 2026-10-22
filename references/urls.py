from django.urls import path

from references.vues import ecrans, pieces, saisie

app_name = "references"
urlpatterns = [
    path("", ecrans.liste, name="liste"),
    path("doublons/", ecrans.doublons, name="doublons"),
    path("doublons/trancher", ecrans.trancher, name="trancher"),
    path("nouvelle", saisie.nouvelle, name="nouvelle"),
    path("<str:code>/modifier", saisie.modifier, name="modifier"),
    path("<str:code>/justificatifs", pieces.justificatifs, name="justificatifs"),
    path("<str:code>/justificatifs/rattacher", pieces.rattacher, name="rattacher"),
    path("<str:code>/justificatifs/reclamer", pieces.reclamer, name="reclamer"),
    path("<str:code>/ouvrages", pieces.ouvrages, name="ouvrages"),
    path("piece/<int:piece_id>/auditer", pieces.auditer, name="auditer"),
    path("piece/<int:piece_id>/detacher", pieces.detacher, name="detacher"),
    path("piece/<int:piece_id>/fichier", pieces.fichier, name="fichier_justificatif"),
    path("<str:code>/", ecrans.fiche, name="fiche"),
]
