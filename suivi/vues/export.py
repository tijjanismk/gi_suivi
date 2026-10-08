"""T08 — téléchargement du classeur Excel de la période (direction et consultation)."""

from django.http import HttpResponse

from identite.decorateurs import consultation_requise
from suivi import export
from suivi.models import Dossier
from suivi.services import journaliser
from suivi.vues.periode import selection_de

TYPE_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@consultation_requise
def classeur(request):
    selection = selection_de(request.GET)
    p = selection.periode
    dossier_id = (
        selection.dossier_id
        if selection.dossier_id and Dossier.objects.filter(pk=selection.dossier_id).exists()
        else None
    )
    cible = f"{p.debut}..{p.fin}" + (f" dossier={dossier_id}" if dossier_id else "")
    journaliser(request, "exporter:excel", cible)
    reponse = HttpResponse(export.octets(p, dossier_id), content_type=TYPE_XLSX)
    reponse["Content-Disposition"] = f'attachment; filename="{export.nom_fichier(p)}"'
    return reponse
