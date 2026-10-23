from django.contrib import admin
from unfold.admin import ModelAdmin

from experts.models import Affectation, Diplome, ExperienceExterne, Expert


@admin.register(Expert)
class ExpertAdmin(ModelAdmin):
    list_display = ["nom", "prenoms", "statut", "categorie", "specialite", "disponible"]
    list_filter = ["statut", "categorie", "disponible", "domaines"]
    search_fields = ["nom", "prenoms", "specialite", "fonction"]
    filter_horizontal = ["domaines"]


@admin.register(Affectation)
class AffectationAdmin(ModelAdmin):
    list_display = ["expert", "mission", "poste", "du", "au", "plein_temps"]
    search_fields = ["expert__nom", "mission__code", "poste"]
    list_select_related = ["expert", "mission"]


@admin.register(Diplome)
class DiplomeAdmin(ModelAdmin):
    list_display = ["expert", "intitule", "niveau", "annee"]
    search_fields = ["expert__nom", "intitule"]


@admin.register(ExperienceExterne)
class ExperienceExterneAdmin(ModelAdmin):
    list_display = ["expert", "employeur", "poste", "du", "au"]
    search_fields = ["expert__nom", "employeur"]
