"""Avis de marchés (ADR 0013) : l'avis, son barème en données, les références sélectionnées et
les pièces administratives exigées.

Le calcul (filtre, sélection, note) vit dans `moteur/avis/` ; ici, seulement ce qu'on garde. Les
fichiers de l'avis restent sur le partage (`PARTAGE_GIC`, règle 4) : la base garde leur chemin.
Un avis n'est jamais supprimé : il passe « sans suite ».
"""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from administratif.models import TypePiece
from experts.models import Diplome, Expert
from moteur.avis.filtres import FiltreInvalideError, lire_filtre


class Avis(models.Model):
    """Un AMI, une DP ou un AO reçu, de la réception au résultat."""

    class Type(models.TextChoices):
        AMI = "AMI", "AMI (manifestation d'intérêt)"
        DP = "DP", "DP (demande de propositions)"
        AO = "AO", "AO (appel d'offres)"
        AUTRE = "autre", "autre"

    class Statut(models.TextChoices):
        RECU = "recu", "reçu"
        EN_ANALYSE = "en_analyse", "en analyse"
        GO = "go", "on répond"
        NO_GO = "no_go", "on ne répond pas"
        DEPOSE = "depose", "déposé"
        GAGNE = "gagne", "gagné"
        PERDU = "perdu", "perdu"
        SANS_SUITE = "sans_suite", "sans suite"

    class ModeDepot(models.TextChoices):
        PHYSIQUE = "physique", "en main propre"
        COURRIEL = "courriel", "par courriel"
        PLATEFORME = "plateforme", "sur une plateforme (UNGM…)"
        AUTRE = "autre", "autre"

    reference = models.CharField("référence de l'avis", max_length=200, db_index=True)
    objet = models.TextField()
    type = models.CharField(max_length=5, choices=Type.choices)
    statut = models.CharField(max_length=12, choices=Statut.choices, default=Statut.RECU)
    maitre_ouvrage = models.ForeignKey(
        "referentiel.Client",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="avis",
        verbose_name="maître d'ouvrage",
    )
    bailleur = models.ForeignKey(
        "referentiel.Bailleur",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="avis",
    )
    pays = models.CharField(max_length=100, default="Mali")
    groupement = models.BooleanField("en groupement", default=False)
    date_publication = models.DateField("publié le", null=True, blank=True)
    date_limite = models.DateField("date limite de dépôt")
    heure_limite = models.TimeField("heure limite", null=True, blank=True)
    mode_depot = models.CharField(
        "mode de dépôt", max_length=12, choices=ModeDepot.choices, blank=True
    )
    lieu_depot = models.CharField("lieu ou plateforme de dépôt", max_length=300, blank=True)
    courriel_depot = models.EmailField("courriel de dépôt", blank=True)
    # La lettre de manifestation d'intérêt du dossier (AV14) : à qui elle s'adresse
    destinataire = models.CharField(
        "destinataire de la lettre",
        max_length=300,
        blank=True,
        help_text="Après « L'attention de », ex. Monsieur le Coordonnateur National de l'Unité "
        "de gestion du projet, Niamey ; vide : le maître d'ouvrage",
    )
    formule_appel = models.CharField(
        "formule d'appel",
        max_length=150,
        blank=True,
        help_text="Ex. Monsieur le Coordonnateur National ; vide : Madame, Monsieur",
    )
    methode_selection = models.CharField(
        "méthode de sélection", max_length=20, blank=True, help_text="QC, SFQC, SMC, SQC…"
    )
    seuil_eligibilite = models.DecimalField(
        "seuil d'éligibilité", max_digits=6, decimal_places=2, null=True, blank=True
    )
    note_maximale = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    fichier_avis_chemin = models.CharField(
        "fichier de l'avis",
        max_length=500,
        blank=True,
        help_text=r"Relatif au partage GIC, ex. AVIS\MALI\2026-10\SOMAPEP\AMI-SOMAPEP-SA.pdf",
    )
    fichier_tdr_chemin = models.CharField(
        "fichier des TDR", max_length=500, blank=True, help_text="Relatif au partage GIC"
    )
    # Dernière simulation (AV04) : note sûre et note possible (ADR 0013, § 3)
    note_sure = models.DecimalField(
        "note sûre", max_digits=6, decimal_places=2, null=True, blank=True
    )
    note_possible = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    simulee_le = models.DateTimeField("simulée le", null=True, blank=True)
    # Qui a décidé de répondre ou non, quand et pourquoi : `DecisionAvis` (ADR 0021)
    observations = models.TextField(blank=True)
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "avis"
        verbose_name_plural = "avis"
        ordering = ["-date_limite", "-pk"]

    def __str__(self) -> str:
        return f"{self.type} {self.reference}"

    def save(self, *args, **kwargs) -> None:
        """À sa création, l'avis reprend les types de pièces actifs exigés par défaut (ADR 0010
        § 1, ADR 0013 § 2) ; on coche ensuite ce que l'avis demande en plus."""
        nouveau = self._state.adding
        super().save(*args, **kwargs)
        if nouveau:
            PieceExigee.objects.bulk_create(
                PieceExigee(avis=self, type=t, origine=PieceExigee.Origine.PAR_DEFAUT)
                for t in TypePiece.objects.filter(exigee_par_defaut=True, actif=True)
            )

    @property
    def decision_en_cours(self) -> DecisionAvis | None:
        """La dernière décision « on répond ou pas », None s'il n'y en a pas encore."""
        return self.decisions.select_related("par").first()


