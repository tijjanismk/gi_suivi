"""T08 — téléchargement du classeur Excel de la période (direction et consultation)."""

from django.http import HttpResponse

from identite.decorateurs import consultation_requise
from suivi import export
from suivi.services import journaliser
from suivi.vues.periode import selection_de

TYPE_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@consultation_requise
def classeur(request):
    selection = selection_de(request.GET)
    p = selection.periode
    journaliser(request, "exporter:excel", f"{p.debut}..{p.fin}")
    reponse = HttpResponse(export.octets(p), content_type=TYPE_XLSX)
    reponse["Content-Disposition"] = f'attachment; filename="{export.nom_fichier(p)}"'
    return reponse
