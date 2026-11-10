"""Écrans des avis (ADR 0013, AV03) : la liste, la fiche (barème, pièces exigées, fichiers) et la
saisie d'un avis et de ses critères. Consultation : direction, consultation seule et
responsables des offres ; saisie : direction et responsables des offres (`GI-Offres`)."""

from __future__ import annotations

import mimetypes

from django.conf import settings
from django.contrib import admin, messages
from django.db.models import Count, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from administratif.models import TypePiece
from administratif.services import PartageIndisponibleError, chemin_absolu
from avis import services
from avis.formulaires import FormulaireAvis, FormulaireBesoin, FormulaireCritere
from avis.models import Avis, BesoinExpert, Critere, Proposition
from experts.models import Expert
from identite.decorateurs import groupe_requis
from moteur.avis.filtres import FiltreInvalideError
from references.models import Mission
from suivi.services import journaliser

SAISIE = (settings.GROUPE_DIRECTION, settings.GROUPE_OFFRES)
CONSULTATION = (*SAISIE, settings.GROUPE_DIRECTION_LECTURE)
FICHIERS = {"avis": ("Avis", "fichier_avis_chemin"), "tdr": ("TDR", "fichier_tdr_chemin")}
LARGES = {
    "objet",
    "observations",
    "lieu_depot",
    "destinataire",
    "fichier_avis_chemin",
    "fichier_tdr_chemin",
}
ECHEANCES = (("a_venir", "à venir"), ("passes", "passés"))


def _peut_saisir(request) -> bool:
    return request.user.dans_groupe(*SAISIE)


@groupe_requis(*CONSULTATION)
def liste(request):
    journaliser(request, "consulter:avis")
    choisis = {k: request.GET.get(k, "").strip() for k in ("q", "type", "statut", "echeance")}
    aujourdhui = timezone.localdate()
    qs = Avis.objects.select_related("maitre_ouvrage", "bailleur")
    qs = qs.annotate(nb_criteres=Count("criteres"))
    if choisis["q"]:
        q = choisis["q"]
        qs = qs.filter(
            Q(reference__icontains=q)
            | Q(objet__icontains=q)
            | Q(maitre_ouvrage__nom__icontains=q)
            | Q(maitre_ouvrage__sigle__icontains=q)
            | Q(bailleur__nom__icontains=q)
            | Q(bailleur__sigle__icontains=q)
        )
    if choisis["type"] in Avis.Type.values:
        qs = qs.filter(type=choisis["type"])
    if choisis["statut"] in Avis.Statut.values:
        qs = qs.filter(statut=choisis["statut"])
    if choisis["echeance"] == "a_venir":
        qs = qs.filter(date_limite__gte=aujourdhui).order_by("date_limite", "pk")
    elif choisis["echeance"] == "passes":
        qs = qs.filter(date_limite__lt=aujourdhui)
    lignes = [(a, (a.date_limite - aujourdhui).days) for a in qs]
    return render(
        request,
        "avis/liste.html",
        {
            **admin.site.each_context(request),
            "titre": "Avis de marchés",
            "lignes": lignes,
            "total": len(lignes),
            "types": Avis.Type.choices,
            "statuts": Avis.Statut.choices,
            "echeances": ECHEANCES,
            **choisis,
            "filtre_actif": any(choisis.values()),
            "peut_saisir": _peut_saisir(request),
        },
    )


def _fichier(a: Avis, quoi: str) -> dict:
    libelle, champ = FICHIERS[quoi]
    chemin = getattr(a, champ)
    existe = None  # inconnu : partage non configuré ou injoignable
    if chemin:
        try:
            existe = chemin_absolu(chemin).is_file()
        except (PartageIndisponibleError, ValueError, OSError):
            existe = None
    return {"quoi": quoi, "libelle": libelle, "chemin": chemin, "existe": existe}


