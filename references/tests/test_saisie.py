"""Revue d'une référence (passage à « vérifiée ») et création d'une référence avec son code."""

from __future__ import annotations

from html import unescape

import pytest
from django.test import override_settings

from references import services
from references.models import Mission
from references.tests.test_references import DIR, IIS, LISTE, VUE
from referentiel.models import Client, Domaine
from suivi.models import JournalAcces

pytestmark = pytest.mark.django_db


@pytest.fixture
def liste():
    return services.importer(services.lire_csv(LISTE))


def html(r) -> str:
    assert r.status_code == 200, r.status_code
    return unescape(r.content.decode())


def donnees(m: Mission, **changes) -> dict:
    base = {
        "intitule": m.intitule,
        "intitule_court": m.intitule_court,
        "domaine": m.domaine_id,
        "nature": m.nature,
        "client": m.client_id or "",
        "pays": m.pays,
        "annee": m.annee or "",
        "devise": m.devise,
        "role": m.role,
    }
    base.update(changes)
    return {k: v for k, v in base.items() if v is not None}


@override_settings(**IIS)
def test_revoir_et_verifier(client, liste):
    m = Mission.objects.get(code="GIC-AEP-CTR-003")
    page = html(client.get("/references/GIC-AEP-CTR-003/modifier", **DIR))
    assert "Revoir GIC-AEP-CTR-003" in page and "ne change pas" in page
    env = Domaine.objects.get(code="ENV")
    r = client.post(
        "/references/GIC-AEP-CTR-003/modifier",
        donnees(
            m,
            numero_contrat="N° 12/2020/SOMAGEP",
            domaines_secondaires=[env.pk, m.domaine_id],  # le principal est retiré des secondaires
            date_debut="2020-03-01",
            date_fin="2021-02-28",
            annee="",
            role="chef_de_file",
            part_bureau="60",
            intervention="realisation",
            client_nouveau="Société malienne de gestion de l'eau potable",
            action="verifiee",
        ),
        follow=True,
        **DIR,
    )
    assert "GIC-AEP-CTR-003 enregistrée (vérifiée)" in html(r)
    m.refresh_from_db()
    assert m.statut_verification == "verifiee" and m.annee == 2020 and m.part_bureau == 60
    assert list(m.domaines_secondaires.values_list("code", flat=True)) == ["ENV"]
    assert m.client.nom.startswith("Société malienne") and Client.objects.count() == 4
    assert JournalAcces.objects.filter(action="reference:revue").exists()
    # remettre « à vérifier », enregistrer simplement
    client.post("/references/GIC-AEP-CTR-003/modifier", donnees(m, action="a_verifier"), **DIR)
    m.refresh_from_db()
    assert m.statut_verification == "a_verifier"
    client.post("/references/GIC-AEP-CTR-003/modifier", donnees(m, pays="Niger"), **DIR)
    m.refresh_from_db()
    assert m.pays == "Niger" and m.statut_verification == "a_verifier"


@override_settings(**IIS)
def test_revue_refus(client, liste):
    m = Mission.objects.get(code="GIC-AEP-CTR-003")
    page = html(
        client.post(
            "/references/GIC-AEP-CTR-003/modifier",
            donnees(m, date_debut="2021-01-01", date_fin="2020-01-01", part_bureau="150"),
            **DIR,
        )
    )
    assert "La fin précède le début" in page and "entre 0 et 100" in page
    absorbee = Mission.objects.get(code="GIC-HYD-ETU-032")
    r = client.post(
        "/references/GIC-HYD-ETU-032/modifier",
        donnees(absorbee, action="verifiee"),
        follow=True,
        **DIR,
    )
    assert "Une fiche absorbée ne se vérifie pas" in html(r)
    assert "Fiche absorbée par GIC-HYD-ETU-033" in html(r)
    assert client.get("/references/GIC-AEP-CTR-003/modifier", **VUE).status_code == 403
    assert "Revoir la fiche" not in html(client.get("/references/GIC-AEP-CTR-003/", **VUE))
    assert "Revoir la fiche" in html(client.get("/references/GIC-AEP-CTR-003/", **DIR))


@override_settings(**IIS)
def test_nouvelle_reference_numero_suivant(client, liste):
    page = html(client.get("/references/nouvelle", **DIR))
    assert "Voir le code proposé" in page and "Code proposé" not in page
    page = html(client.get("/references/nouvelle", {"domaine": "HYD", "nature": "ETU"}, **DIR))
    assert "GIC-HYD-ETU-034" in page  # après 033 ; la fiche absorbée 032 compte aussi
    page = html(
        client.post(
            "/references/nouvelle", {"domaine": "HYD", "nature": "ETU", "intitule": " "}, **DIR
        )
    )
    assert "Indiquez l'intitulé" in page
    r = client.post(
        "/references/nouvelle",
        {"domaine": "HYD", "nature": "ETU", "intitule": "Étude APD du seuil de Kalaban"},
        follow=True,
        **DIR,
    )
    assert "Code GIC-HYD-ETU-034 attribué" in html(r)
    m = Mission.objects.get(code="GIC-HYD-ETU-034")
    assert m.statut_code == "nouveau" and m.statut_verification == "a_verifier"
    assert "GIC-HYD-ETU-035" in html(
        client.get("/references/nouvelle", {"domaine": "HYD", "nature": "ETU"}, **DIR)
    )
    assert "Code proposé" not in html(
        client.get("/references/nouvelle", {"domaine": "HYD", "nature": "X"}, **DIR)
    )
    assert client.get("/references/nouvelle", **VUE).status_code == 403
    assert "Nouvelle référence" in html(client.get("/references/", **DIR))
