from django import forms
from django.contrib import admin, messages
from django.utils import timezone
from unfold.admin import ModelAdmin

from referentiel import services
from referentiel.models import (
    Bailleur,
    Categorie,
    Client,
    Domaine,
    Livrable,
    Terme,
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


class TermeForm(forms.ModelForm):
    class Meta:
        model = Terme
        fields = [
            "type_ouvrage",
            "terme",
            "pays",
            "portee",
            "statut",
            "origine",
            "source_url",
            "nb_avis",
            "motif",
        ]

    def clean(self):
        donnees = super().clean()
        if donnees.get("statut") == Terme.Statut.REJETE and not donnees.get("motif", "").strip():
            raise forms.ValidationError("Indiquez le motif du rejet.")
        return donnees


@admin.register(Terme)
class TermeAdmin(ModelAdmin):
    """Les termes des types d'ouvrages par pays (ADR 0019) : la file des termes proposés, à
    valider ou à rejeter avec un motif. Un terme ne se supprime pas : rejeté, il reste."""

    form = TermeForm
    list_display = [
        "terme",
        "type_ouvrage",
        "pays_ou_tous",
        "portee",
        "statut",
        "origine",
        "nb_avis",
        "decide_par",
        "decide_le",
    ]
    list_filter = ["statut", "pays", "portee", "origine", "type_ouvrage"]
    search_fields = ["terme", "cle", "type_ouvrage__libelle", "type_ouvrage__cle"]
    readonly_fields = ["cle", "propose_par", "propose_le", "decide_par", "decide_le"]
    actions = ["action_valider", "action_rejeter"]

    @admin.display(description="pays", ordering="pays")
    def pays_ou_tous(self, obj: Terme) -> str:
        return obj.pays or "tous"

    def has_delete_permission(self, request, obj=None) -> bool:
        return False  # un terme rejeté reste, pour la trace (règle 3)

    def save_model(self, request, obj: Terme, form, change) -> None:
        if not change:
            obj.propose_par = obj.propose_par or request.user.get_username()
        if "statut" in form.changed_data and obj.statut != Terme.Statut.PROPOSE:
            obj.decide_par, obj.decide_le = request.user, timezone.now()
        super().save_model(request, obj, form, change)

    @admin.action(description="Valider les termes choisis")
    def action_valider(self, request, queryset) -> None:
        for t in queryset:
            services.valider(t, request.user)
        self.message_user(request, f"{queryset.count()} terme(s) validé(s).")

    @admin.action(description="Rejeter les termes choisis (motif déjà rempli)")
    def action_rejeter(self, request, queryset) -> None:
        faits, sans_motif = 0, []
        for t in queryset:
            if t.motif.strip():
                services.rejeter(t, t.motif, request.user)
                faits += 1
            else:
                sans_motif.append(t.terme)
        self.message_user(request, f"{faits} terme(s) rejeté(s).")
        if sans_motif:
            self.message_user(
                request,
                "Sans motif, non rejetés (ouvrir le terme pour écrire le motif) : "
                + ", ".join(sans_motif),
                level=messages.WARNING,
            )


@admin.register(Livrable)
class LivrableAdmin(ModelAdmin):
    list_display = ["libelle", "cle", "ordre"]


@admin.register(TypeQuantite)
class TypeQuantiteAdmin(ModelAdmin):
    list_display = ["libelle", "unite", "cle", "ordre"]
