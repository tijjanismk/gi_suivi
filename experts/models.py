"""Le vivier des experts et leurs affectations aux références (ADR 0012).

Une affectation cite toujours une référence du bureau (`references.Mission`) et porte sa preuve :
c'est ce qui rend un CV vérifiable (règles des CV, section 8).
"""

from __future__ import annotations

from django.db import models

from references.models import Mission
from referentiel.models import Domaine, TypeOuvrage


class Expert(models.Model):
    class Statut(models.TextChoices):
        INTERNE = "interne", "interne"
        EXTERNE = "externe", "externe"
        ANCIEN = "ancien", "ancien (plus mobilisable)"

    class Categorie(models.TextChoices):
        INGENIEUR = "ingenieur", "ingénieur"
        TECHNICIEN_SUPERIEUR = "technicien_superieur", "technicien supérieur"
        TECHNICIEN = "technicien", "technicien"

    nom = models.CharField(max_length=100)
    prenoms = models.CharField("prénoms", max_length=150, blank=True)
    statut = models.CharField(max_length=10, choices=Statut.choices, default="interne")
    categorie = models.CharField("catégorie", max_length=25, choices=Categorie.choices, blank=True)
    fonction = models.CharField(max_length=150, blank=True)
    specialite = models.CharField("spécialité", max_length=200, blank=True)
    domaines = models.ManyToManyField(Domaine, blank=True, related_name="experts")
    debut_carriere = models.PositiveSmallIntegerField(
        "début de carrière (année)", null=True, blank=True
    )
    nationalite = models.CharField("nationalité", max_length=80, blank=True, default="malienne")
    langues = models.CharField(max_length=200, blank=True, default="français")
    disponible = models.BooleanField(default=True)
    dossier = models.CharField(
        "dossier sur le partage", max_length=300, blank=True, help_text=r"EXPERTS\NOM Prénom"
    )
    accord_le = models.DateField(
        "accord écrit le",
        null=True,
        blank=True,
        help_text="Expert externe : accord écrit pour présenter son CV (règles des CV, section 7)",
    )
    notes = models.TextField(blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nom", "prenoms"]
        constraints = [models.UniqueConstraint(fields=["nom", "prenoms"], name="expert_nom_unique")]

    def __str__(self) -> str:
        return f"{self.nom} {self.prenoms}".strip()

    @property
    def mobilisable(self) -> bool:
        return self.disponible and self.statut != self.Statut.ANCIEN


class Diplome(models.Model):
    class Niveau(models.TextChoices):
        BAC2 = "bac+2", "bac+2"
        BAC3 = "bac+3", "bac+3"
        BAC4 = "bac+4", "bac+4"
        BAC5 = "bac+5", "bac+5"
        BAC8 = "bac+8", "bac+8 (doctorat)"

    expert = models.ForeignKey(Expert, on_delete=models.CASCADE, related_name="diplomes")
    intitule = models.CharField("intitulé", max_length=250)
    etablissement = models.CharField("établissement", max_length=200, blank=True)
    pays = models.CharField(max_length=80, blank=True)
    annee = models.PositiveSmallIntegerField("année", null=True, blank=True)
    niveau = models.CharField(max_length=6, choices=Niveau.choices, blank=True)
    justificatif = models.CharField("justificatif sur le partage", max_length=500, blank=True)

    class Meta:
        verbose_name = "diplôme"
        ordering = ["-annee", "intitule"]

    def __str__(self) -> str:
        return f"{self.intitule} ({self.annee or 'année ?'})"


class Affectation(models.Model):
    """L'expert sur une référence du bureau : poste, période, preuve."""

    expert = models.ForeignKey(Expert, on_delete=models.CASCADE, related_name="affectations")
    mission = models.ForeignKey(Mission, on_delete=models.PROTECT, related_name="affectations")
    poste = models.CharField(max_length=150)
    du = models.DateField(null=True, blank=True)
    au = models.DateField(null=True, blank=True, help_text="Vide = en cours")
    plein_temps = models.BooleanField("à temps plein", default=True)
    temps_hj = models.DecimalField(
        "hommes-jours", max_digits=7, decimal_places=1, null=True, blank=True
    )
    preuve = models.CharField(
        max_length=250, help_text="Contrat, annexe, rapport ou attestation qui cite l'expert"
    )
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-du", "mission__code"]

    def __str__(self) -> str:
        return f"{self.expert} — {self.mission.code} ({self.poste})"


class ExperienceExterne(models.Model):
    """Une expérience hors du bureau, pour le CV et le compte des années."""

    expert = models.ForeignKey(Expert, on_delete=models.CASCADE, related_name="experiences")
    employeur = models.CharField(max_length=200)
    poste = models.CharField(max_length=150)
    lieu = models.CharField(max_length=150, blank=True)
    du = models.DateField(null=True, blank=True)
    au = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)
    types_ouvrage = models.ManyToManyField(TypeOuvrage, blank=True, related_name="+")

    class Meta:
        verbose_name = "expérience hors du bureau"
        verbose_name_plural = "expériences hors du bureau"
        ordering = ["-du"]

    def __str__(self) -> str:
        return f"{self.expert} — {self.employeur} ({self.poste})"
