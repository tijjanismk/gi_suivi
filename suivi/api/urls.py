from django.urls import path

from suivi.api.segments import recevoir_segments

app_name = "api"
urlpatterns = [path("segments", recevoir_segments, name="segments")]