class Critere(models.Model):
    """Une ligne du barème, décrite en données (`docs/schema-donnees.md`) ; `moteur/avis/` la
    calcule. Les modes sont ceux de `moteur.avis.notation.Mode`."""

    class Mode(models.TextChoices):
        PAR_MISSION = "par_mission", "points par référence"
        ANCIENNETE = "anciennete", "ancienneté"
        FORFAIT = "forfait", "forfait"
        MANUEL = "manuel", "note saisie à la main"

    class Experience(models.TextChoices):
        """La rubrique D du dossier où vont ses références (`moteur.avis.sommaire.Experience`)."""

        GENERALE = "generale", "expérience générale (liste de D.1)"
        SPECIFIQUE = "specifique", "expérience spécifique (un D.2 à lui)"
        HORS = "hors", "hors des expériences (pas de liste)"

    avis = models.ForeignKey(Avis, on_delete=models.CASCADE, related_name="criteres")
    code = models.CharField(max_length=20, help_text="Numérotation du barème : 1, 2.1, E.1…")
    reference_avis = models.CharField(
        "renvoi dans l'avis", max_length=100, blank=True, help_text="Ex. TDR § 12"
    )
    libelle = models.TextField("texte du critère")
    ordre = models.PositiveSmallIntegerField(default=0)
    mode = models.CharField(max_length=12, choices=Mode.choices)
    experience = models.CharField(
        "rubrique du dossier",
        max_length=10,
        choices=Experience.choices,
        blank=True,
        help_text="Vide : d'après le texte (« expériences générales », « spécifiques ») ou le "
        "critère parent, sinon spécifique pour des points par référence",
    )
    points_par_mission = models.DecimalField(
        "points par référence", max_digits=6, decimal_places=2, default=0
    )
    plafond = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Les points du forfait ; vide = sans plafond",
    )
    nb_min_missions = models.PositiveSmallIntegerField("références demandées au moins", default=0)
    annees_seuil = models.PositiveSmallIntegerField("années demandées", default=0)
    points_socle = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    points_par_annee = models.DecimalField(
        "points par année au-delà", max_digits=6, decimal_places=2, default=0
    )
    filtre = models.JSONField(
        default=dict, blank=True, help_text="Format dans docs/schema-donnees.md"
    )
    note_manuelle = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    brouillon = models.BooleanField(
        default=False,
        help_text="Préparé par Claude Desktop (outil MCP) : ne compte pas avant d'être confirmé",
    )

    class Meta:
        verbose_name = "critère"
        verbose_name_plural = "critères"
        ordering = ["avis", "ordre", "code"]
        constraints = [
            models.UniqueConstraint(fields=["avis", "code"], name="critere_code_unique_par_avis")
        ]

    def __str__(self) -> str:
        return f"{self.code} — {self.libelle[:80]}"

    def clean(self) -> None:
        """Le filtre se lit par le moteur, avec son message ; chaque mode a de quoi compter."""
        erreurs = {}
        try:
            lire_filtre(self.filtre)
        except FiltreInvalideError as e:
            erreurs["filtre"] = str(e)
        if self.mode == self.Mode.PAR_MISSION and not self.points_par_mission:
            erreurs["points_par_mission"] = "des points par référence sont nécessaires"
        if self.mode == self.Mode.ANCIENNETE and not self.points_socle:
            erreurs["points_socle"] = "les points du socle sont nécessaires"
        if self.mode == self.Mode.FORFAIT and self.plafond is None:
            erreurs["plafond"] = "les points du forfait se saisissent dans le plafond"
        if erreurs:
            raise ValidationError(erreurs)


