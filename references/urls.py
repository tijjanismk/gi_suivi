from django.urls import path

from references.vues import ecrans

app_name = "references"
urlpatterns = [
    path("", ecrans.liste, name="liste"),
    path("doublons/", ecrans.doublons, name="doublons"),
    path("doublons/trancher", ecrans.trancher, name="trancher"),
    path("<str:code>/", ecrans.fiche, name="fiche"),
]