@groupe_requis(*CONSULTATION)
def fiche(request, avis_id: int):
    a = get_object_or_404(
        Avis.objects.select_related("maitre_ouvrage", "bailleur", "cree_par"), pk=avis_id
    )
    journaliser(request, "consulter:avis", str(a.pk))
    criteres = list(a.criteres.all())
    calcules = [c for c in criteres if c.mode != Critere.Mode.MANUEL]
    besoins = a.besoins.exists()
    references = services.references_du_bureau() if calcules or besoins else []
    termes = services.lexique() if calcules else ()
    lignes = []
    for c in criteres:
        apercu, erreur = None, ""
        if c in calcules:
            try:
                apercu = services.apercu(c.filtre, references, a.pays, termes)
            except FiltreInvalideError as e:
                erreur = str(e)
        lignes.append(
            {
                "c": c,
                "filtre": services.filtre_en_clair(c.filtre),
                "apercu": apercu,
                "erreur": erreur,
            }
        )
    exigees = {p.type_id: p for p in a.pieces_exigees.all()}
    types = TypePiece.objects.filter(Q(actif=True) | Q(pk__in=list(exigees)))
    controle = services.controle_pieces(a)
    postes = services.experts_pour(a, references) if besoins else []
    sommaire = services.sommaire(a, controle) if a.type == Avis.Type.AMI else []
    return render(
        request,
        "avis/fiche.html",
        {
            **admin.site.each_context(request),
            "titre": f"{a.type} {a.reference}",
            "a": a,
            "jours": (a.date_limite - timezone.localdate()).days,
            "criteres": lignes,
            "brouillons": sum(1 for c in criteres if c.brouillon),
            "pieces": [(t, exigees.get(t.pk)) for t in types],
            "controle": controle,
            "besoins": postes,
            "sommaire": sommaire,
            "lien_controle": services.lien_controle(a),
            "fichiers": [_fichier(a, quoi) for quoi in FICHIERS],
            "peut_saisir": _peut_saisir(request),
        },
    )


def _dossier(request, avis_id: int, intercalaires_seulement: bool):
    a = get_object_or_404(
        Avis.objects.select_related("maitre_ouvrage", "bailleur"), pk=avis_id, type=Avis.Type.AMI
    )
    quoi = "intercalaires" if intercalaires_seulement else "dossier"
    journaliser(request, "consulter:avis", f"{a.pk} {quoi}")
    d = services.plan_dossier(a, intercalaires_seulement)
    return render(request, "avis/dossier.html", {"a": a, "d": d, "quoi": quoi})


@groupe_requis(*CONSULTATION)
def dossier(request, avis_id: int):
    """La réponse à un AMI, page par page, à imprimer depuis le navigateur (AV14) : couverture,
    sommaire, intercalaires, lettre, listes de références, organigramme ; les pièces du partage
    et les pages manquantes sont marquées à leur place. AMI seulement."""
    return _dossier(request, avis_id, intercalaires_seulement=False)


@groupe_requis(*CONSULTATION)
def intercalaires(request, avis_id: int):
    """Le sommaire puis un intercalaire par page A4, tirés du même plan que le dossier, pour les
    imprimer à part (sur papier de couleur, par exemple). AMI seulement."""
    return _dossier(request, avis_id, intercalaires_seulement=True)


@groupe_requis(*CONSULTATION)
def logo(request):
    """Le logo du bureau, lu sur le partage (jamais écrit) : `LOGO.png` dans `services.LOGOS`."""
    chemin = services.logo_du_bureau()
    if chemin is None:
        raise Http404("pas de logo")
    type_mime = mimetypes.guess_type(chemin.name)[0] or "application/octet-stream"
    return FileResponse(chemin.open("rb"), content_type=type_mime)


@groupe_requis(*CONSULTATION)
def fichier(request, avis_id: int, quoi: str):
    """Ouvre le fichier de l'avis ou des TDR, lu sur le partage (jamais écrit, règle 4)."""
    a = get_object_or_404(Avis, pk=avis_id)
    if quoi not in FICHIERS or not getattr(a, FICHIERS[quoi][1]):
        raise Http404("pas de fichier")
    try:
        chemin = chemin_absolu(getattr(a, FICHIERS[quoi][1]))
    except (PartageIndisponibleError, ValueError) as x:
        raise Http404(str(x)) from x
    if not chemin.is_file():
        raise Http404(f"{chemin.name} introuvable sur le partage")
    journaliser(request, "consulter:fichier_avis", f"{a.pk} {chemin.name}")
    type_mime = mimetypes.guess_type(chemin.name)[0] or "application/octet-stream"
    return FileResponse(chemin.open("rb"), content_type=type_mime, filename=chemin.name)


