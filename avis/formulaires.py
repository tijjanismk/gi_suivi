"""Formulaires du module avis : l'avis, la décision « on répond ou pas » (ADR 0021), et le critère
dont le filtre se saisit en champs (cases, années, mots-clés) puis se compose en JSON pour le
moteur (ADR 0013, § 3)."""

from __future__ import annotations

import re
from decimal import Decimal

from django import forms

from avis.models import Avis, BesoinExpert, Critere, DecisionAvis
from moteur.avis import decision as decision_moteur
from moteur.avis.filtres import FiltreInvalideError, lire_filtre
from references.models import Mission
from referentiel.models import Domaine, TypeOuvrage, TypeQuantite

CHAMP = (
    "gic:mt-1 gic:block gic:w-full gic:rounded-md gic:px-2 gic:py-1.5 gic:text-sm "
    "border border-base-200 dark:border-base-700 dark:bg-base-900"
)
# Le partage tel qu'on le copie depuis l'explorateur : \\AD-SERVEUR\GIC\… ou D:\GIC\…
_PREFIXE_PARTAGE = re.compile(r"^(\\\\[^\\]+\\GIC|[A-Za-z]:\\GIC)\\", re.IGNORECASE)
# Justificatifs exigés : choix du formulaire → clés du filtre
PIECES = {
    "trois": {},
    "quatre": {"pieces_requises": ["garde", "deuxieme_page", "signature", "attestation"]},
    "attestation": {"pieces_requises": ["attestation"]},
    "pv_bonne_fin": {"pieces_requises": ["bonne_fin|pv_reception"]},
    "aucune": {"pieces_completes_requises": False},
}
CHOIX_PIECES = [
    ("trois", "page de garde, page de signature et attestation"),
    ("quatre", "les trois pièces et la 2e page du contrat (cas exceptionnel, ADR 0015)"),
    ("attestation", "l'attestation seule"),
    ("pv_bonne_fin", "PV de réception ou attestation de bonne fin"),
    ("aucune", "aucun justificatif exigé : toutes les références comptent"),
]
CASES = ("natures", "domaines", "roles", "types_ouvrage", "familles_ouvrage")
TEXTES = ("mots_cles", "pays", "clients", "bailleurs")
# Clés du filtre que le formulaire saisit ; les autres (catégories, localités) sont gardées
GEREES = {
    *CASES,
    *TEXTES,
    "annee_min",
    "annee_max",
    "quantites_min",
    "pieces_requises",
    "pieces_completes_requises",
}


def _habiller(formulaire: forms.BaseForm, prefixe: str) -> None:
    for nom, champ in formulaire.fields.items():
        champ.widget.attrs["id"] = f"{prefixe}-{nom}"
        if not isinstance(champ.widget, forms.CheckboxSelectMultiple | forms.CheckboxInput):
            champ.widget.attrs["class"] = CHAMP


def relatif_au_partage(texte: str) -> str:
    """Un chemin copié de l'explorateur (`\\\\AD-SERVEUR\\GIC\\AVIS\\x.pdf`, `D:\\GIC\\…`) ou
    écrit avec des `/` → relatif au partage : `AVIS\\x.pdf`."""
    t = texte.strip().strip('"').replace("/", "\\")
    return _PREFIXE_PARTAGE.sub("", t).lstrip("\\")


class StatutSansDecision:
    """Le statut ne passe à « on répond » ou « on ne répond pas » que par une décision motivée
    (ADR 0021) : ni le formulaire de l'avis ni l'administration ne le posent."""

    def clean_statut(self) -> str:
        nouveau = self.cleaned_data["statut"]
        ancien = self.instance.statut if self.instance.pk else None
        refus = decision_moteur.changement_de_statut(ancien, nouveau)
        if refus:
            raise forms.ValidationError(refus)
        return nouveau


