from datetime import date, datetime, timedelta
from io import StringIO
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from suivi.management.commands.suivi_purger import limite_retention, moins_des_mois
from suivi.models import DemandeRecalcul, JournalAcces, Parametre, Poste, Segment

pytestmark = pytest.mark.django_db


def segment(employe, poste, debut):
    return Segment.objects.create(
        employe=employe,
        poste=poste,
        debut=debut,
        fin=debut + timedelta(minutes=5),
        duree_s=300,
        etat="ACTIF",
        application="x",
        lot_id=uuid4(),
    )


def test_moins_des_mois():
    assert moins_des_mois(date(2026, 10, 8), 24) == date(2024, 10, 8)
    assert moins_des_mois(date(2026, 3, 31), 1) == date(2026, 2, 28)
    assert moins_des_mois(date(2026, 1, 15), 13) == date(2024, 12, 15)


def test_limite_retention_lit_le_parametre():
    assert limite_retention(date(2026, 10, 8)).date() == date(2024, 10, 8)
    Parametre.objects.filter(cle="retention_mois").update(valeur=6)
    assert limite_retention(date(2026, 10, 8)).date() == date(2026, 4, 8)


def test_purge_supprime_au_dela_de_la_retention_et_rien_d_autre(employes, postes):
    limite = limite_retention()
    vieux = segment(employes[0], postes[0], limite - timedelta(days=1))
    recent = segment(employes[0], postes[0], limite + timedelta(days=1))
    journal = JournalAcces.objects.create(login="x", action="y", horodatage=timezone.now())
    JournalAcces.objects.filter(pk=journal.pk).update(
        horodatage=timezone.now() - timedelta(days=3000)
    )
    vieille_demande = DemandeRecalcul.objects.create(motif="ancienne")
    DemandeRecalcul.objects.filter(pk=vieille_demande.pk).update(
        traitee_le=timezone.now() - timedelta(days=100)
    )
    en_attente = DemandeRecalcul.objects.create(motif="en attente")

    sortie = StringIO()
    call_command("suivi_purger", "--simuler", stdout=sortie)
    assert "1 segments à supprimer" in sortie.getvalue() and Segment.objects.count() == 2

    sortie = StringIO()
    call_command("suivi_purger", stdout=sortie)
    assert "1 segments supprimés" in sortie.getvalue()
    assert not Segment.objects.filter(pk=vieux.pk).exists()
    assert Segment.objects.filter(pk=recent.pk).exists()
    assert JournalAcces.objects.filter(pk=journal.pk).exists()  # jamais purgé
    assert not DemandeRecalcul.objects.filter(pk=vieille_demande.pk).exists()
    assert DemandeRecalcul.objects.filter(pk=en_attente.pk).exists()


def test_postes_muets_signale_rouge_et_orange(postes):
    pc1, pc2 = postes
    pc1.dernier_envoi = timezone.now() - timedelta(minutes=10)
    pc1.demarrages_semaine = 12
    pc1.save()  # orange
    # pc2 : jamais vu envoyer → rouge
    sortie = StringIO()
    with pytest.raises(SystemExit) as fin:
        call_command("suivi_postes_muets", stdout=sortie)
    assert fin.value.code == 1
    texte = sortie.getvalue()
    assert "ROUGE  PC-ETUDES-02 : n'a jamais envoyé" in texte
    assert "ORANGE PC-ETUDES-01 : 12 démarrages" in texte
    assert "2 poste(s), 1 rouge(s), 1 orange(s)." in texte


def test_postes_muets_tout_va_bien_code_zero(postes):
    for p in postes:
        p.dernier_envoi = timezone.now()
        p.save()
    sortie = StringIO()
    call_command("suivi_postes_muets", stdout=sortie)  # pas de SystemExit
    assert "0 rouge(s), 0 orange(s)" in sortie.getvalue()


def test_remise_a_zero_des_demarrages(postes):
    Poste.objects.update(demarrages_semaine=7, dernier_envoi=timezone.now())
    sortie = StringIO()
    call_command("suivi_postes_muets", "--remettre-demarrages", stdout=sortie)
    assert "remis à zéro sur 2 poste(s)" in sortie.getvalue()
    assert set(Poste.objects.values_list("demarrages_semaine", flat=True)) == {0}


@override_settings(IDENTITE_SOURCE="iis")
def test_api_sante_sans_identite(client):
    assert client.get("/api/sante").json() == {"etat": "ok"}
    assert client.get("/sante/").json() == {"etat": "ok"}


def test_segment_du_jour_jamais_purge(employes, postes):
    segment(employes[0], postes[0], timezone.now() - timedelta(hours=1))
    call_command("suivi_purger", stdout=StringIO())
    assert Segment.objects.count() == 1


def test_limite_retention_est_minuit_local():
    limite = timezone.localtime(limite_retention(date(2026, 10, 8)))
    assert (limite.hour, limite.minute) == (0, 0)
    assert isinstance(limite, datetime)