class Selection(models.Model):
    """Une référence éligible à un critère, telle que la simulation l'a classée (AV04). Une
    personne peut la forcer ou l'exclure : son choix (`retenue_par`, `motif`) reste d'une
    simulation à l'autre (ADR 0013, § 2). L'avis se retrouve par le critère."""

    class Preuve(models.TextChoices):
        PROUVEE = "prouvee", "prouvée"
        A_AUDITER = "a_auditer", "pièces à auditer"
        MANQUANTE = "manquante", "pièce manquante"

    critere = models.ForeignKey(Critere, on_delete=models.CASCADE, related_name="selections")
    mission = models.ForeignKey(
        "references.Mission", on_delete=models.PROTECT, related_name="selections"
    )
    rang = models.PositiveSmallIntegerField(default=0)
    preuve = models.CharField(max_length=10, choices=Preuve.choices)
    points = models.DecimalField("points apportés", max_digits=6, decimal_places=2, default=0)
    points_en_jeu = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    retenue = models.BooleanField(
        default=False, help_text="Jointe au dossier ; forcée ou exclue si une personne l'a choisi"
    )
    retenue_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    retenue_le = models.DateTimeField(null=True, blank=True)
    motif = models.CharField(max_length=300, blank=True)

    class Meta:
        verbose_name = "référence sélectionnée"
        verbose_name_plural = "références sélectionnées"
        ordering = ["critere", "rang"]
        constraints = [
            models.UniqueConstraint(
                fields=["critere", "mission"], name="selection_unique_par_critere"
            )
        ]

    def __str__(self) -> str:
        return f"{self.critere.code} — {self.mission.code}"

    @property
    def choix_d_une_personne(self) -> bool:
        return self.retenue_par_id is not None


class PieceExigee(models.Model):
    """Une pièce administrative que le dossier de l'avis doit joindre (ADR 0010, § 1)."""

    class Origine(models.TextChoices):
        PAR_DEFAUT = "par_defaut", "exigée dans chaque dossier"
        AVIS = "avis", "demandée par l'avis"

    avis = models.ForeignKey(Avis, on_delete=models.CASCADE, related_name="pieces_exigees")
    type = models.ForeignKey(TypePiece, on_delete=models.PROTECT, related_name="exigee_par")
    origine = models.CharField(max_length=12, choices=Origine.choices, default=Origine.AVIS)

    class Meta:
        verbose_name = "pièce exigée"
        verbose_name_plural = "pièces exigées"
        ordering = ["avis", "type__ordre", "type__libelle"]
        constraints = [
            models.UniqueConstraint(fields=["avis", "type"], name="piece_exigee_unique_par_avis")
        ]

    def __str__(self) -> str:
        return f"{self.avis} — {self.type}"


