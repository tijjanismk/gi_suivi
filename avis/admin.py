"""Administration des avis en attendant leurs écrans (AV03) : un avis avec ses critères et ses
pièces exigées. Aucune suppression d'un avis : il passe « sans suite »."""

from django import forms
from django.contrib import admin
from unfold.admin import ModelAdmin, StackedInline, TabularInline

from avis.formulaires import FormulaireAvis, StatutSansDecision
from avis.models import Avis, BesoinExpert, Critere, DecisionAvis, PieceExigee, Selection


class SansSuppression:
    def has_delete_permission(self, request, obj=None) -> bool:
        return False


class CritereEnLigne(StackedInline):
    model = Critere
    extra = 0


class PieceExigeeEnLigne(TabularInline):
    model = PieceExigee
    extra = 0


class LectureSeule:
    """Une décision se prend depuis la fiche de l'avis et ne se modifie jamais (ADR 0021)."""

    def has_add_permission(self, request, obj=None) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


class DecisionEnLigne(LectureSeule, TabularInline):
    model = DecisionAvis
    extra = 0
    fields = ["le", "decision", "par", "qualite", "motif", "note_sure", "note_possible"]
    readonly_fields = fields


class FormulaireAvisAdmin(StatutSansDecision, forms.ModelForm):
    class Meta:
        model = Avis
        fields = FormulaireAvis.Meta.fields  # les champs modifiables de l'avis, comme avant


@admin.register(Avis)
class AvisAdmin(SansSuppression, ModelAdmin):
    form = FormulaireAvisAdmin
    list_display = ["reference", "type", "objet_court", "date_limite", "statut"]
    list_filter = ["type", "statut"]
    search_fields = ["reference", "objet"]
    readonly_fields = [
        "note_sure",
        "note_possible",
        "simulee_le",
        "cree_par",
        "cree_le",
    ]

    @admin.display(description="objet")
    def objet_court(self, obj: Avis) -> str:
        return obj.objet[:80]

    def get_inlines(self, request, obj):
        # Les pièces exigées par défaut sont reprises à la création ; on les complète ensuite
        return [CritereEnLigne, PieceExigeeEnLigne, DecisionEnLigne] if obj else [CritereEnLigne]

    def save_model(self, request, obj, form, change) -> None:
        if not change:
            obj.cree_par = request.user
        super().save_model(request, obj, form, change)


@admin.register(DecisionAvis)
class DecisionAvisAdmin(LectureSeule, ModelAdmin):
    list_display = ["le", "avis", "decision", "par", "qualite", "note_sure", "note_possible"]
    list_filter = ["decision", "qualite"]
    search_fields = ["avis__reference", "motif"]
    list_select_related = ["avis", "par"]


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
