"""Administration des avis en attendant leurs écrans (AV03) : un avis avec ses critères et ses
pièces exigées. Aucune suppression d'un avis : il passe « sans suite »."""

from django.contrib import admin
from unfold.admin import ModelAdmin, StackedInline, TabularInline

from avis.models import Avis, BesoinExpert, Critere, PieceExigee, Selection


class SansSuppression:
    def has_delete_permission(self, request, obj=None) -> bool:
        return False


class CritereEnLigne(StackedInline):
    model = Critere
    extra = 0


class PieceExigeeEnLigne(TabularInline):
    model = PieceExigee
    extra = 0


@admin.register(Avis)
class AvisAdmin(SansSuppression, ModelAdmin):
    list_display = ["reference", "type", "objet_court", "date_limite", "statut"]
    list_filter = ["type", "statut"]
    search_fields = ["reference", "objet"]
    readonly_fields = [
        "note_sure",
        "note_possible",
        "simulee_le",
        "decision_par",
        "decision_le",
        "cree_par",
        "cree_le",
    ]

    @admin.display(description="objet")
    def objet_court(self, obj: Avis) -> str:
        return obj.objet[:80]

    def get_inlines(self, request, obj):
        # Les pièces exigées par défaut sont reprises à la création ; on les complète ensuite
        return [CritereEnLigne, PieceExigeeEnLigne] if obj else [CritereEnLigne]

    def save_model(self, request, obj, form, change) -> None:
        if not change:
            obj.cree_par = request.user
        super().save_model(request, obj, form, change)


@admin.register(Selection)
class SelectionAdmin(SansSuppression, ModelAdmin):
    list_display = ["critere", "mission", "rang", "preuve", "points", "retenue"]
    list_filter = ["preuve", "retenue"]
    search_fields = ["mission__code", "critere__avis__reference"]
    list_select_related = ["critere", "mission"]

    def has_add_permission(self, request) -> bool:
        return False  # la sélection vient de la simulation (AV04)


@admin.register(BesoinExpert)
class BesoinExpertAdmin(ModelAdmin):
    list_display = ["avis", "poste", "niveau_min", "annees_experience_min", "expert_retenu"]
    search_fields = ["poste", "avis__reference"]
    list_select_related = ["avis", "expert_retenu"]