class BesoinExpert(models.Model):
    """Un expert clé que l'avis demande (TDR) : le profil exigé, et l'expert retenu pour le poste
    (ADR 0012, AV06). Un poste sans expert retenu est signalé sur la fiche de l'avis."""

    avis = models.ForeignKey(Avis, on_delete=models.CASCADE, related_name="besoins")
    poste = models.CharField(max_length=150, help_text="Ex. chef de mission, spécialiste QHSE")
    ordre = models.PositiveSmallIntegerField(default=0)
    niveau_min = models.CharField(
        "diplôme au moins", max_length=6, choices=Diplome.Niveau.choices, blank=True
    )
    annees_experience_min = models.PositiveSmallIntegerField("années d'expérience", default=0)
    nb_references_min = models.PositiveSmallIntegerField("références au moins", default=0)
    specialites = models.CharField(
        "spécialités acceptées",
        max_length=300,
        blank=True,
        help_text="Mots de la spécialité ou du diplôme, séparés par des virgules ; un seul suffit",
    )
    filtre_references = models.JSONField(
        "références comptées",
        default=dict,
        blank=True,
        help_text="Filtre des missions de l'expert, au format des critères",
    )
    expert_retenu = models.ForeignKey(
        Expert, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    observations = models.TextField(blank=True)

    class Meta:
        verbose_name = "expert demandé"
        verbose_name_plural = "experts demandés"
        ordering = ["avis", "ordre", "pk"]

    def __str__(self) -> str:
        return f"{self.avis} — {self.poste}"

    def clean(self) -> None:
        try:
            lire_filtre(self.filtre_references)
        except FiltreInvalideError as e:
            raise ValidationError({"filtre_references": str(e)}) from None


class Proposition(models.Model):
    """Un avis candidat, pas encore validé (règle 3 de `CONTEXT.md`) : ce qu'une veille, un dépôt
    de TDR ou Claude a extrait. Une personne confirme champ par champ, puis accepte (l'avis est
    créé) ou rejette (avec un motif). La proposition reste pour la trace."""

    class Origine(models.TextChoices):
        VEILLE = "veille", "veille"
        DEPOT_TDR = "depot_tdr", "dépôt de TDR"
        CLAUDE = "claude", "Claude Desktop"
        SAISIE = "saisie", "saisie"

    class Statut(models.TextChoices):
        A_VALIDER = "a_valider", "à valider"
        ACCEPTEE = "acceptee", "acceptée"
        REJETEE = "rejetee", "rejetée"

    origine = models.CharField(max_length=10, choices=Origine.choices)
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.A_VALIDER)
    source_url = models.URLField("adresse de la source", max_length=500, blank=True)
    fichier_chemin = models.CharField(
        "fichier source", max_length=500, blank=True, help_text="Relatif au partage GIC"
    )
    champs_extraits = models.JSONField(default=dict, blank=True)
    champs_confirmes = models.JSONField(default=dict, blank=True)
    avis_cree = models.ForeignKey(
        Avis, null=True, blank=True, on_delete=models.SET_NULL, related_name="propositions"
    )
    proposee_par = models.CharField("proposée par", max_length=150, blank=True)
    proposee_le = models.DateTimeField(auto_now_add=True)
    decide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    decide_le = models.DateTimeField(null=True, blank=True)
    motif_rejet = models.CharField(max_length=500, blank=True)

    class Meta:
        verbose_name = "proposition d'avis"
        verbose_name_plural = "propositions d'avis"
        ordering = ["statut", "-proposee_le"]

    def __str__(self) -> str:
        reference = (self.champs_extraits or {}).get("reference", "")
        return f"Proposition {self.pk} ({self.get_origine_display()}) {reference}".strip()


class DecisionAvis(models.Model):
    """Une décision « on répond » ou « on ne répond pas » sur un avis (ADR 0021, ISO 9001
    § 8.2.3) : qui, à quel titre, quand, pourquoi, et la note de la dernière simulation à ce
    moment. Jamais modifiée ni supprimée : la plus récente est la décision en cours, les autres
    restent pour la trace. Seules la direction et sa délégation décident (ADR 0022)."""

    class Decision(models.TextChoices):
        GO = "go", "on répond"
        NO_GO = "no_go", "on ne répond pas"

    class Qualite(models.TextChoices):
        DIRECTION = "direction", "direction"
        DELEGATION = "delegation", "délégation de la direction"

    avis = models.ForeignKey(Avis, on_delete=models.PROTECT, related_name="decisions")
    decision = models.CharField("décision", max_length=6, choices=Decision.choices)
    motif = models.TextField()
    par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    qualite = models.CharField("qualité", max_length=10, choices=Qualite.choices)
    le = models.DateTimeField(auto_now_add=True)
    statut_avant = models.CharField("statut avant", max_length=12, choices=Avis.Statut.choices)
    note_sure = models.DecimalField(
        "note sûre", max_digits=6, decimal_places=2, null=True, blank=True
    )
    note_possible = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    simulee_le = models.DateTimeField("simulée le", null=True, blank=True)

    class Meta:
        verbose_name = "décision sur un avis"
        verbose_name_plural = "décisions sur les avis"
        ordering = ["-le", "-pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(decision__in=["go", "no_go"]) & ~models.Q(motif=""),
                name="decision_avis_motivee",
            )
        ]

    def __str__(self) -> str:
        return f"{self.avis} — {self.get_decision_display()}"