@groupe_requis(*SAISIE)
def modifier(request, avis_id: int | None = None):
    a = get_object_or_404(Avis, pk=avis_id) if avis_id else None
    formulaire = FormulaireAvis(request.POST or None, instance=a)
    if request.method == "POST" and formulaire.is_valid():
        nouveau = a is None
        a = formulaire.save(commit=False)
        if nouveau:
            a.cree_par = request.user
        a.save()
        journaliser(request, "avis:creer" if nouveau else "avis:modifier", str(a.pk))
        suite = " Pièces exigées par défaut reprises ; saisissez le barème." if nouveau else ""
        messages.success(request, f"{a} enregistré.{suite}")
        return redirect("avis:fiche", avis_id=a.pk)
    return render(
        request,
        "avis/formulaire.html",
        {
            **admin.site.each_context(request),
            "titre": "Nouvel avis" if a is None else f"Modifier {a}",
            "a": a,
            "formulaire": formulaire,
            "larges": LARGES,
        },
    )


@groupe_requis(*SAISIE)
def critere(request, avis_id: int, critere_id: int | None = None):
    """Saisie d'un critère. « Aperçu » montre les références retenues sans rien enregistrer."""
    a = get_object_or_404(Avis, pk=avis_id)
    if critere_id:
        c = get_object_or_404(Critere, pk=critere_id, avis=a)
    else:
        c = Critere(avis=a, ordre=a.criteres.count() + 1)
    formulaire = FormulaireCritere(request.POST or None, instance=c)
    apercu = None
    if request.method == "POST" and formulaire.is_valid():
        if request.POST.get("action") == "apercu":
            apercu = services.apercu(formulaire.instance.filtre, pays_avis=a.pays)
        else:
            c = formulaire.save(commit=False)
            c.brouillon = False  # enregistré par une personne : il compte (AV09)
            c.save()
            journaliser(request, "avis:critere", f"{a.pk} {c.code}")
            messages.success(request, f"Critère {c.code} enregistré.")
            return redirect("avis:fiche", avis_id=a.pk)
    return render(
        request,
        "avis/critere.html",
        {
            **admin.site.each_context(request),
            "titre": f"Critère {c.code}" if c.pk else "Nouveau critère",
            "a": a,
            "c": c,
            "formulaire": formulaire,
            "apercu": apercu,
        },
    )


@require_POST
@groupe_requis(*SAISIE)
def retirer_critere(request, avis_id: int, critere_id: int):
    c = get_object_or_404(Critere, pk=critere_id, avis_id=avis_id)
    journaliser(request, "avis:retirer_critere", f"{avis_id} {c.code}")
    c.delete()
    messages.success(request, f"Critère {c.code} retiré du barème.")
    return redirect("avis:fiche", avis_id=avis_id)


@require_POST
@groupe_requis(*SAISIE)
def pieces(request, avis_id: int):
    a = get_object_or_404(Avis, pk=avis_id)
    ajoutees, retirees = services.regler_pieces(a, request.POST.getlist("pieces"))
    journaliser(request, "avis:pieces", f"{a.pk} +{ajoutees} -{retirees}")
    bilan = f"{ajoutees} ajoutée(s), {retirees} retirée(s)"
    messages.success(request, f"Pièces exigées enregistrées ({bilan}).")
    return redirect("avis:fiche", avis_id=a.pk)


# -- simulation (AV04) --------------------------------------------------------------------------
VERDICTS = {"eligible": "éligible", "incertain": "incertain", "non_eligible": "non éligible"}
CANDIDATES_AFFICHEES = 40
PIECES_EN_JEU_AFFICHEES = 60


