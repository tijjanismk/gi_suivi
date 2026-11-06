"""Référentiel partagé par les références, les experts et les avis (docs/schema-donnees.md).

Domaines du code de référence, catégories, clients, bailleurs (ADR 0008) ; types d'ouvrages,
livrables et types de quantités (ADR 0011) ; termes des types d'ouvrages par pays (ADR 0019).
Les localités viendront avec le module avis.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models

from moteur.references.doublons import normaliser

# Les pays où le bureau intervient (présentation du bureau) et le Cameroun (ADR 0019) : une liste
# fermée, pour que « Guinée » et « Guinee » ne fassent pas deux pays.
PAYS_BUREAU = (
    "Mali",
    "Niger",
    "Burkina Faso",
    "Guinée",
    "Mauritanie",
    "Sénégal",
    "Togo",
    "Gabon",
    "Cameroun",
)


class Domaine(models.Model):
    """Les domaines du code de référence (GIC-<domaine>-<nature>-<numéro>)."""

    code = models.CharField(max_length=3, unique=True)
    libelle = models.CharField("libellé", max_length=100)
    ordre = models.PositiveSmallIntegerField(default=100)

    class Meta:
        ordering = ["ordre", "code"]

    def __str__(self) -> str:
        return f"{self.code} — {self.libelle}"


class Categorie(models.Model):
    """Catégorie d'une mission dans son domaine (bas-fonds, périmètres irrigués, AEP…)."""

    domaine = models.ForeignKey(Domaine, on_delete=models.PROTECT, related_name="categories")
    cle = models.SlugField("clé", max_length=80, unique=True)
    libelle = models.CharField("libellé", max_length=150)

    class Meta:
        verbose_name = "catégorie"
        ordering = ["domaine__ordre", "libelle"]

    def __str__(self) -> str:
        return self.libelle


class Client(models.Model):
    """Maître d'ouvrage."""

    class Type(models.TextChoices):
        ETAT = "etat", "État"
        COLLECTIVITE = "collectivite", "collectivité"
        PROJET = "projet", "projet"
        ONG = "ong", "ONG"
        PRIVE = "prive", "privé"
        BAILLEUR = "bailleur", "bailleur"

    nom = models.CharField(max_length=200, unique=True)
    sigle = models.CharField(max_length=50, blank=True)
    type = models.CharField(max_length=20, choices=Type.choices, blank=True)
    pays = models.CharField(max_length=100, blank=True, default="Mali")

    class Meta:
        ordering = ["nom"]

    def __str__(self) -> str:
        return self.sigle or self.nom


class Bailleur(models.Model):
    nom = models.CharField(max_length=200, unique=True)
    sigle = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ["nom"]

    def __str__(self) -> str:
        return self.sigle or self.nom


class TypeOuvrage(models.Model):
    """Liste fermée du chantier 4 (ADR 0011), avec la famille qui relie le vocabulaire des
    bailleurs au nôtre : « recharge de nappe » trouve les seuils. Les noms que les pays donnent à
    chaque type sont des `Terme` (ADR 0019) ; `synonymes` est l'ancien tableau, repris en termes
    par la migration 0007 et retiré quand plus rien ne le lit."""

    cle = models.SlugField("clé", max_length=60, unique=True)
    libelle = models.CharField("libellé", max_length=120)
    famille = models.CharField(max_length=120, blank=True)
    synonymes = ArrayField(models.CharField(max_length=120), default=list, blank=True)
    ordre = models.PositiveSmallIntegerField(default=100)
    actif = models.BooleanField(default=True)

    class Meta:
        verbose_name = "type d'ouvrage"
        verbose_name_plural = "types d'ouvrages"
        ordering = ["ordre", "libelle"]

    def __str__(self) -> str:
        return self.libelle


