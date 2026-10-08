from django.urls import path

from suivi.vues import direction

app_name = "suivi"
urlpatterns = [
    path("", direction.vue_ensemble, name="vue_ensemble"),
]
