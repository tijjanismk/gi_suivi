from django.urls import path
from django.views.generic import RedirectView

app_name = "avis"
urlpatterns = [
    # Les écrans viennent avec AV03 ; d'ici là, la liste est celle de l'administration
    path("", RedirectView.as_view(pattern_name="admin:avis_avis_changelist"), name="liste"),
]
