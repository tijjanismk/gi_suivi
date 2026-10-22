from django.contrib import admin
from unfold.admin import ModelAdmin

from referentiel.models import (
    Bailleur,
    Categorie,
    Client,
    Domaine,
    Livrable,
    TypeOuvrage,
    TypeQuantite,
)


@admin.register(Domaine)
class DomaineAdmin(ModelAdmin):
    list_display = ["code", "libelle", "ordre"]

    def has_delete_permission(self, request, obj=None) -> bool:
        return False  # un domaine nomme des codes de référence immuables


@admin.register(Categorie)
class CategorieAdmin(ModelAdmin):
    list_display = ["libelle", "domaine", "cle"]
    list_filter = ["domaine"]
    search_fields = ["libelle", "cle"]


@admin.register(Client)
class ClientAdmin(ModelAdmin):
    list_display = ["nom", "sigle", "type", "pays"]
    list_filter = ["type"]
    search_fields = ["nom", "sigle"]


@admin.register(Bailleur)
class BailleurAdmin(ModelAdmin):
    list_display = ["nom", "sigle"]
    search_fields = ["nom", "sigle"]


@admin.register(TypeOuvrage)
class TypeOuvrageAdmin(ModelAdmin):
    list_display = ["libelle", "famille", "cle", "ordre", "actif"]
    list_filter = ["famille", "actif"]
    search_fields = ["libelle", "cle", "famille"]


@admin.register(Livrable)
class LivrableAdmin(ModelAdmin):
    list_display = ["libelle", "cle", "ordre"]


@admin.register(TypeQuantite)
class TypeQuantiteAdmin(ModelAdmin):
    list_display = ["libelle", "unite", "cle", "ordre"]
