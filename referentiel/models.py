"""Référentiel partagé par les références, les experts et les avis (docs/schema-donnees.md).

Premier lot (ADR 0008) : domaines du code de référence, catégories, clients, bailleurs. Les
types d'ouvrages, localités et types de quantités viennent avec le chantier 4.
"""

from __future__ import annotations

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
