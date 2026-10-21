from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from suivi.models import (
    Dossier,
    Employe,
    JournalAcces,
    Parametre,
    Racine,
    RegleException,
    Tache,
)
from suivi.services import recalculer, valider_dossier


@admin.register(Racine)
class RacineAdmin(ModelAdmin):
    list_display = ["chemin", "profondeur", "motif_code", "active"]
    list_editable = ["active"]


@admin.register(Parametre)
class ParametreAdmin(ModelAdmin):
    list_display = ["cle", "valeur", "description"]
    search_fields = ["cle"]


class RegleExceptionEnLigne(TabularInline):
    model = RegleException
    extra = 0
    readonly_fields = ["cree_par", "cree_le"]


@admin.register(RegleException)
class RegleExceptionAdmin(ModelAdmin):
    list_display = ["motif", "type", "dossier", "cree_par", "cree_le"]
    list_filter = ["type"]
    search_fields = ["motif", "dossier__code", "dossier__nom"]
    readonly_fields = ["cree_par", "cree_le"]

    def save_model(self, request, obj, form, change) -> None:
        if not change:
            obj.cree_par = request.user
        super().save_model(request, obj, form, change)
        # Effet immédiat pour la direction : les segments concernés sont rattachés tout de suite
        r = recalculer()
        self.message_user(
            request, f"Exception enregistrée ; {r['modifies']} segment(s) reclassé(s)."
        )


@admin.register(Dossier)
class DossierAdmin(ModelAdmin):
    list_display = ["code", "nom", "statut", "valide", "racine"]
    list_filter = ["statut", "valide", "racine"]
    search_fields = ["code", "nom", "chemin_windows"]
    readonly_fields = ["valide_par", "valide_le"]
    inlines = [RegleExceptionEnLigne]
    actions = ["valider"]

    @admin.action(description="Valider les dossiers sélectionnés", permissions=["change"])
    def valider(self, request, queryset) -> None:
        n = 0
        for dossier in queryset.filter(valide=False):
            valider_dossier(dossier, request.user)
            n += 1
        self.message_user(request, f"{n} dossier(s) validé(s) ; recalcul demandé.")


# Pas de page pour Poste, Segment ni DemandeRecalcul (retirées le 21/10/2026) : l'écran
# « État des postes » montre les postes, les écrans Journée, Personnes et « À classer » montrent
# les segments, et la file de recalcul se vide seule (tâche planifiée suivi_recalculer).


@admin.register(Employe)
class EmployeAdmin(ModelAdmin):
    list_display = ["nom_affiche", "login", "heures_prevues_semaine", "actif"]
    list_filter = ["actif"]
    search_fields = ["nom_affiche", "login"]
    readonly_fields = ["sid_ad"]


@admin.register(Tache)
class TacheAdmin(ModelAdmin):
    """Correction ponctuelle (titre, fichiers, personne) ; le suivi courant se fait dans l'écran
    Tâches."""

    list_display = ["titre", "dossier", "personne", "echeance", "etat", "creee_le"]
    list_filter = ["etat", "personne"]
    search_fields = ["titre", "dossier__code", "dossier__nom", "fichiers"]
    readonly_fields = ["creee_par", "creee_le", "faite_le", "modifiee_le"]
    list_select_related = ["dossier", "personne"]


@admin.register(JournalAcces)
class JournalAccesAdmin(ModelAdmin):
    list_display = ["horodatage", "login", "action", "cible", "adresse_ip"]
    list_filter = ["action"]

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
