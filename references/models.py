"""Références du bureau (ADR 0008) : une mission = un contrat signé, un code immuable.

Une fiche reconnue comme doublon d'une autre n'est jamais supprimée : elle est « absorbée par »
le code gardé. Les décisions sur les paires suspectes sont gardées (`DecisionDoublon`) pour
qu'une paire tranchée ne revienne pas.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from referentiel.models import Bailleur, Categorie, Client, Domaine


class Mission(models.Model):
    class Nature(models.TextChoices):
        ETU = "ETU", "études"
        CTR = "CTR", "contrôle"
        ETC = "ETC", "études et contrôle"

    class Role(models.TextChoices):
        SEUL = "seul", "seul"
        CHEF_DE_FILE = "chef_de_file", "chef de file d'un groupement"
        MEMBRE = "membre", "membre d'un groupement"

    class Intervention(models.TextChoices):
        REALISATION = "realisation", "réalisation"
        REHABILITATION = "rehabilitation", "réhabilitation"

    class StatutCode(models.TextChoices):
        EXISTANT = "existant", "existant"
        NOUVEAU = "nouveau", "attribué au chantier 2"

    class Verification(models.TextChoices):
        IMPORTEE = "importee", "importée"
        A_VERIFIER = "a_verifier", "à vérifier"
        VERIFIEE = "verifiee", "vérifiée"

    code = models.CharField(
        max_length=30, unique=True, help_text="Attribué une fois, jamais modifié"
    )
    domaine = models.ForeignKey(
        Domaine, on_delete=models.PROTECT, related_name="missions", help_text="Domaine principal"
    )
    domaines_secondaires = models.ManyToManyField(
        Domaine, blank=True, related_name="missions_secondaires"
    )
    nature = models.CharField(max_length=3, choices=Nature.choices)
    categorie = models.ForeignKey(
        Categorie, null=True, blank=True, on_delete=models.PROTECT, related_name="missions"
    )
    intitule = models.TextField("intitulé")
    intitule_court = models.CharField("intitulé court", max_length=300, blank=True)
    numero_contrat = models.CharField("numéro du contrat", max_length=100, blank=True)
    client = models.ForeignKey(
        Client, null=True, blank=True, on_delete=models.PROTECT, related_name="missions"
    )
    bailleur = models.ForeignKey(
        Bailleur, null=True, blank=True, on_delete=models.PROTECT, related_name="missions"
    )
    pays = models.CharField(max_length=100, blank=True, default="Mali")
    annee = models.PositiveSmallIntegerField("année", null=True, blank=True, db_index=True)
    date_debut = models.DateField(null=True, blank=True)
    date_fin = models.DateField(null=True, blank=True)
    montant = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    devise = models.CharField(max_length=10, default="FCFA")
    role = models.CharField("rôle du bureau", max_length=20, choices=Role.choices, default="seul")
    part_bureau = models.DecimalField(
        "part du bureau (%)", max_digits=5, decimal_places=2, null=True, blank=True
    )
    intervention = models.CharField(max_length=20, choices=Intervention.choices, blank=True)
    statut_code = models.CharField(max_length=10, choices=StatutCode.choices, default="existant")
    statut_verification = models.CharField(
        "vérification", max_length=12, choices=Verification.choices, default="importee"
    )
    absorbee_par = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="absorbees",
        verbose_name="absorbée par",
        help_text="Même contrat qu'une autre référence : c'est elle qui compte",
    )
    source_word = models.CharField("fichier Word d'origine", max_length=300, blank=True)
    numero_source = models.CharField("numéro dans la source", max_length=50, blank=True)
    observations = models.TextField(blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]
        indexes = [models.Index(fields=["domaine", "nature"], name="mission_domaine_nature")]

    def __str__(self) -> str:
        return f"{self.code} — {self.intitule_court or self.intitule[:80]}"

    def save(self, *args, **kwargs) -> None:
        """Règle 2 de CONTEXT.md et ADR 0008 § 2 : un code enregistré ne change plus."""
        self.code = self.code.strip().upper()
        if self.pk:
            ancien = Mission.objects.filter(pk=self.pk).values_list("code", flat=True).first()
            if ancien is not None and ancien != self.code:
                raise ValueError(f"le code {ancien} est immuable (ADR 0008)")
        super().save(*args, **kwargs)

    @property
    def libelle(self) -> str:
        return self.intitule_court or self.intitule


class DecisionDoublon(models.Model):
    """La décision d'une personne sur une paire suspecte. `mission_a` a la plus petite clé."""

    mission_a = models.ForeignKey(Mission, on_delete=models.PROTECT, related_name="+")
    mission_b = models.ForeignKey(Mission, on_delete=models.PROTECT, related_name="+")
    meme_contrat = models.BooleanField("même contrat")
    gardee = models.ForeignKey(
        Mission, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    raisons = models.CharField("raisons de la détection", max_length=300, blank=True)
    note = models.CharField(max_length=300, blank=True)
    par = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "décision de doublon"
        verbose_name_plural = "décisions de doublon"
        ordering = ["-le"]
        constraints = [
            models.UniqueConstraint(fields=["mission_a", "mission_b"], name="decision_paire_unique")
        ]

    def __str__(self) -> str:
        verdict = f"même contrat, gardée {self.gardee.code}" if self.meme_contrat else "différents"
        return f"{self.mission_a.code} / {self.mission_b.code} : {verdict}"
