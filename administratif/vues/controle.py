"""Écran 4 des maquettes, première étape (AD07) : contrôle des pièces à une date limite de dépôt,
sans le module avis. La personne saisit la date limite et coche les pièces que l'avis demande en
plus ; chaque pièce est jugée à cette date, jamais à la date du jour (ADR 0010, § 6).
L'assemblage du dossier PDF (pages en filigrane) viendra avec son propre ADR (dépendance PDF).
"""

from __future__ import annotations

from datetime import timedelta

from django.contrib import admin
from django.shortcuts import render
from django.utils import timezone

from administratif import services
from administratif.models import TypePiece
from administratif.vues.registre import lire_date
from identite.decorateurs import consultation_requise
from suivi.services import journaliser

DELAI_PAR_DEFAUT = timedelta(days=14)


@consultation_requise
def controle(request):
    aujourd_hui = timezone.localdate()
    date_limite = lire_date(request.GET.get("date")) or aujourd_hui + DELAI_PAR_DEFAUT
    facultatives = TypePiece.objects.filter(actif=True, exigee_par_defaut=False)
    en_plus = [c for c in request.GET.getlist("avec") if facultatives.filter(code=c).exists()]
    avis = request.GET.get("avis", "").strip()[:200]
    journaliser(request, "consulter:controle_pieces", f"{date_limite} {' '.join(en_plus)}")
    lignes = services.controle_a_la_date(date_limite, en_plus)
    a_regler = [x for x in lignes if x.a_regler]
    return render(
        request,
        "administratif/controle.html",
        {
            **admin.site.each_context(request),
            "titre": "Contrôle des pièces avant un dépôt",
            "lignes": lignes,
            "a_regler": len(a_regler),
            "valides": len(lignes) - len(a_regler),
            "expirations": services.expirations_d_ici(date_limite, lignes),
            "date_limite": date_limite,
            "aujourd_hui": aujourd_hui,
            "passe": date_limite < aujourd_hui,
            "facultatives": facultatives,
            "en_plus": en_plus,
            "avis": avis,
            "peut_agir": request.user.direction,
        },
    )
