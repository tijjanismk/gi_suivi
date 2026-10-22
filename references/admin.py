"""Administration de secours : le travail courant se fait dans les écrans (liste, fiche,
doublons). Aucune suppression : une fiche en double est absorbée, jamais effacée."""

from django.contrib import admin
from unfold.admin import ModelAdmin

from references.models import DecisionDoublon, Mission


@admin.register(Mission)
class MissionAdmin(ModelAdmin):
    list_display = [
        "code",
        "intitule_court",
        "domaine",
        "nature",
        "client",
        "annee",
        "statut_verification",
    ]
    list_filter = ["domaine", "nature", "statut_verification", "statut_code"]
    search_fields = ["code", "intitule", "intitule_court", "client__nom", "numero_contrat"]
    list_select_related = ["domaine", "client"]
    filter_horizontal = ["domaines_secondaires"]
    readonly_fields = ["cree_le", "modifie_le"]

    def get_readonly_fields(self, request, obj=None):
        # ADR 0008 : le code est attribué une fois, jamais modifié
        return [*self.readonly_fields, "code", "absorbee_par"] if obj else self.readonly_fields

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(DecisionDoublon)
class DecisionDoublonAdmin(ModelAdmin):
    list_display = ["le", "mission_a", "mission_b", "meme_contrat", "gardee", "par"]
    list_filter = ["meme_contrat"]

    def has_add_permission(self, request) -> bool:
        return False  # une décision se prend dans l'écran « Doublons à arbitrer »

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
