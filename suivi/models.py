"""Modèle de données de GI-SUIVI (docs/suivi-transposition-python.md, section 2).

Les segments bruts ne sont jamais modifiés, sauf `dossier` et `statut_classement` lors d'un
recalcul : `debut`, `fin`, `fichier`, `chemin` restent ce que l'agent a envoyé.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from moteur.suivi.classement import normaliser_chemin


class Employe(models.Model):
    """Une personne mesurée. Le SID AD est la clé stable : le login change parfois."""

    sid_ad = models.CharField("SID AD", max_length=100, unique=True)
    login = models.CharField(max_length=150)
    nom_affiche = models.CharField("nom affiché", max_length=200, blank=True)
    actif = models.BooleanField(default=True)
    heures_prevues_semaine = models.DecimalField(
        "heures prévues par semaine", max_digits=4, decimal_places=1, default=40
    )
    utilisateur = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="employe",
    )

    class Meta:
        verbose_name = "employé"
        ordering = ["nom_affiche", "login"]

    def __str__(self) -> str:
        return self.nom_affiche or self.login


class Poste(models.Model):
    """Un ordinateur qui envoie des segments. Alimenté par chaque lot."""

    nom = models.CharField(max_length=100, unique=True)
    version_agent = models.CharField("version de l'agent", max_length=20, blank=True)
    dernier_envoi = models.DateTimeField(null=True, blank=True)
    demarrages_semaine = models.PositiveIntegerField(
        "démarrages de l'agent cette semaine", default=0
    )
    premier_vu = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nom"]

    def __str__(self) -> str:
        return self.nom


class Racine(models.Model):
    """Un dossier sous lequel les dossiers de projet se trouvent à `profondeur` niveaux."""

    chemin = models.CharField(
        max_length=400, unique=True, help_text=r"UNC, ex. \\AD-SERVEUR\GIC\MISSIONS_EN_COURS"
    )
    profondeur = models.PositiveSmallIntegerField(default=1)
    motif_code = models.CharField(
        "motif du code",
        max_length=200,
        default=r"^(GIC-[A-Z]{3}-[A-Z]{3}-\d{3}|\d{4}-[A-Z0-9]+-\d{3})",
        help_text="Expression régulière ; le premier groupe est le code du dossier.",
    )
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["chemin"]

    def __str__(self) -> str:
        return self.chemin


class Dossier(models.Model):
    """Un dossier de projet : la future table `Projet` partagée avec le module avis."""

    class Statut(models.TextChoices):
        DETECTE = "detecte", "détecté"
        ACTIF = "actif", "actif"
        CLOS = "clos", "clos"

    code = models.CharField(max_length=50, blank=True, db_index=True)
    nom = models.CharField(max_length=300)
    client = models.CharField(max_length=200, blank=True)
    responsable = models.ForeignKey(
        Employe,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="dossiers_responsable",
    )
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.DETECTE)
    chemin_windows = models.CharField(
        "chemin Windows",
        max_length=400,
        unique=True,
        help_text="UNC normalisé : minuscules, sans accents.",
    )
    racine = models.ForeignKey(
        Racine, null=True, blank=True, on_delete=models.PROTECT, related_name="dossiers"
    )
    valide = models.BooleanField("validé", default=False)
    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    valide_le = models.DateTimeField("validé le", null=True, blank=True)
    # Liens vers les missions (references) et les avis (avis) : ajoutés par migration
    # quand ces modules existeront.

    class Meta:
        ordering = ["code", "nom"]

    def __str__(self) -> str:
        return f"{self.code} — {self.nom}" if self.code else self.nom

    def save(self, *args, **kwargs) -> None:
        # Une seule écriture du chemin, celle du moteur : H:\ et \\AD-SERVEUR\GIC donnent
        # le même dossier
        self.chemin_windows = normaliser_chemin(self.chemin_windows)
        super().save(*args, **kwargs)


class RegleException(models.Model):
    """Rattachement hors convention (le blueprint dit « exception »).

    Un chemin exact, un dossier (préfixe) ou un mot-clé → un dossier de projet.
    """

    class Type(models.TextChoices):
        CHEMIN = "chemin", "chemin exact"
        PREFIXE = "prefixe", "dossier (et tout ce qu'il contient)"
        MOT_CLE = "mot_cle", "mot-clé dans le chemin"

    motif = models.CharField(max_length=400)
    type = models.CharField(max_length=10, choices=Type.choices)
    dossier = models.ForeignKey(Dossier, on_delete=models.CASCADE, related_name="exceptions")
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    cree_le = models.DateTimeField("créée le", auto_now_add=True)

    class Meta:
        verbose_name = "exception"
        ordering = ["-cree_le"]
        constraints = [
            models.UniqueConstraint(fields=["motif", "type"], name="exception_motif_type_unique")
        ]

    def __str__(self) -> str:
        return f"{self.get_type_display()} « {self.motif} » → {self.dossier}"


class Segment(models.Model):
    """Une période continue sur une application et un fichier, telle que l'agent l'a mesurée."""

    class Etat(models.TextChoices):
        ACTIF = "ACTIF", "actif"
        INACTIF = "INACTIF", "inactif"

    class StatutClassement(models.TextChoices):
        DOSSIER = "dossier", "rattaché à un dossier"
        A_CLASSER = "a_classer", "à classer"
        BROUILLON = "brouillon", "brouillon"
        APPLICATION = "application", "application sans fichier"
        IGNORE = "ignore", "ignoré"

    employe = models.ForeignKey(Employe, on_delete=models.PROTECT, related_name="segments")
    poste = models.ForeignKey(Poste, on_delete=models.PROTECT, related_name="segments")
    dossier = models.ForeignKey(
        Dossier, null=True, blank=True, on_delete=models.SET_NULL, related_name="segments"
    )
    debut = models.DateTimeField("début")
    fin = models.DateTimeField()
    duree_s = models.DecimalField("durée (s)", max_digits=9, decimal_places=1)
    etat = models.CharField("état", max_length=8, choices=Etat.choices)
    application = models.CharField(max_length=200)
    fichier = models.CharField(max_length=400, blank=True)
    chemin = models.CharField(max_length=1000, blank=True)
    statut_classement = models.CharField(
        "classement",
        max_length=12,
        choices=StatutClassement.choices,
        default=StatutClassement.A_CLASSER,
    )
    lot_id = models.UUIDField("lot")
    cree_le = models.DateTimeField("reçu le", auto_now_add=True)

    class Meta:
        ordering = ["debut"]
        indexes = [
            models.Index(fields=["employe", "debut"], name="segment_employe_debut"),
            models.Index(fields=["dossier", "debut"], name="segment_dossier_debut"),
            models.Index(fields=["lot_id"], name="segment_lot"),
            models.Index(fields=["statut_classement", "debut"], name="segment_classement_debut"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(fin__gte=models.F("debut")), name="segment_fin_apres_debut"
            )
        ]

    def __str__(self) -> str:
        return f"{self.employe} {self.debut:%d/%m %H:%M} {self.application} {self.fichier}".strip()


class JournalAcces(models.Model):
    """Qui a consulté ou modifié quoi, et quand. Jamais modifié, jamais purgé avec les segments."""

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    login = models.CharField(max_length=150)  # gardé même si l'utilisateur disparaît
    action = models.CharField(max_length=50)
    cible = models.CharField(max_length=300, blank=True)
    horodatage = models.DateTimeField(auto_now_add=True, db_index=True)
    adresse_ip = models.GenericIPAddressField("adresse IP", null=True, blank=True)

    class Meta:
        verbose_name = "entrée du journal d'accès"
        verbose_name_plural = "journal d'accès"
        ordering = ["-horodatage"]

    def __str__(self) -> str:
        return f"{self.horodatage:%d/%m/%Y %H:%M} {self.login} {self.action} {self.cible}"


class Parametre(models.Model):
    """Réglage modifiable sans redéploiement : seuil d'inactivité, rétention, correspondances…"""

    cle = models.CharField("clé", max_length=100, unique=True)
    valeur = models.JSONField()
    description = models.CharField(max_length=300, blank=True)

    class Meta:
        verbose_name = "paramètre"
        ordering = ["cle"]

    def __str__(self) -> str:
        return self.cle
