"""Écran 3 des maquettes (AD04) : déposer une nouvelle version d'une pièce.

1. La personne pose le PDF scanné dans le dossier du type sur le partage.
2. L'écran liste les fichiers du dossier pas encore enregistrés ; les doublons (même contenu
   qu'un autre fichier, ou qu'une version déjà enregistrée) ne sont pas sélectionnables.
3. Elle saisit la date d'émission ; l'échéance est proposée par le moteur, puis confirmée ou
   corrigée (« Calculer l'échéance », puis « Enregistrer »).
"""

from __future__ import annotations

from django.conf import settings
from django.contrib import admin, messages
from django.shortcuts import redirect, render

from administratif import services
from administratif.models import TypePiece
from administratif.vues.registre import lire_date
from identite.decorateurs import groupe_requis
from suivi.services import journaliser


@groupe_requis(settings.GROUPE_DIRECTION)
def deposer(request):
    donnees = request.POST if request.method == "POST" else request.GET
    types = TypePiece.objects.filter(actif=True)
    type_piece = types.filter(code=donnees.get("type", "")).first()
    contexte = {
        **admin.site.each_context(request),
        "titre": "Déposer une nouvelle version",
        "types": types,
        "t": type_piece,
        "fichiers": [],
        "choisi": donnees.get("empreinte", ""),
        "date_emission": donnees.get("date_emission", ""),
        "valide_jusqu_au": donnees.get("valide_jusqu_au", ""),
        "numero": donnees.get("numero", ""),
        "erreur_partage": "",
        "proposition": None,
    }
    if type_piece is None:
        return render(request, "administratif/depot.html", contexte)
    try:
        fichiers = services.fichiers_du_dossier(type_piece)
    except (services.PartageIndisponibleError, OSError) as e:
        contexte["erreur_partage"] = str(e)
        return render(request, "administratif/depot.html", contexte)
    contexte["fichiers"] = fichiers
    enregistrables = [f for f in fichiers if f.enregistrable]
    if not contexte["choisi"] and enregistrables:
        contexte["choisi"] = enregistrables[0].empreinte
    courante = services.registre(types=[type_piece])[0].version
    contexte["courante"] = courante
    if request.method != "POST":
        return render(request, "administratif/depot.html", contexte)

    fichier = next((f for f in enregistrables if f.empreinte == contexte["choisi"]), None)
    date_emission = lire_date(contexte["date_emission"])
    valide_jusqu_au = lire_date(contexte["valide_jusqu_au"])
    if fichier is None:
        messages.error(request, "Choisissez un fichier nouveau du dossier.")
        return render(request, "administratif/depot.html", contexte)
    if request.POST.get("nouveau_scan") and request.POST.get("action") == "enregistrer":
        try:
            version = services.enregistrer_nouveau_scan(type_piece, fichier, request.user)
        except ValueError as e:
            messages.error(request, str(e))
            return render(request, "administratif/depot.html", contexte)
        journaliser(request, "piece:nouveau_scan", f"{type_piece.code} {version.chemin}")
        messages.success(
            request,
            f"Nouveau scan enregistré pour la version du {version.date_emission:%d/%m/%Y} ; "
            "l'ancien scan est dans l'historique.",
        )
        return redirect("administratif:fiche", code=type_piece.code)
    if date_emission is None:
        messages.error(request, "Indiquez la date d'émission écrite sur le document.")
        return render(request, "administratif/depot.html", contexte)
    permanente = type_piece.regle_validite == TypePiece.Regle.PERMANENTE
    if request.POST.get("action") == "proposer" or (valide_jusqu_au is None and not permanente):
        try:
            proposition = type_piece.date_de_fin(date_emission)
        except ValueError:
            proposition = None
        contexte["proposition"] = proposition
        contexte["valide_jusqu_au"] = proposition.isoformat() if proposition else ""
        if permanente:
            messages.info(request, "Pièce permanente : pas d'échéance. Vérifiez puis enregistrez.")
        elif proposition:
            messages.info(
                request,
                f"Échéance proposée : {type_piece.regle_texte}. Corrigez-la si le document porte "
                "une autre date, puis enregistrez.",
            )
        else:
            messages.warning(
                request, "Saisissez la date de fin de validité écrite sur le document."
            )
        return render(request, "administratif/depot.html", contexte)
    try:
        version = services.enregistrer_version(
            type_piece,
            fichier,
            date_emission,
            None if permanente else valide_jusqu_au,
            contexte["numero"],
            request.user,
        )
    except ValueError as e:
        messages.error(request, str(e))
        return render(request, "administratif/depot.html", contexte)
    journaliser(request, "piece:deposer", f"{type_piece.code} {version.chemin}")
    messages.success(
        request,
        f"Version du {version.date_emission:%d/%m/%Y} enregistrée"
        + (
            f", valide jusqu'au {version.valide_jusqu_au:%d/%m/%Y}."
            if version.valide_jusqu_au
            else "."
        ),
    )
    return redirect("administratif:fiche", code=type_piece.code)
