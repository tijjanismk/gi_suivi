"""Administration de secours : le travail courant se fait dans les écrans (liste, fiche,
doublons). Aucune suppression : une fiche en double est absorbée, jamais effacée."""

from django.contrib import admin
from unfold.admin import ModelAdmin

from references.models import DecisionDoublon, Mission, PieceJustificative, Quantite, Reclamation


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
    filter_horizontal = ["domaines_secondaires", "types_ouvrage", "livrables"]
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


@admin.register(PieceJustificative)
class PieceJustificativeAdmin(ModelAdmin):
    list_display = ["mission", "type", "nature_exacte", "lisible", "coherente", "chemin"]
    list_filter = ["type", "lisible", "coherente"]
    search_fields = ["mission__code", "chemin"]
    readonly_fields = ["empreinte", "taille", "nb_pages", "rattachee_par", "rattachee_le"]

    def has_add_permission(self, request) -> bool:
        return False  # un justificatif se rattache par l'écran, qui lit le fichier et son empreinte


@admin.register(Reclamation)
class ReclamationAdmin(ModelAdmin):
    list_display = ["mission", "type", "etat", "le", "contact_client"]
    list_filter = ["etat", "type"]
    search_fields = ["mission__code", "contact_client"]


@admin.register(Quantite)
class QuantiteAdmin(ModelAdmin):
    list_display = ["mission", "type", "valeur", "source"]
    list_filter = ["type"]
    search_fields = ["mission__code"]
