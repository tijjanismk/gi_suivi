"""Référentiel partagé par les références, les experts et les avis (docs/schema-donnees.md).

Domaines du code de référence, catégories, clients, bailleurs (ADR 0008) ; types d'ouvrages,
livrables et types de quantités (ADR 0011). Les localités viendront avec le module avis.
"""

from __future__ import annotations

from django.contrib.postgres.fields import ArrayField
from django.db import models


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
    """Liste fermée du chantier 4 (ADR 0011), avec la famille et les synonymes qui relient le
    vocabulaire des bailleurs au nôtre : « recharge de nappe » trouve les seuils."""

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
