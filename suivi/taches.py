"""Tâches confiées (F01) : le temps passé est calculé, jamais saisi.

Règle de calcul, la même partout (écran direction, « Mes tâches », tests) :
- segments **actifs** de la personne à qui la tâche est confiée ;
- depuis le début du jour de création de la tâche, jusqu'à sa clôture (`faite_le`) si elle est
  faite, sinon jusqu'à maintenant ;
- si la tâche nomme des fichiers (un motif par ligne) : les segments dont le nom ou le chemin
  contient l'un des motifs, quel que soit leur classement (une copie sur le Bureau compte aussi) ;
- sinon : les segments rattachés au dossier de la tâche.
"""

from __future__ import annotations

from datetime import datetime, time
from functools import reduce
from operator import or_

from django.db.models import Q, Sum
from django.utils import timezone

from suivi.models import Segment, Tache
from suivi.vues.frise import duree_courte


def segments_de(tache: Tache, maintenant: datetime | None = None):
    maintenant = maintenant or timezone.now()
    debut = timezone.make_aware(
        datetime.combine(timezone.localtime(tache.creee_le).date(), time.min)
    )
    fin = tache.faite_le if tache.etat == Tache.Etat.FAITE and tache.faite_le else maintenant
    qs = Segment.objects.filter(
        employe_id=tache.personne_id,
        etat=Segment.Etat.ACTIF,
        debut__gte=debut,
        debut__lt=fin,
    )
    motifs = tache.motifs
    if motifs:
        return qs.filter(
            reduce(or_, (Q(fichier__icontains=m) | Q(chemin__icontains=m) for m in motifs))
        )
    return qs.filter(dossier_id=tache.dossier_id)


def temps_tache(tache: Tache, maintenant: datetime | None = None) -> int:
    """Secondes actives passées sur la tâche (règle ci-dessus)."""
    total = segments_de(tache, maintenant).aggregate(s=Sum("duree_s"))["s"]
    return int(total or 0)


def preparer(taches, maintenant: datetime | None = None) -> list[Tache]:
    """Ajoute à chaque tâche ce que les écrans affichent : temps passé, retard."""
    aujourd_hui = timezone.localdate()
    resultat = []
    for t in taches:
        t.temps_s = temps_tache(t, maintenant)
        t.temps = duree_courte(t.temps_s) if t.temps_s else "—"
        t.retard = t.en_retard(aujourd_hui)
        resultat.append(t)
    return resultat