class Terme(models.Model):
    """Un nom qui mène à un type d'ouvrage, dans un pays ou dans tous (ADR 0019) : « AEPS » au
    Burkina mène à l'AES. Un terme venu d'une machine (collecte, Claude) attend ici, proposé,
    qu'une personne le valide (règle 3) ; seuls les termes validés servent."""

    class Portee(models.TextChoices):
        PARTOUT = "partout", "références et avis"
        REFERENCES = "references", "références du bureau seulement"

    class Statut(models.TextChoices):
        PROPOSE = "propose", "proposé"
        VALIDE = "valide", "validé"
        REJETE = "rejete", "rejeté"

    class Origine(models.TextChoices):
        REPRISE = "reprise", "ancien synonyme"
        COLLECTE = "collecte", "collecte d'avis"
        SAISIE = "saisie", "saisie"
        CLAUDE = "claude", "Claude Desktop"
        AVIS = "avis", "rattaché depuis un avis"

    type_ouvrage = models.ForeignKey(
        TypeOuvrage, on_delete=models.PROTECT, related_name="termes", verbose_name="type d'ouvrage"
    )
    terme = models.CharField(
        max_length=120, help_text="Tel qu'il s'écrit dans les avis : accents, tiret, sigle."
    )
    cle = models.CharField("clé", max_length=120, editable=False)
    pays = models.CharField(
        max_length=100,
        blank=True,
        choices=[(p, p) for p in PAYS_BUREAU],
        help_text="Vide : tous les pays.",
    )
    portee = models.CharField(
        "portée", max_length=10, choices=Portee.choices, default=Portee.PARTOUT
    )
    statut = models.CharField(max_length=8, choices=Statut.choices, default=Statut.PROPOSE)
    origine = models.CharField(max_length=10, choices=Origine.choices, default=Origine.SAISIE)
    source_url = models.URLField("avis qui l'emploie", max_length=500, blank=True)
    nb_avis = models.PositiveIntegerField("nombre d'avis", null=True, blank=True)
    motif = models.CharField(max_length=500, blank=True)
    propose_par = models.CharField("proposé par", max_length=150, blank=True)
    propose_le = models.DateTimeField("proposé le", auto_now_add=True)
    decide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="décidé par",
    )
    decide_le = models.DateTimeField("décidé le", null=True, blank=True)

    class Meta:
        verbose_name = "terme d'un type d'ouvrage"
        verbose_name_plural = "termes des types d'ouvrages"
        ordering = ["type_ouvrage__ordre", "terme", "pays"]
        constraints = [
            models.UniqueConstraint(
                fields=["type_ouvrage", "cle", "pays"], name="terme_unique_par_type_et_pays"
            )
        ]

    def __str__(self) -> str:
        return f"{self.terme} ({self.pays})" if self.pays else self.terme

    def save(self, *args, **kwargs) -> None:
        self.terme = (self.terme or "").strip()
        self.cle = normaliser(self.terme)
        super().save(*args, **kwargs)


class Livrable(models.Model):
    """Ce que la mission a produit : APS, APD, DAO, EIES, NIES, suivi-contrôle."""

    cle = models.SlugField("clé", max_length=40, unique=True)
    libelle = models.CharField("libellé", max_length=120)
    ordre = models.PositiveSmallIntegerField(default=100)

    class Meta:
        ordering = ["ordre", "libelle"]

    def __str__(self) -> str:
        return self.libelle


class TypeQuantite(models.Model):
    """Superficie, longueur, forages, sites, capacité : ajouter un type sans migration."""

    cle = models.SlugField("clé", max_length=40, unique=True)
    libelle = models.CharField("libellé", max_length=120)
    unite = models.CharField("unité", max_length=20)
    ordre = models.PositiveSmallIntegerField(default=100)

    class Meta:
        verbose_name = "type de quantité"
        verbose_name_plural = "types de quantités"
        ordering = ["ordre", "libelle"]

    def __str__(self) -> str:
        return f"{self.libelle} ({self.unite})"