@groupe_requis(*CONSULTATION)
def simulation(request, avis_id: int):
    """La note de l'avis, calculée à chaque affichage ; « Enregistrer » garde la sélection."""
    a = get_object_or_404(Avis, pk=avis_id)
    journaliser(request, "consulter:simulation_avis", str(a.pk))
    try:
        resultat = services.calculer(a)
    except FiltreInvalideError as e:
        messages.error(request, f"Un filtre du barème ne se lit plus : {e}")
        return redirect("avis:fiche", avis_id=a.pk)
    criteres = {c.code: c for c in a.criteres.all()}
    ids = {x.reference.ident for rc in resultat.criteres for x in rc.candidates}
    libelles = {m.pk: m.libelle for m in Mission.objects.filter(pk__in=ids)}
    en_jeu = {(p.critere, p.code): p.points for p in resultat.en_jeu}
    blocs = []
    for rc in resultat.criteres:
        c = criteres[rc.critere.code]
        retenues = {x.reference.ident for x in rc.retenues}
        lignes = [
            {
                "x": x,
                "libelle": libelles.get(x.reference.ident, ""),
                "retenue": x.reference.ident in retenues,
                "en_jeu": en_jeu.get((c.code, x.reference.code)),
            }
            for x in rc.candidates[:CANDIDATES_AFFICHEES]
        ]
        exclues = c.selections.filter(retenue_par__isnull=False, retenue=False)
        blocs.append(
            {
                "c": c,
                "rc": rc,
                "lignes": lignes,
                "autres": max(len(rc.candidates) - CANDIDATES_AFFICHEES, 0),
                "exclues": exclues.select_related("mission"),
            }
        )
    codes = {p.code for p in resultat.en_jeu}
    intitules = dict(Mission.objects.filter(code__in=codes).values_list("code", "intitule_court"))
    pieces = [
        {"p": p, "intitule": intitules.get(p.code, "")}
        for p in resultat.en_jeu[:PIECES_EN_JEU_AFFICHEES]
    ]
    return render(
        request,
        "avis/simulation.html",
        {
            **admin.site.each_context(request),
            "titre": f"Simulation {a.type} {a.reference}",
            "a": a,
            "resultat": resultat,
            "verdict": VERDICTS.get(resultat.verdict or "", ""),
            "blocs": blocs,
            "pieces": pieces,
            "autres_pieces": max(len(resultat.en_jeu) - PIECES_EN_JEU_AFFICHEES, 0),
            "peut_saisir": _peut_saisir(request),
        },
    )


@require_POST
@groupe_requis(*SAISIE)
def enregistrer_simulation(request, avis_id: int):
    a = get_object_or_404(Avis, pk=avis_id)
    try:
        resultat = services.calculer(a)
    except FiltreInvalideError as e:
        messages.error(request, f"Un filtre du barème ne se lit plus : {e}")
        return redirect("avis:fiche", avis_id=a.pk)
    services.enregistrer_simulation(a, resultat)
    notes = f"{resultat.note_sure.normalize():f} / {resultat.note_possible.normalize():f}"
    journaliser(request, "avis:simulation", f"{a.pk} {notes}")
    messages.success(request, f"Simulation enregistrée : note sûre / possible {notes}.")
    return redirect("avis:simulation", avis_id=a.pk)


@require_POST
@groupe_requis(*SAISIE)
def choix(request, avis_id: int):
    """Forcer ou exclure une référence pour un critère, avec un motif, ou annuler ce choix."""
    a = get_object_or_404(Avis, pk=avis_id)
    critere_id = request.POST.get("critere", "")
    if not critere_id.isdigit():
        raise Http404("critère inconnu")
    c = get_object_or_404(Critere, pk=int(critere_id), avis=a)
    code = request.POST.get("code", "").strip().upper()
    decision = request.POST.get("decision", "")
    motif = request.POST.get("motif", "").strip()[:300]
    m = Mission.objects.filter(code=code).first()
    if m is None:
        messages.error(request, f"Référence introuvable : {code or '(vide)'}.")
    elif decision != "annuler" and not motif:
        messages.error(request, "Indiquez le motif : il reste avec le choix.")
    else:
        try:
            services.choisir(c, m, decision, motif, request.user)
        except ValueError as e:
            messages.error(request, str(e))
        else:
            journaliser(request, f"avis:{decision}", f"{a.pk} {c.code} {m.code}")
            fait = {"forcer": "forcée", "exclure": "exclue", "annuler": "rendue au calcul"}
            messages.success(request, f"{m.code} {fait[decision]} pour le critère {c.code}.")
    return redirect("avis:simulation", avis_id=a.pk)


# -- experts demandés (AV06) ----------------------------------------------------------------------
@groupe_requis(*SAISIE)
def besoin(request, avis_id: int, besoin_id: int | None = None):
    a = get_object_or_404(Avis, pk=avis_id)
    if besoin_id:
        b = get_object_or_404(BesoinExpert, pk=besoin_id, avis=a)
    else:
        b = BesoinExpert(avis=a, ordre=a.besoins.count() + 1)
    formulaire = FormulaireBesoin(request.POST or None, instance=b)
    if request.method == "POST" and formulaire.is_valid():
        b = formulaire.save()
        journaliser(request, "avis:besoin", f"{a.pk} {b.poste}"[:300])
        messages.success(request, f"Poste « {b.poste} » enregistré.")
        return redirect("avis:fiche", avis_id=a.pk)
    return render(
        request,
        "avis/besoin.html",
        {
            **admin.site.each_context(request),
            "titre": b.poste if b.pk else "Nouveau poste demandé",
            "a": a,
            "b": b,
            "formulaire": formulaire,
        },
    )


