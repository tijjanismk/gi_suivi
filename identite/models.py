from __future__ import annotations

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.postgres.fields import ArrayField
from django.db import models


class GestionnaireUtilisateurs(BaseUserManager):
    def create_user(self, login_windows: str, **champs) -> Utilisateur:
        u = self.model(login_windows=normaliser_login(login_windows), **champs)
        u.set_unusable_password()  # jamais de mot de passe : l'identité vient d'IIS
        u.save(using=self._db)
        return u

    def create_superuser(self, login_windows: str, **champs) -> Utilisateur:
        # Les droits viennent des groupes AD, pas d'un drapeau en base.
        return self.create_user(login_windows, groupes=[settings.GROUPE_DIRECTION], **champs)


def normaliser_login(login: str) -> str:
    """`GICONSEILS\\Jean.Traore` → `giconseils\\jean.traore` : une seule écriture par personne."""
    return login.strip().lower()


class Utilisateur(AbstractBaseUser):
    """Une personne du domaine. Créée ou mise à jour par le middleware depuis REMOTE_USER.

    Pas de mot de passe (le champ hérité reste inutilisable), pas de drapeau « administrateur » :
    les droits se lisent dans `groupes`, copie des groupes AD rafraîchie toutes les 10 minutes.
    """

    login_windows = models.CharField(max_length=150, unique=True)
    nom_affiche = models.CharField(max_length=200, blank=True)
    courriel = models.EmailField(blank=True)
    groupes = ArrayField(models.CharField(max_length=100), default=list, blank=True)
    groupes_lus_le = models.DateTimeField(null=True, blank=True)
    derniere_activite = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)  # nom imposé par Django

    objects = GestionnaireUtilisateurs()

    USERNAME_FIELD = "login_windows"

    class Meta:
        verbose_name = "utilisateur"
        ordering = ["login_windows"]

    def __str__(self) -> str:
        return self.nom_affiche or self.login_windows

    def dans_groupe(self, *noms: str) -> bool:
        voulus = {n.lower() for n in noms}
        return any(g.lower() in voulus for g in self.groupes)

    # -- droits -------------------------------------------------------------------------
    @property
    def direction(self) -> bool:
        """Membre de GI-Direction : voit tout et peut agir (valider, paramétrer, rattacher)."""
        return self.is_active and self.dans_groupe(settings.GROUPE_DIRECTION)

    @property
    def lecture_seule(self) -> bool:
        """Membre de GI-Direction-Lecture seulement : voit tout, ne modifie rien."""
        return (
            self.is_active
            and not self.direction
            and self.dans_groupe(settings.GROUPE_DIRECTION_LECTURE)
        )

    # -- ce que l'admin Django attend ---------------------------------------------------
    @property
    def is_staff(self) -> bool:
        return self.direction or self.lecture_seule

    def has_perm(self, perm: str, obj=None) -> bool:
        if self.direction:
            return True
        if self.lecture_seule:
            # « suivi.view_segment » oui ; add_, change_, delete_ non
            return perm.rsplit(".", 1)[-1].startswith("view_")
        return False

    def has_module_perms(self, app_label: str) -> bool:
        return self.is_staff
