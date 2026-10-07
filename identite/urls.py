from django.urls import path

from identite.vues import qui_suis_je

app_name = "identite"
urlpatterns = [path("qui-suis-je", qui_suis_je, name="qui_suis_je")]