@require_POST
@groupe_requis(*SAISIE)
def retenir(request, avis_id: int, besoin_id: int):
    b = get_object_or_404(BesoinExpert, pk=besoin_id, avis_id=avis_id)
    ident = request.POST.get("expert", "")
    b.expert_retenu = Expert.objects.filter(pk=int(ident)).first() if ident.isdigit() else None
    b.save(update_fields=["expert_retenu"])
    journaliser(request, "avis:retenir_expert", f"{avis_id} {b.poste} {ident}"[:300])
    messages.success(request, f"{b.poste} : {b.expert_retenu or 'aucun expert retenu'}.")
    return redirect("avis:fiche", avis_id=avis_id)


@require_POST
@groupe_requis(*SAISIE)
def retirer_besoin(request, avis_id: int, besoin_id: int):
    b = get_object_or_404(BesoinExpert, pk=besoin_id, avis_id=avis_id)
    journaliser(request, "avis:retirer_besoin", f"{avis_id} {b.poste}"[:300])
    b.delete()
    messages.success(request, f"Poste « {b.poste} » retiré.")
    return redirect("avis:fiche", avis_id=avis_id)


# -- propositions à valider (AV08) ---------------------------------------------------------------
def pastille_propositions(request) -> int | None:
    """Pastille du menu : propositions d'avis à valider (direction, offres, consultation)."""
    u = getattr(request, "user", None)
    if not (u and getattr(u, "is_authenticated", False) and u.dans_groupe(*CONSULTATION)):
        return None
    return services.a_valider() or None


@groupe_requis(*CONSULTATION)
def propositions(request):
    journaliser(request, "consulter:propositions_avis")
    a_valider = Proposition.objects.filter(statut=Proposition.Statut.A_VALIDER)
    decidees = Proposition.objects.exclude(statut=Proposition.Statut.A_VALIDER)
    return render(
        request,
        "avis/propositions.html",
        {
            **admin.site.each_context(request),
            "titre": "Propositions d'avis",
            "a_valider": a_valider.order_by("-proposee_le"),
            "decidees": decidees.select_related("avis_cree").order_by("-decide_le")[:30],
        },
    )


@groupe_requis(*CONSULTATION)
def proposition(request, proposition_id: int):
    """Les champs extraits à gauche, le formulaire de l'avis prérempli à droite : on corrige,
    puis on accepte (l'avis est créé) ou on rejette avec un motif (règle 3)."""
    p = get_object_or_404(Proposition.objects.select_related("avis_cree"), pk=proposition_id)
    ouverte = p.statut == Proposition.Statut.A_VALIDER
    formulaire = FormulaireAvis(initial=services.initiaux(p)) if ouverte else None
    if request.method == "POST":
        if not _peut_saisir(request):
            return render(request, "identite/refus.html", {"groupes": SAISIE}, status=403)
        action = request.POST.get("action", "")
        try:
            if action == "rejeter":
                services.rejeter(p, request.POST.get("motif", ""), request.user)
                journaliser(request, "avis:rejeter_proposition", str(p.pk))
                messages.success(request, f"Proposition {p.pk} rejetée.")
                return redirect("avis:propositions")
            formulaire = FormulaireAvis(request.POST)
            if formulaire.is_valid():
                a = services.accepter(p, formulaire, request.user)
                journaliser(request, "avis:accepter_proposition", f"{p.pk} -> {a.pk}")
                messages.success(request, f"{a} créé depuis la proposition {p.pk}.")
                return redirect("avis:fiche", avis_id=a.pk)
        except ValueError as e:
            messages.error(request, f"{str(e)[:1].upper()}{str(e)[1:]}.")
            return redirect("avis:proposition", proposition_id=p.pk)
    return render(
        request,
        "avis/proposition.html",
        {
            **admin.site.each_context(request),
            "titre": f"Proposition {p.pk}",
            "p": p,
            "ouverte": ouverte,
            "extraits": sorted((p.champs_extraits or {}).items()),
            "formulaire": formulaire,
            "larges": LARGES,
            "peut_saisir": _peut_saisir(request),
        },
    )
