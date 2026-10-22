"""Revue d'une référence et création d'une référence nouvelle (docs/design.md § 5.3 ;
chantiers 2 et 6). Direction seulement ; le code n'est jamais modifiable (ADR 0008 § 2)."""

from __future__ import annotations

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from identite.decorateurs import groupe_requis
from moteur.references.codes import prochain_code
from references.models import Mission
from referentiel.models import Client, Domaine
from suivi.services import journaliser

CHAMP = (
    "gic:mt-1 gic:block gic:w-full gic:rounded-md gic:px-2 gic:py-1.5 gic:text-sm "
    "border border-base-200 dark:border-base-700 dark:bg-base-900"
)
LARGES = {"intitule", "intitule_court", "observations", "domaines_secondaires"}


class FormulaireMission(forms.ModelForm):
    client_nouveau = forms.CharField(
        label="ou nouveau client", required=False, max_length=200,
        help_text="Si le client n'est pas dans la liste",
    )  # fmt: skip

    class Meta:
        model = Mission
        fields = [
            "intitule",
            "intitule_court",
            "domaine",
            "domaines_secondaires",
            "nature",
            "categorie",
            "client",
            "bailleur",
            "numero_contrat",
            "pays",
            "annee",
            "date_debut",
            "date_fin",
            "montant",
            "devise",
            "role",
            "part_bureau",
            "intervention",
            "observations",
        ]
        widgets = {
            "intitule": forms.Textarea(attrs={"rows": 3}),
            "observations": forms.Textarea(attrs={"rows": 3}),
            "date_debut": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "date_fin": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "domaines_secondaires": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["client"].queryset = Client.objects.order_by("nom")
        for nom, champ in self.fields.items():
            champ.widget.attrs["id"] = f"mission-{nom}"
            if not isinstance(champ.widget, forms.CheckboxSelectMultiple):
                champ.widget.attrs["class"] = CHAMP

    def clean(self) -> dict:
        donnees = super().clean()
        debut, fin = donnees.get("date_debut"), donnees.get("date_fin")
        if debut and fin and fin < debut:
            self.add_error("date_fin", "La fin précède le début.")
        part = donnees.get("part_bureau")
        if part is not None and not 0 < part <= 100:
            self.add_error("part_bureau", "Une part en pourcentage, entre 0 et 100.")
        if donnees.get("domaine") in donnees.get("domaines_secondaires", []):
            donnees["domaines_secondaires"] = [
                d for d in donnees["domaines_secondaires"] if d != donnees["domaine"]
            ]
        return donnees

    def save(self, commit: bool = True) -> Mission:
        nom = self.cleaned_data.get("client_nouveau", "").strip()
        if nom:
            self.instance.client = Client.objects.filter(
                nom__iexact=nom
            ).first() or Client.objects.create(nom=nom)
        if self.instance.date_debut and not self.instance.annee:
            self.instance.annee = self.instance.date_debut.year
        return super().save(commit)


@groupe_requis(settings.GROUPE_DIRECTION)
def modifier(request, code: str):
    m = get_object_or_404(Mission, code=code)
    formulaire = FormulaireMission(request.POST or None, instance=m)
    if request.method == "POST" and formulaire.is_valid():
        action = request.POST.get("action", "enregistrer")
        if action == "verifiee" and m.absorbee_par_id:
            messages.error(
                request, "Une fiche absorbée ne se vérifie pas : c'est le code gardé qui compte."
            )
            return redirect("references:modifier", code=code)
        m = formulaire.save()
        if action == "verifiee":
            m.statut_verification = Mission.Verification.VERIFIEE
        elif action == "a_verifier":
            m.statut_verification = Mission.Verification.A_VERIFIER
        m.save(update_fields=["statut_verification", "modifie_le"])
        journaliser(request, "reference:revue", f"{code} {m.statut_verification}")
        messages.success(request, f"{code} enregistrée ({m.get_statut_verification_display()}).")
        return redirect("references:fiche", code=code)
    return render(
        request,
        "references/formulaire.html",
        {
            **admin.site.each_context(request),
            "titre": f"Revoir {m.code}",
            "m": m,
            "formulaire": formulaire,
            "larges": LARGES,
        },
    )


@groupe_requis(settings.GROUPE_DIRECTION)
def nouvelle(request):
    """Une référence pour un contrat qui n'a pas encore de code (missions en cours,
    chantier 6) : le code proposé est le numéro suivant de la série domaine-nature."""
    donnees = request.POST if request.method == "POST" else request.GET
    domaine = Domaine.objects.filter(code=donnees.get("domaine", "")).first()
    nature = donnees.get("nature", "")
    existants = Mission.objects.values_list("code", flat=True)
    propose = (
        prochain_code(domaine.code, nature, existants)
        if domaine and nature in dict(Mission.Nature.choices)
        else ""
    )
    intitule = donnees.get("intitule", "").strip()
    if request.method == "POST" and propose:
        if not intitule:
            messages.error(request, "Indiquez l'intitulé du contrat.")
        else:
            # le numéro est recalculé au moment d'enregistrer ; l'unicité du code en base
            # empêche deux attributions simultanées du même numéro
            with transaction.atomic():
                code = prochain_code(domaine.code, nature, existants.all())
                m = Mission.objects.create(
                    code=code, domaine=domaine, nature=nature, intitule=intitule,
                    intitule_court=intitule[:300], statut_code=Mission.StatutCode.NOUVEAU,
                    statut_verification=Mission.Verification.A_VERIFIER,
                )  # fmt: skip
            journaliser(request, "reference:nouvelle", code)
            messages.success(request, f"Code {code} attribué. Complétez la fiche.")
            return redirect("references:modifier", code=m.code)
    return render(
        request,
        "references/nouvelle.html",
        {
            **admin.site.each_context(request),
            "titre": "Nouvelle référence",
            "domaines": Domaine.objects.all(),
            "natures": Mission.Nature.choices,
            "domaine": domaine,
            "nature": nature,
            "propose": propose,
            "intitule": intitule,
        },
    )
