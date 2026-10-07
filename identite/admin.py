from django.contrib import admin
from django.contrib.auth.models import Group

from identite.models import Utilisateur

# Les droits viennent des groupes AD (Utilisateur.groupes) : les groupes Django ne servent à rien
# et une saisie dedans laisserait croire qu'elle donne des droits.
admin.site.unregister(Group)


@admin.register(Utilisateur)
class UtilisateurAdmin(admin.ModelAdmin):
    """Lecture seule : les utilisateurs et leurs groupes viennent de l'AD, pas d'une saisie."""

    list_display = ["login_windows", "nom_affiche", "groupes", "derniere_activite", "is_active"]
    search_fields = ["login_windows", "nom_affiche"]
    readonly_fields = [
        "login_windows",
        "groupes",
        "groupes_lus_le",
        "derniere_activite",
        "last_login",
    ]
    exclude = ["password"]

    def has_add_permission(self, request) -> bool:
        return False