class FormulaireAvis(StatutSansDecision, forms.ModelForm):
    class Meta:
        model = Avis
        fields = [
            "reference",
            "objet",
            "type",
            "statut",
            "maitre_ouvrage",
            "bailleur",
            "pays",
            "groupement",
            "date_publication",
            "date_limite",
            "heure_limite",
            "mode_depot",
            "lieu_depot",
            "courriel_depot",
            "destinataire",
            "formule_appel",
            "methode_selection",
            "seuil_eligibilite",
            "note_maximale",
            "fichier_avis_chemin",
            "fichier_tdr_chemin",
            "observations",
        ]
        widgets = {
            "objet": forms.Textarea(attrs={"rows": 3}),
            "observations": forms.Textarea(attrs={"rows": 3}),
            "date_publication": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "date_limite": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "heure_limite": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        _habiller(self, "avis")
        self.fields[
            "statut"
        ].help_text = "« On répond » et « on ne répond pas » se décident depuis la fiche de l'avis."

    def _chemin(self, nom: str) -> str:
        texte = relatif_au_partage(self.cleaned_data.get(nom, ""))
        morceaux = [m for m in texte.split("\\") if m]
        if any(m in (".", "..") or ":" in m for m in morceaux):
            raise forms.ValidationError(
                "Un chemin du partage GIC, par exemple AVIS\\MALI\\2026-10\\avis.pdf."
            )
        return "\\".join(morceaux)

    def clean_fichier_avis_chemin(self) -> str:
        return self._chemin("fichier_avis_chemin")

    def clean_fichier_tdr_chemin(self) -> str:
        return self._chemin("fichier_tdr_chemin")

    def clean(self) -> dict:
        donnees = super().clean()
        publie, limite = donnees.get("date_publication"), donnees.get("date_limite")
        if publie and limite and limite < publie:
            self.add_error("date_limite", "La date limite précède la publication.")
        return donnees


class FormulaireDecision(forms.Form):
    """« On répond » ou « on ne répond pas », avec son motif ; le contrôle est celui du moteur."""

    decision = forms.ChoiceField(
        label="Décision",
        choices=DecisionAvis.Decision.choices,
        widget=forms.RadioSelect,
        error_messages={"required": "Choisissez « on répond » ou « on ne répond pas »."},
    )
    motif = forms.CharField(
        label="Motif",
        max_length=decision_moteur.MOTIF_MAX,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Pourquoi : métier, références, experts, exigences financières, délai…",
        error_messages={"required": "Indiquez pourquoi vous décidez de répondre ou non."},
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["motif"].widget.attrs["class"] = CHAMP
        self.fields["motif"].strip = False  # le moteur nettoie et juge le motif


def _choix_pieces(filtre: dict) -> str:
    if filtre.get("pieces_completes_requises") is False:
        return "aucune"
    for cle, valeurs in PIECES.items():
        if valeurs.get("pieces_requises") == filtre.get("pieces_requises"):
            return cle
    return "tel_quel"


def _en_json(valeur: Decimal) -> int | str:
    """Un minimum de quantité dans le JSON : 30 reste 30, 30,5 devient « 30.5 »."""
    if valeur == valeur.to_integral_value():
        return int(valeur)
    return f"{valeur.normalize():f}"


class FormulaireCritere(forms.ModelForm):
    """Le critère et son filtre. Le filtre composé est vérifié par le moteur ; les clés que le
    formulaire ne saisit pas (catégories, localités) sont gardées telles quelles."""

    natures = forms.MultipleChoiceField(
        label="natures",
        required=False,
        choices=Mission.Nature.choices,
        widget=forms.CheckboxSelectMultiple,
    )
    domaines = forms.MultipleChoiceField(
        label="domaines (principal ou secondaire)",
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    roles = forms.MultipleChoiceField(
        label="rôle du bureau",
        required=False,
        choices=Mission.Role.choices,
        widget=forms.CheckboxSelectMultiple,
        help_text="« Contrôleur principal » : seul ou chef de file",
    )
    types_ouvrage = forms.MultipleChoiceField(
        label="types d'ouvrages", required=False, widget=forms.CheckboxSelectMultiple
    )
    familles_ouvrage = forms.MultipleChoiceField(
        label="ou familles d'ouvrages", required=False, widget=forms.CheckboxSelectMultiple
    )
    annee_min = forms.IntegerField(
        label="depuis l'année", required=False, min_value=1900, max_value=2100
    )
    annee_max = forms.IntegerField(
        label="jusqu'à l'année", required=False, min_value=1900, max_value=2100
    )
    mots_cles = forms.CharField(
        label="mots-clés de l'intitulé",
        required=False,
        help_text="Séparés par des virgules ; un seul suffit ; « génie civil » veut les deux mots",
    )
    pays = forms.CharField(label="pays", required=False, help_text="Séparés par des virgules")
    clients = forms.CharField(
        label="clients", required=False, help_text="Nom ou sigle, séparés par des virgules"
    )
    bailleurs = forms.CharField(
        label="bailleurs", required=False, help_text="Nom ou sigle, séparés par des virgules"
    )
    pieces = forms.ChoiceField(label="justificatifs exigés", choices=CHOIX_PIECES)

    class Meta:
        model = Critere
        fields = [
            "code",
            "libelle",
            "reference_avis",
            "ordre",
            "experience",
            "mode",
            "points_par_mission",
            "plafond",
            "nb_min_missions",
            "annees_seuil",
            "points_socle",
            "points_par_annee",
            "note_manuelle",
        ]
        widgets = {"libelle": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.filtre = dict(self.instance.filtre or {})
        self.fields["domaines"].choices = [
            (d.code, f"{d.code} — {d.libelle}") for d in Domaine.objects.all()
        ]
        types = list(TypeOuvrage.objects.filter(actif=True))
        self.fields["types_ouvrage"].choices = [(t.cle, t.libelle) for t in types]
        familles = sorted({t.famille for t in types if t.famille})
        self.fields["familles_ouvrage"].choices = [(f, f) for f in familles]
        self.quantites = list(TypeQuantite.objects.all())
        for q in self.quantites:
            self.fields[f"quantite_{q.cle}"] = forms.DecimalField(
                label=f"{q.libelle} au moins ({q.unite})",
                required=False,
                min_value=0,
                max_digits=14,
                decimal_places=2,
            )
        choix = _choix_pieces(self.filtre)
        if choix == "tel_quel":
            exigees = " ; ".join(self.filtre.get("pieces_requises", []))
            self.fields["pieces"].choices = [
                *CHOIX_PIECES,
                ("tel_quel", f"comme enregistré : {exigees}"),
            ]
        if not self.is_bound:
            self._remplir(choix)
        _habiller(self, "critere")

    def _remplir(self, choix: str) -> None:
        f = self.filtre
        for cle in (*CASES, "annee_min", "annee_max"):
            if cle in f:
                self.initial[cle] = f[cle]
        for cle in TEXTES:
            if cle in f:
                self.initial[cle] = ", ".join(f[cle])
        for cle, minimum in (f.get("quantites_min") or {}).items():
            self.initial[f"quantite_{cle}"] = minimum
        self.initial["pieces"] = choix

    def groupes(self) -> list[tuple[str, list[forms.BoundField]]]:
        """Les champs par bloc, dans l'ordre de l'écran."""
        noms = [
            ("Le critère", ["code", "ordre", "reference_avis", "experience", "libelle"]),
            (
                "Le calcul",
                [
                    "mode",
                    "points_par_mission",
                    "plafond",
                    "nb_min_missions",
                    "annees_seuil",
                    "points_socle",
                    "points_par_annee",
                    "note_manuelle",
                ],
            ),
            ("Les références retenues", [*CASES, "annee_min", "annee_max", *TEXTES]),
            ("Quantités minimales", [f"quantite_{q.cle}" for q in self.quantites]),
            ("Preuve", ["pieces"]),
        ]
        return [(titre, [self[n] for n in champs]) for titre, champs in noms]

    def clean_code(self) -> str:
        code = self.cleaned_data["code"].strip()
        autres = Critere.objects.filter(avis=self.instance.avis, code=code)
        if autres.exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(f"Le critère {code} existe déjà dans cet avis.")
        return code

    def _composer(self, d: dict) -> dict:
        f = {cle: v for cle, v in self.filtre.items() if cle not in GEREES}
        for cle in CASES:
            if d.get(cle):
                f[cle] = list(d[cle])
        for cle in ("annee_min", "annee_max"):
            if d.get(cle) is not None:
                f[cle] = d[cle]
        for cle in TEXTES:
            valeurs = [v.strip() for v in (d.get(cle) or "").split(",") if v.strip()]
            if valeurs:
                f[cle] = valeurs
        quantites = {
            q.cle: _en_json(d[f"quantite_{q.cle}"])
            for q in self.quantites
            if d.get(f"quantite_{q.cle}") is not None
        }
        if quantites:
            f["quantites_min"] = quantites
        if d.get("pieces") == "tel_quel":
            for cle in ("pieces_requises", "pieces_completes_requises"):
                if cle in self.filtre:
                    f[cle] = self.filtre[cle]
        else:
            f.update(PIECES.get(d.get("pieces"), {}))
        return f

    def clean(self) -> dict:
        donnees = super().clean()
        filtre = self._composer(donnees)
        try:
            lire_filtre(filtre)
        except FiltreInvalideError as e:
            self.add_error(None, f"Filtre : {e}")
        else:
            self.instance.filtre = filtre
        return donnees


class FormulaireBesoin(forms.ModelForm):
    """Un poste demandé par les TDR ; les références comptées se filtrent comme un critère
    (natures, domaines, années, mots-clés), sans exigence de pièces."""

    natures = forms.MultipleChoiceField(
        label="références comptées : natures",
        required=False,
        choices=Mission.Nature.choices,
        widget=forms.CheckboxSelectMultiple,
    )
    domaines = forms.MultipleChoiceField(
        label="domaines", required=False, widget=forms.CheckboxSelectMultiple
    )
    annee_min = forms.IntegerField(
        label="depuis l'année", required=False, min_value=1900, max_value=2100
    )
    mots_cles = forms.CharField(
        label="mots-clés de l'intitulé", required=False, help_text="Séparés par des virgules"
    )

    class Meta:
        model = BesoinExpert
        fields = [
            "poste",
            "ordre",
            "niveau_min",
            "annees_experience_min",
            "nb_references_min",
            "specialites",
            "observations",
        ]
        widgets = {"observations": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["domaines"].choices = [
            (d.code, f"{d.code} — {d.libelle}") for d in Domaine.objects.all()
        ]
        f = dict(self.instance.filtre_references or {})
        if not self.is_bound:
            for cle in ("natures", "domaines", "annee_min"):
                if cle in f:
                    self.initial[cle] = f[cle]
            if f.get("mots_cles"):
                self.initial["mots_cles"] = ", ".join(f["mots_cles"])
        _habiller(self, "besoin")

    def clean(self) -> dict:
        d = super().clean()
        filtre = {cle: list(d[cle]) for cle in ("natures", "domaines") if d.get(cle)}
        if d.get("annee_min") is not None:
            filtre["annee_min"] = d["annee_min"]
        mots_cles = [v.strip() for v in (d.get("mots_cles") or "").split(",") if v.strip()]
        if mots_cles:
            filtre["mots_cles"] = mots_cles
        try:
            lire_filtre(filtre)
        except FiltreInvalideError as e:
            self.add_error(None, f"Filtre : {e}")
        else:
            self.instance.filtre_references = filtre
        return d
