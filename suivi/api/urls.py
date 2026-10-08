from django.urls import path

from suivi.api.moi import moi_aujourdhui, racines
from suivi.api.segments import recevoir_segments

app_name = "api"
urlpatterns = [
    path("segments", recevoir_segments, name="segments"),
    path("moi/aujourdhui", moi_aujourdhui, name="moi_aujourdhui"),
    path("racines", racines, name="racines"),
]
