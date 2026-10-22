"""Écran 5 des maquettes (AD05) : types de pièces, réglés une fois par la direction ; les
échéances proposées au dépôt en découlent."""

from __future__ import annotations

import re

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.shortcuts import get_object_or_404, redirect, render

from administratif.models import TypePiece
from identite.decorateurs import consultation_requise, groupe_requis
from identite.models import Utilisateur
from suivi.services import journaliser

CHAMP = (
    "gic:mt-1 gic:w-full gic:rounded-md gic:px-2 gic:py-1.5 gic:text-sm "
    "border border-base-200 dark:border-base-700 dark:bg-base-900"
)
AVEC_DUREE = (TypePiece.Regle.APRES_EMISSION, TypePiece.Regle.REVUE_PERIODIQUE)


class FormulaireType(forms.ModelForm):
    class Meta:
        model = TypePiece
        fields = [
            "code",
            "libelle",
            "organisme",
            "regle_validite",
            "duree_mois",
            "rappel_jours",
            "exigee_par_defaut",
            "dossier",
            "responsable",
            "ordre",
            "actif",
        ]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["dossier"].required = False
        self.fields["responsable"].queryset = Utilisateur.objects.filter(is_active=True).order_by(
            "nom_affiche", "login_windows"
        )
        self.fields["responsable"].empty_label = "La direction"
        if self.instance.pk:
            self.fields["code"].disabled = True  # le code nomme le dossier : fixé à la création
        for nom, champ in self.fields.items():
            if not isinstance(champ.widget, forms.CheckboxInput):
                champ.widget.attrs["class"] = CHAMP
            champ.widget.attrs["id"] = f"type-{nom}"

    def clean_code(self) -> str:
        code = self.cleaned_data["code"].strip().upper()
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9-]*", code):
            raise forms.ValidationError("Majuscules, chiffres et tirets seulement.")
        return code

    def clean(self) -> dict:
        donnees = super().clean()
        if donnees.get("regle_validite") in AVEC_DUREE and not donnees.get("duree_mois"):
            self.add_error("duree_mois", "Cette règle demande une durée en mois.")
        if not donnees.get("dossier") and donnees.get("code"):
            donnees["dossier"] = f"ADMINISTRATIF\\PIECES\\{donnees['code']}"
        return donnees


@consultation_requise
def types(request):
    journaliser(request, "consulter:types_pieces")
    return render(
        request,
        "administratif/types.html",
        {
            **admin.site.each_context(request),
            "titre": "Types de pièces",
            "types": TypePiece.objects.select_related("responsable").order_by(
                "-actif", "ordre", "libelle"
            ),
            "peut_agir": request.user.direction,
        },
    )


@groupe_requis(settings.GROUPE_DIRECTION)
def modifier_type(request, code: str | None = None):
    instance = get_object_or_404(TypePiece, code=code) if code else None
    formulaire = FormulaireType(request.POST or None, instance=instance)
    if request.method == "POST" and formulaire.is_valid():
        t = formulaire.save()
        journaliser(request, "piece:type", f"{'modifié' if instance else 'créé'} {t.code}")
        messages.success(request, f"Type « {t.libelle} » enregistré.")
        return redirect("administratif:types")
    return render(
        request,
        "administratif/type_formulaire.html",
        {
            **admin.site.each_context(request),
            "titre": f"Modifier : {instance.libelle}" if instance else "Ajouter un type de pièce",
            "formulaire": formulaire,
            "t": instance,
        },
    )
