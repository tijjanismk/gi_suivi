"""AV12 (ADR 0021 et 0022) — la décision « on répond ou pas » : motivée, prise par la
direction ou sa délégation, gardée avec la note du moment, visible sur la fiche, seul chemin
vers le statut."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from html import unescape

import pytest
from django.forms.models import model_to_dict
from django.test import override_settings
from django.utils import timezone
from freezegun import freeze_time

from avis import services
from avis.admin import FormulaireAvisAdmin
from avis.models import Avis, DecisionAvis
from identite.models import Utilisateur
from moteur.avis.decision import DecisionInvalideError
from suivi.models import JournalAcces

pytestmark = pytest.mark.django_db
IIS = {"IDENTITE_SOURCE": "iis", "IDENTITE_LECTEUR_GROUPES": "avis.tests.test_decision.groupes"}
DIR = {"REMOTE_USER": "GICONSEILS\\directrice"}
DELEGUE = {"REMOTE_USER": "GICONSEILS\\i.bouba"}
OFFRES = {"REMOTE_USER": "GICONSEILS\\o.hassane"}
VUE = {"REMOTE_USER": "GICONSEILS\\visionneuse"}
MOTIF = "Lots A et B dans notre métier, 26 références de contrôle ; QHSE à renforcer."


def groupes(login: str) -> list[str]:
    return {
        "giconseils\\directrice": ["GI-Direction"],
        "giconseils\\i.bouba": ["GI-Decision-Avis", "GI-Offres"],
        "giconseils\\o.hassane": ["GI-Offres"],
        "giconseils\\visionneuse": ["GI-Direction-Lecture"],
    }.get(login, [])


def html(r) -> str:
    return unescape(r.content.decode())


@pytest.fixture(autouse=True)
def le_20_octobre():
    with freeze_time("2026-10-20 10:12"), override_settings(**IIS):
        yield


@pytest.fixture
def unicef():
    return Avis.objects.create(
        reference="LRPS-MLI-2026-9206428",
        objet="Suivi et contrôle des forages équipés d'AES, des latrines et du génie civil",
        type=Avis.Type.DP,
        statut=Avis.Statut.EN_ANALYSE,
        date_limite=date(2026, 10, 28),
        note_sure=Decimal("0"),
        note_possible=Decimal("25"),
        simulee_le=timezone.make_aware(datetime(2026, 10, 19, 17, 30)),
    )


def test_la_decision_est_gardee_avec_la_note_du_moment(client, unicef):
    r = client.post(f"/avis/{unicef.pk}/decider", {"decision": "go", "motif": MOTIF}, **DIR)
    assert r.status_code == 302 and r.url == f"/avis/{unicef.pk}/"
    d = DecisionAvis.objects.get()
    assert (d.decision, d.motif, d.qualite, d.statut_avant) == (
        "go",
        MOTIF,
        "direction",
        "en_analyse",
    )
    assert d.par.login_windows == "giconseils\\directrice"
    assert (d.note_sure, d.note_possible) == (Decimal("0"), Decimal("25"))
    unicef.refresh_from_db()
    assert unicef.statut == "go" and unicef.decision_en_cours == d
    assert JournalAcces.objects.filter(action="avis:decider", cible=f"{unicef.pk} go").exists()

    page = html(client.get(f"/avis/{unicef.pk}/", **DIR))
    assert "On répond" in page and "décision du 20/10/2026 à 10:12" in page
    assert MOTIF in page and "(direction)" in page
    assert "Note à ce moment : sûre 0, possible 25 (simulation du 19/10/2026 17:30)" in page
    assert "Revoir la décision" in page


@pytest.mark.parametrize("motif", ["", "   "])
def test_une_decision_sans_motif_est_refusee(client, unicef, motif):
    r = client.post(f"/avis/{unicef.pk}/decider", {"decision": "go", "motif": motif}, **DIR)
    page = html(r)
    assert r.status_code == 200 and 'id="form-decision"' in page
    assert "Indiquez pourquoi vous décidez de répondre ou non." in page
    assert not DecisionAvis.objects.exists()
    unicef.refresh_from_db()
    assert unicef.statut == "en_analyse"


def test_la_delegation_revoit_la_decision_et_l_historique_reste(client, unicef):
    client.post(f"/avis/{unicef.pk}/decider", {"decision": "go", "motif": MOTIF}, **DIR)
    revue = "TDR lus : le lot A est réservé aux entreprises du génie civil."
    with freeze_time("2026-10-22 08:00"):
        r = client.post(
            f"/avis/{unicef.pk}/decider", {"decision": "no_go", "motif": revue}, **DELEGUE
        )
    assert r.status_code == 302
    en_cours, ancienne = DecisionAvis.objects.all()  # la plus récente d'abord
    assert (en_cours.decision, en_cours.qualite, en_cours.statut_avant) == (
        "no_go",
        "delegation",
        "go",
    )
    assert ancienne.decision == "go" and ancienne.motif == MOTIF
    page = html(client.get(f"/avis/{unicef.pk}/", **DIR))
    assert "On ne répond pas" in page and "(délégation de la direction)" in page
    assert "Décisions précédentes (1)" in page and MOTIF in page


def test_la_meme_decision_ne_se_repete_pas(client, unicef):
    client.post(f"/avis/{unicef.pk}/decider", {"decision": "go", "motif": MOTIF}, **DIR)
    page = html(
        client.post(f"/avis/{unicef.pk}/decider", {"decision": "go", "motif": "Bis"}, **DIR)
    )
    assert "déjà la décision en cours" in page and DecisionAvis.objects.count() == 1


def test_ni_les_offres_ni_la_consultation_ne_decident(client, unicef):
    for qui in (OFFRES, VUE):
        r = client.post(f"/avis/{unicef.pk}/decider", {"decision": "go", "motif": MOTIF}, **qui)
        assert r.status_code == 403
        page = html(client.get(f"/avis/{unicef.pk}/", **qui))
        assert 'id="form-decision"' not in page
        assert "La direction ou sa délégation décide ici" in page
    assert not DecisionAvis.objects.exists()
    offres = Utilisateur.objects.get(login_windows="giconseils\\o.hassane")
    with pytest.raises(DecisionInvalideError, match="Seules la direction et sa délégation"):
        services.decider(unicef, "go", MOTIF, offres)


def test_pas_de_decision_apres_le_depot(client, unicef):
    Avis.objects.filter(pk=unicef.pk).update(statut=Avis.Statut.DEPOSE)
    assert 'id="form-decision"' not in html(client.get(f"/avis/{unicef.pk}/", **DIR))
    url = f"/avis/{unicef.pk}/decider"
    r = client.post(url, {"decision": "no_go", "motif": MOTIF}, follow=True, **DIR)
    assert "avant le dépôt" in html(r) and not DecisionAvis.objects.exists()


def test_une_decision_sans_simulation(client):
    a = Avis.objects.create(
        reference="AMI-2026-01", objet="Études", type=Avis.Type.AMI, date_limite=date(2026, 11, 30)
    )
    client.post(f"/avis/{a.pk}/decider", {"decision": "no_go", "motif": "Hors métier"}, **DIR)
    d = DecisionAvis.objects.get()
    assert d.statut_avant == "recu" and d.note_sure is None and d.simulee_le is None
    assert "Pas de simulation à la date de la décision" in html(client.get(f"/avis/{a.pk}/", **DIR))


def test_le_formulaire_de_l_avis_ne_pose_pas_la_decision(client, unicef):
    donnees = {
        **{k: v for k, v in model_to_dict(unicef).items() if v is not None},
        "date_limite": "2026-10-28",
        "statut": "go",
    }
    page = html(client.post(f"/avis/{unicef.pk}/modifier", donnees, **DIR))
    assert "se décident depuis la fiche de l'avis" in page
    unicef.refresh_from_db()
    assert unicef.statut == "en_analyse"

    # une fois décidé, l'avis se modifie sans toucher à la décision, et passe au dépôt
    services.decider(
        unicef, "go", MOTIF, Utilisateur.objects.get(login_windows="giconseils\\directrice")
    )
    for statut in ("go", "depose"):
        r = client.post(f"/avis/{unicef.pk}/modifier", {**donnees, "statut": statut}, **DIR)
        assert r.status_code == 302
    unicef.refresh_from_db()
    assert unicef.statut == "depose" and DecisionAvis.objects.count() == 1


def test_l_administration_ne_pose_pas_la_decision(unicef):
    donnees = {**model_to_dict(unicef), "statut": "no_go"}
    formulaire = FormulaireAvisAdmin(data=donnees, instance=unicef)
    assert not formulaire.is_valid()
    assert "se décident depuis la fiche" in str(formulaire.errors["statut"])
