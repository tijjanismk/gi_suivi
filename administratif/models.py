"""Pièces administratives du bureau (ADR 0010) : types, versions, demandes de renouvellement.

Les fichiers restent sur le partage (`PARTAGE_GIC`, règle 4) : la base garde le chemin relatif et
l'empreinte SHA-256 de chaque version, jamais le fichier. Une version n'est jamais supprimée :
remplacée, elle passe dans l'historique ; écartée par erreur, elle est « retirée » avec un motif.
"""

from __future__ import annotations

from datetime import date

from django.conf import settings
from django.db import models

from moteur.administratif import echeances


class TypePiece(models.Model):
    """Une pièce exigée dans les dossiers d'offre, et sa règle de validité. Réglé par la
    direction (écran « Types de pièces »)."""

    class Regle(models.TextChoices):
        APRES_EMISSION = "apres_emission", "N mois après l'émission"
        FIN_ANNEE = "fin_annee", "jusqu'au 31/12 de l'année d'émission"
        DATE_DU_DOCUMENT = "date_du_document", "date écrite sur le document"
        REVUE_PERIODIQUE = "revue_periodique", "revue tous les N mois"
        PERMANENTE = "permanente", "permanente"

    code = models.CharField(
        max_length=40, unique=True, help_text="Majuscules et tirets, ex. QUITUS-FISCAL"
    )
    libelle = models.CharField("pièce", max_length=200)
    organisme = models.CharField("délivrée par", max_length=200, blank=True)
    regle_validite = models.CharField("règle de validité", max_length=20, choices=Regle.choices)
    duree_mois = models.PositiveSmallIntegerField(
        "durée en mois",
        null=True,
        blank=True,
        help_text=(
            "Après l'émission ou entre deux revues ; indicative si la date est sur le document"
        ),
    )
    rappel_jours = models.PositiveSmallIntegerField("rappel (jours avant l'échéance)", default=15)
    exigee_par_defaut = models.BooleanField(
        "exigée dans chaque dossier",
        default=True,
        help_text="Sinon, seulement quand l'avis la demande",
    )
    dossier = models.CharField(
        max_length=300,
        help_text=r"Relatif au partage GIC, ex. ADMINISTRATIF\PIECES\QUITUS-FISCAL",
    )
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Vide = la direction",
    )
    ordre = models.PositiveSmallIntegerField(default=100)
    actif = models.BooleanField(default=True)

    class Meta:
        verbose_name = "type de pièce"
        verbose_name_plural = "types de pièces"
        ordering = ["ordre", "libelle"]

    def __str__(self) -> str:
        return self.libelle

    @property
    def regle_texte(self) -> str:
        if self.regle_validite == self.Regle.APRES_EMISSION:
            return f"{self.duree_mois} mois après l'émission"
        if self.regle_validite == self.Regle.REVUE_PERIODIQUE:
            return f"revue tous les {self.duree_mois} mois"
        if self.regle_validite == self.Regle.DATE_DU_DOCUMENT and self.duree_mois:
            return f"date écrite sur le document ({self.duree_mois} mois en pratique)"
        return self.get_regle_validite_display()

    def date_de_fin(self, date_emission: date, date_document: date | None = None) -> date | None:
        return echeances.date_de_fin(
            self.regle_validite, date_emission, self.duree_mois, date_document
        )


class PieceAdministrative(models.Model):
    """Une version d'une pièce : un fichier du partage, identifié par son empreinte."""

    type = models.ForeignKey(TypePiece, on_delete=models.PROTECT, related_name="versions")
    chemin = models.CharField(max_length=500, help_text="Relatif au partage GIC")
    empreinte = models.CharField("empreinte SHA-256", max_length=64, unique=True)
    taille = models.BigIntegerField(null=True, blank=True)
    nb_pages = models.PositiveIntegerField("pages", null=True, blank=True)
    numero = models.CharField("numéro du document", max_length=100, blank=True)
    date_emission = models.DateField("émise le")
    valide_jusqu_au = models.DateField(
        "valide jusqu'au", null=True, blank=True, help_text="Vide = permanente"
    )
    deposee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    deposee_le = models.DateTimeField("enregistrée le", auto_now_add=True)
    retiree = models.BooleanField("retirée", default=False)
    motif_retrait = models.CharField(max_length=300, blank=True)

    class Meta:
        verbose_name = "pièce administrative"
        verbose_name_plural = "pièces administratives"
        ordering = ["type__ordre", "-date_emission", "-pk"]

    def __str__(self) -> str:
        return f"{self.type} du {self.date_emission:%d/%m/%Y}"

    @property
    def nom_fichier(self) -> str:
        return self.chemin.replace("/", "\\").rsplit("\\", 1)[-1]

    def pour_moteur(self) -> echeances.Version:
        return echeances.Version(self.date_emission, self.valide_jusqu_au, self.pk)


class DemandeRenouvellement(models.Model):
    """Une démarche en cours auprès de l'organisme. Close d'elle-même quand une version émise
    depuis la demande est enregistrée."""

    type = models.ForeignKey(TypePiece, on_delete=models.PROTECT, related_name="demandes")
    demandee_le = models.DateField("demandée le")
    aupres_de = models.CharField("auprès de", max_length=200, blank=True)
    par = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    relance_prevue_le = models.DateField("relance prévue le", null=True, blank=True)
    note = models.CharField(max_length=300, blank=True)
    close_le = models.DateField("close le", null=True, blank=True)

    class Meta:
        verbose_name = "demande de renouvellement"
        verbose_name_plural = "demandes de renouvellement"
        ordering = ["-demandee_le", "-pk"]

    def __str__(self) -> str:
        return f"{self.type} demandé le {self.demandee_le:%d/%m/%Y}"
