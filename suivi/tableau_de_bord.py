"""Indicateurs de l'accueil de l'administration (Unfold, DASHBOARD_CALLBACK).

Avant-goût de T02 (vue d'ensemble) : quatre chiffres lus en base, sans calcul métier ici.
Chaque carte mène à l'écran qui détaille le chiffre (l'admin n'a plus de page Segments ni Postes).
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

from django.db.models import Q, Sum
from django.urls import reverse
from django.utils import timezone

from suivi.models import Dossier, Poste, Segment


def _heures(secondes) -> str:
    s = int(secondes or 0)
    return f"{s // 3600} h {s % 3600 // 60:02d}"


def contexte(request, context: dict) -> dict:
    maintenant = timezone.now()
    debut_jour = timezone.make_aware(datetime.combine(timezone.localdate(), time.min))
    du_jour = Segment.objects.filter(debut__gte=debut_jour, etat=Segment.Etat.ACTIF)
    context["indicateurs"] = [
        {
            "titre": "Temps actif aujourd'hui",
            "valeur": _heures(du_jour.aggregate(s=Sum("duree_s"))["s"]),
            "icone": "schedule",
            "lien": reverse("suivi:journee"),
        },
        {
            "titre": "Personnes actives aujourd'hui",
            "valeur": du_jour.values("employe").distinct().count(),
            "icone": "groups",
            "lien": reverse("suivi:employes"),
        },
        {
            "titre": "À classer (7 derniers jours)",
            "valeur": Segment.objects.filter(
                statut_classement=Segment.StatutClassement.A_CLASSER,
                debut__gte=debut_jour - timedelta(days=7),
            ).count(),
            "icone": "inbox",
            "lien": reverse("suivi:a_classer"),
        },
        {
            "titre": "Postes muets depuis 24 h",
            "valeur": Poste.objects.filter(
                Q(dernier_envoi__lt=maintenant - timedelta(hours=24)) | Q(dernier_envoi=None)
            ).count(),
            "icone": "desktop_access_disabled",
            "lien": reverse("suivi:postes"),
        },
    ]
    context["dossiers_a_valider"] = Dossier.objects.filter(statut=Dossier.Statut.DETECTE).count()
    return context
