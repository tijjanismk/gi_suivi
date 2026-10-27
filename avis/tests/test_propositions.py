"""AV08 (règle 3 de CONTEXT.md) — propositions d'avis : rien n'entre sans validation."""

from __future__ import annotations

import re
from datetime import date
from html import unescape

import pytest
from django.test import override_settings

from administratif.tests.conftest import DIR, IIS, VUE
from avis import services
from avis.models import Avis, Proposition
from referentiel.models import Client

pytestmark = pytest.mark.django_db
EXTRAITS = {
    "reference": "LRPS-MLI-2026-9206428",
    "objet": "Suivi et contrôle des forages équipés d'AES, des latrines et du génie civil",
    "type": "dp",
    "date_limite": "28/10/2026",
    "maitre_ouvrage": "UNICEF",
    "bailleur": "Banque mondiale",
    "pays": "Mali",
}


def html(r) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", unescape(r.content.decode())).split())


@pytest.fixture(autouse=True)
def identite():
    with override_settings(**IIS):
        yield


@pytest.fixture
def unicef():
    return Client.objects.create(nom="UNICEF")


def test_champs_extraits_prets_a_confirmer(unicef):
    p = services.creer_proposition("claude", EXTRAITS, par="GICONSEILS\\essai")
    initial = services.initiaux(p)
    assert initial["type"] == "DP" and initial["date_limite"] == date(2026, 10, 28)
    assert initial["maitre_ouvrage"] == unicef.pk
    assert "Bailleur proposé : Banque mondiale (absent du référentiel)" in initial["observations"]
    assert services.a_valider() == 1
    with pytest.raises(ValueError):
        services.creer_proposition("inconnue", EXTRAITS)


def test_accepter_cree_un_avis_et_un_seul(client, unicef):
    p = services.creer_proposition("claude", EXTRAITS)
    assert "LRPS-MLI-2026-9206428" in html(client.get("/avis/propositions/", **DIR))
    page = unescape(client.get(f"/avis/propositions/{p.pk}", **DIR).content.decode())
    assert 'value="LRPS-MLI-2026-9206428"' in page and "Bailleur proposé" in page
    confirme = {
        "reference": "LRPS-MLI-2026-9206428",
        "objet": EXTRAITS["objet"],
        "type": "DP",
        "statut": "depose",
        "pays": "Mali",
        "date_limite": "2026-10-28",
        "maitre_ouvrage": unicef.pk,
        "action": "accepter",
    }
    r = client.post(f"/avis/propositions/{p.pk}", confirme, **DIR)
    a = Avis.objects.get()
    assert r.status_code == 302 and r.url == f"/avis/{a.pk}/"
    p.refresh_from_db()
    assert p.statut == Proposition.Statut.ACCEPTEE and p.avis_cree == a
    assert p.champs_confirmes["reference"] == "LRPS-MLI-2026-9206428"
    deja = html(client.post(f"/avis/propositions/{p.pk}", confirme, follow=True, **DIR))
    assert "Proposition déjà acceptée." in deja and Avis.objects.count() == 1


def test_rejeter_avec_un_motif(client):
    p = services.creer_proposition("veille", {"reference": "AMI-2026-17"})
    url = f"/avis/propositions/{p.pk}"
    sans = html(client.post(url, {"action": "rejeter"}, follow=True, **DIR))
    assert "Indiquez le motif du rejet." in sans
    assert client.post(url, {"action": "rejeter"}, **VUE).status_code == 403
    client.post(url, {"action": "rejeter", "motif": "hors domaine"}, **DIR)
    p.refresh_from_db()
    assert p.statut == Proposition.Statut.REJETEE and not Avis.objects.exists()
    page = html(client.get(f"/avis/propositions/{p.pk}", **VUE))
    assert "Rejetée le" in page and "hors domaine" in page
