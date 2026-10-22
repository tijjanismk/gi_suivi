"""Administration de secours : le travail courant se fait dans les écrans (registre, dépôt,
types). Aucune suppression : une version se retire avec un motif, un type se désactive."""

from django.contrib import admin
from unfold.admin import ModelAdmin

from administratif.models import DemandeRenouvellement, PieceAdministrative, TypePiece


class SansSuppression:
    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(TypePiece)
class TypePieceAdmin(SansSuppression, ModelAdmin):
    list_display = ["code", "libelle", "regle_validite", "duree_mois", "rappel_jours", "actif"]
    list_filter = ["regle_validite", "exigee_par_defaut", "actif"]
    search_fields = ["code", "libelle", "organisme"]


@admin.register(PieceAdministrative)
class PieceAdministrativeAdmin(SansSuppression, ModelAdmin):
    list_display = ["type", "date_emission", "valide_jusqu_au", "chemin", "retiree"]
    list_filter = ["type", "retiree"]
    search_fields = ["chemin", "numero", "empreinte"]
    readonly_fields = ["empreinte", "taille", "nb_pages", "deposee_par", "deposee_le"]
    list_select_related = ["type"]

    def has_add_permission(self, request) -> bool:
        return False  # une version se dépose par l'écran, qui lit le fichier et son empreinte


@admin.register(DemandeRenouvellement)
class DemandeRenouvellementAdmin(SansSuppression, ModelAdmin):
    list_display = ["type", "demandee_le", "aupres_de", "relance_prevue_le", "close_le"]
    list_filter = ["type"]
    list_select_related = ["type"]
