from django.contrib import admin

from suivi.models import (
    Dossier,
    Employe,
    JournalAcces,
    Parametre,
    Poste,
    Racine,
    RegleException,
    Segment,
)


@admin.register(Racine)
class RacineAdmin(admin.ModelAdmin):
    list_display = ["chemin", "profondeur", "motif_code", "active"]
    list_editable = ["active"]


@admin.register(Parametre)
class ParametreAdmin(admin.ModelAdmin):
    list_display = ["cle", "valeur", "description"]
    search_fields = ["cle"]


class RegleExceptionEnLigne(admin.TabularInline):
    model = RegleException
    extra = 0
    readonly_fields = ["cree_par", "cree_le"]


@admin.register(RegleException)
class RegleExceptionAdmin(admin.ModelAdmin):
    list_display = ["motif", "type", "dossier", "cree_par", "cree_le"]
    list_filter = ["type"]
    search_fields = ["motif", "dossier__code", "dossier__nom"]
    readonly_fields = ["cree_par", "cree_le"]

    def save_model(self, request, obj, form, change) -> None:
        if not change:
            obj.cree_par = request.user
        super().save_model(request, obj, form, change)


@admin.register(Dossier)
class DossierAdmin(admin.ModelAdmin):
    list_display = ["code", "nom", "statut", "valide", "racine"]
    list_filter = ["statut", "valide", "racine"]
    search_fields = ["code", "nom", "chemin_windows"]
    readonly_fields = ["valide_par", "valide_le"]
    inlines = [RegleExceptionEnLigne]


@admin.register(Employe)
class EmployeAdmin(admin.ModelAdmin):
    list_display = ["nom_affiche", "login", "heures_prevues_semaine", "actif"]
    list_filter = ["actif"]
    search_fields = ["nom_affiche", "login"]
    readonly_fields = ["sid_ad"]


@admin.register(Poste)
class PosteAdmin(admin.ModelAdmin):
    list_display = ["nom", "version_agent", "dernier_envoi", "demarrages_semaine"]
    readonly_fields = ["nom", "version_agent", "dernier_envoi", "demarrages_semaine", "premier_vu"]

    def has_add_permission(self, request) -> bool:
        return False  # un poste naît de son premier lot (POST /api/segments)


@admin.register(Segment)
class SegmentAdmin(admin.ModelAdmin):
    """Consultation seulement : les segments bruts ne se corrigent pas à la main."""

    list_display = [
        "debut",
        "employe",
        "application",
        "fichier",
        "duree_s",
        "statut_classement",
        "dossier",
    ]
    list_filter = ["statut_classement", "etat"]
    date_hierarchy = "debut"
    list_select_related = ["employe", "dossier"]

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False


@admin.register(JournalAcces)
class JournalAccesAdmin(admin.ModelAdmin):
    list_display = ["horodatage", "login", "action", "cible", "adresse_ip"]
    list_filter = ["action"]

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
