"""Écrans du vivier (ADR 0012) : liste, fiche, création et modification d'un expert, diplômes,
justificatifs du dossier (CV, diplômes, attestations, à ouvrir), affectations aux références
(avec leur preuve) et expériences hors du bureau. Consultation : direction et consultation
seule ; toute écriture : direction, journalisée."""

from __future__ import annotations

import mimetypes

from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.db.models import Count, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from administratif.services import PartageIndisponibleError
from administratif.vues.registre import lire_date
from experts import justificatifs, services
from experts.models import Affectation, Diplome, ExperienceExterne, Expert
from identite.decorateurs import consultation_requise, groupe_requis
from references.models import Mission
from referentiel.models import Domaine
from suivi.services import journaliser

CHAMP = (
    "gic:mt-1 gic:block gic:w-full gic:rounded-md gic:px-2 gic:py-1.5 gic:text-sm "
    "border border-base-200 dark:border-base-700 dark:bg-base-900"
)


class FormulaireExpert(forms.ModelForm):
    class Meta:
        model = Expert
        fields = [
            "nom",
            "prenoms",
            "statut",
            "categorie",
            "fonction",
            "specialite",
            "domaines",
            "debut_carriere",
            "nationalite",
            "langues",
            "disponible",
            "dossier",
            "accord_le",
            "notes",
        ]
        widgets = {
            "domaines": forms.CheckboxSelectMultiple,
            "accord_le": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        for nom, champ in self.fields.items():
            champ.widget.attrs["id"] = f"expert-{nom}"
            if not isinstance(champ.widget, forms.CheckboxSelectMultiple | forms.CheckboxInput):
                champ.widget.attrs["class"] = CHAMP


@consultation_requise
def vivier(request):
    journaliser(request, "consulter:experts")
    qs = Expert.objects.prefetch_related("domaines").annotate(nb_affectations=Count("affectations"))
    texte = request.GET.get("q", "").strip()
    if texte:
        qs = qs.filter(
            Q(nom__icontains=texte)
            | Q(prenoms__icontains=texte)
            | Q(specialite__icontains=texte)
            | Q(fonction__icontains=texte)
        )
    statut = request.GET.get("statut", "")
    if statut in Expert.Statut.values:
        qs = qs.filter(statut=statut)
    categorie = request.GET.get("categorie", "")
    if categorie in Expert.Categorie.values:
        qs = qs.filter(categorie=categorie)
    domaine = request.GET.get("domaine", "")
    if domaine:
        qs = qs.filter(domaines__code=domaine)
    mobilisables = request.GET.get("mobilisables") == "1"
    if mobilisables:
        qs = qs.filter(disponible=True).exclude(statut=Expert.Statut.ANCIEN)
    experts = list(qs.order_by("nom", "prenoms"))
    for e in experts:
        e.annees = services.annees(e)
    return render(
        request,
        "experts/vivier.html",
        {
            **admin.site.each_context(request),
            "titre": "Experts du bureau",
            "experts": experts,
            "q": texte,
            "statut": statut,
            "categorie": categorie,
            "domaine": domaine,
            "mobilisables": mobilisables,
            "statuts": Expert.Statut.choices,
            "categories": Expert.Categorie.choices,
            "domaines": Domaine.objects.all(),
            "peut_agir": request.user.direction,
        },
    )


def _missions():
    return Mission.objects.filter(absorbee_par=None).order_by("code")


@consultation_requise
def fiche(request, expert_id: int):
    e = get_object_or_404(Expert.objects.prefetch_related("domaines"), pk=expert_id)
    journaliser(request, "consulter:expert", str(e.pk))
    erreur, fichiers = "", []
    try:
        fichiers = justificatifs.fichiers(e)
    except (PartageIndisponibleError, OSError) as x:
        erreur = str(x)
    diplomes = list(e.diplomes.all())
    prefixe = f"{e.dossier}\\".lower()
    for d in diplomes:  # le justificatif s'ouvre s'il est dans le dossier de l'expert
        dans = d.justificatif[len(prefixe) :] if d.justificatif.lower().startswith(prefixe) else ""
        d.dans_dossier = dans if e.dossier else ""
    return render(
        request,
        "experts/fiche.html",
        {
            **admin.site.each_context(request),
            "titre": str(e),
            "e": e,
            "annees": services.annees(e),
            "alertes": services.alertes(e),
            "affectations": e.affectations.select_related("mission", "mission__client"),
            "diplomes": diplomes,
            "fichiers": fichiers,
            "erreur_partage": erreur,
            "experiences": e.experiences.prefetch_related("types_ouvrage"),
            "missions": _missions(),
            "niveaux": Diplome.Niveau.choices,
            "peut_agir": request.user.direction,
        },
    )


@consultation_requise
def fichier(request, expert_id: int):
    """Ouvre un fichier du dossier de l'expert : `?f=` chemin relatif au dossier."""
    e = get_object_or_404(Expert, pk=expert_id)
    try:
        chemin = justificatifs.chemin_du_fichier(e, request.GET.get("f", ""))
    except (PartageIndisponibleError, ValueError) as x:
        raise Http404(str(x)) from x
    journaliser(request, "consulter:fichier_expert", f"{e.pk} {chemin.name}")
    type_mime = mimetypes.guess_type(chemin.name)[0] or "application/octet-stream"
    return FileResponse(chemin.open("rb"), content_type=type_mime, filename=chemin.name)


@groupe_requis(settings.GROUPE_DIRECTION)
def modifier(request, expert_id: int | None = None):
    e = get_object_or_404(Expert, pk=expert_id) if expert_id else None
    formulaire = FormulaireExpert(request.POST or None, instance=e)
    if request.method == "POST" and formulaire.is_valid():
        e = formulaire.save()
        journaliser(request, "expert:modifier" if expert_id else "expert:creer", str(e.pk))
        messages.success(request, f"{e} enregistré.")
        return redirect("experts:fiche", expert_id=e.pk)
    return render(
        request,
        "experts/formulaire.html",
        {
            **admin.site.each_context(request),
            "titre": f"Modifier {e}" if e else "Nouvel expert",
            "e": e,
            "formulaire": formulaire,
        },
    )


def _retour(request, expert: Expert):
    retour = request.POST.get("retour", "")
    if retour.startswith("/references/"):
        return redirect(retour)
    return redirect("experts:fiche", expert_id=expert.pk)


@require_POST
@groupe_requis(settings.GROUPE_DIRECTION)
def affecter(request):
    """Depuis la fiche d'un expert ou d'une référence : expert, mission, poste, dates, preuve."""
    e = get_object_or_404(Expert, pk=request.POST.get("expert"))
    m = get_object_or_404(Mission, pk=request.POST.get("mission"))
    if m.absorbee_par_id:
        m = m.absorbee_par  # une référence absorbée renvoie au code gardé
    poste, preuve = request.POST.get("poste", "").strip(), request.POST.get("preuve", "").strip()
    du, au = lire_date(request.POST.get("du")), lire_date(request.POST.get("au"))
    if not poste or not preuve:
        messages.error(
            request, "Le poste et la preuve sont obligatoires : sans preuve, pas d'affectation."
        )
    elif du and au and au < du:
        messages.error(request, "La fin précède le début.")
    else:
        a = Affectation.objects.create(
            expert=e,
            mission=m,
            poste=poste[:150],
            du=du,
            au=au,
            plein_temps=request.POST.get("plein_temps") == "1",
            preuve=preuve[:250],
        )
        journaliser(request, "expert:affecter", f"{e.pk} {m.code} {a.poste}")
        messages.success(request, f"{e} affecté à {m.code} comme {a.poste}.")
    return _retour(request, e)


@require_POST
@groupe_requis(settings.GROUPE_DIRECTION)
def retirer_affectation(request, affectation_id: int):
    a = get_object_or_404(
        Affectation.objects.select_related("expert", "mission"), pk=affectation_id
    )
    expert = a.expert
    journaliser(
        request,
        "expert:retirer_affectation",
        f"{expert.pk} {a.mission.code} {a.poste} {a.du}..{a.au}",
    )
    a.delete()
    messages.success(request, f"Affectation à {a.mission.code} retirée.")
    return _retour(request, expert)


@require_POST
@groupe_requis(settings.GROUPE_DIRECTION)
def ajouter_diplome(request, expert_id: int):
    e = get_object_or_404(Expert, pk=expert_id)
    intitule = request.POST.get("intitule", "").strip()
    annee = request.POST.get("annee", "")
    niveau = request.POST.get("niveau", "")
    if (
        not intitule
        or (annee and not annee.isdigit())
        or (niveau and niveau not in Diplome.Niveau.values)
    ):
        messages.error(request, "Intitulé obligatoire ; année en chiffres ; niveau de la liste.")
    else:
        Diplome.objects.create(
            expert=e,
            intitule=intitule[:250],
            etablissement=request.POST.get("etablissement", "").strip()[:200],
            pays=request.POST.get("pays", "").strip()[:80],
            annee=int(annee) if annee else None,
            niveau=niveau,
        )
        journaliser(request, "expert:diplome", f"{e.pk} {intitule}")
        messages.success(request, "Diplôme ajouté.")
    return redirect("experts:fiche", expert_id=e.pk)


@require_POST
@groupe_requis(settings.GROUPE_DIRECTION)
def ajouter_experience(request, expert_id: int):
    e = get_object_or_404(Expert, pk=expert_id)
    employeur, poste = (
        request.POST.get("employeur", "").strip(),
        request.POST.get("poste", "").strip(),
    )
    du, au = lire_date(request.POST.get("du")), lire_date(request.POST.get("au"))
    if not employeur or not poste:
        messages.error(request, "Employeur et poste obligatoires.")
    elif du and au and au < du:
        messages.error(request, "La fin précède le début.")
    else:
        ExperienceExterne.objects.create(
            expert=e,
            employeur=employeur[:200],
            poste=poste[:150],
            lieu=request.POST.get("lieu", "").strip()[:150],
            du=du,
            au=au,
            description=request.POST.get("description", "").strip(),
        )
        journaliser(request, "expert:experience", f"{e.pk} {employeur}")
        messages.success(request, "Expérience ajoutée.")
    return redirect("experts:fiche", expert_id=e.pk)


@require_POST
@groupe_requis(settings.GROUPE_DIRECTION)
def retirer_element(request, quoi: str, element_id: int):
    modele = {"diplome": Diplome, "experience": ExperienceExterne}.get(quoi)
    if modele is None:
        messages.error(request, "Élément inconnu.")
        return redirect("experts:vivier")
    x = get_object_or_404(modele, pk=element_id)
    expert = x.expert
    journaliser(request, f"expert:retirer_{quoi}", f"{expert.pk} {x}")
    x.delete()
    messages.success(request, "Retiré.")
    return redirect("experts:fiche", expert_id=expert.pk)
