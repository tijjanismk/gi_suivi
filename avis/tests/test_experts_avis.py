"""AV06 (ADR 0012, 0013) — les experts demandés par un avis : profil, vivier, expert retenu."""

from __future__ import annotations

import re
from datetime import date
from html import unescape

import pytest
from django.test import override_settings

from administratif.tests.conftest import DIR, IIS, VUE
from avis import services
from avis.models import Avis, BesoinExpert
from experts.models import Affectation, Diplome, Expert
from references.models import Mission
from referentiel.models import Domaine

pytestmark = pytest.mark.django_db


def html(r) -> str:
    """Le texte de la page, sans les balises ni les blancs en trop."""
    return " ".join(re.sub(r"<[^>]+>", " ", unescape(r.content.decode())).split())


@pytest.fixture(autouse=True)
def identite():
    with override_settings(**IIS):
        yield


@pytest.fixture
def unicef():
    return Avis.objects.create(
        reference="LRPS-MLI-2026-9206428",
        objet="Suivi et contrôle des forages",
        type=Avis.Type.DP,
        date_limite=date(2026, 10, 28),
    )


@pytest.fixture
def vivier():
    controle = Mission.objects.create(
        code="GIC-AEP-CTR-015",
        domaine=Domaine.objects.get(code="AEP"),
        nature="CTR",
        annee=2019,
        intitule="Contrôle des forages",
    )
    dicko = Expert.objects.create(
        nom="DICKO", prenoms="Oumar", specialite="Génie civil", debut_carriere=2008
    )
    Diplome.objects.create(expert=dicko, intitule="Ingénieur génie civil (BTP)", niveau="bac+5")
    Affectation.objects.create(
        expert=dicko, mission=controle, poste="chef de mission", preuve="attestation 2019"
    )
    keita = Expert.objects.create(
        nom="KEITA",
        prenoms="Ousmane",
        specialite="Génie civil",
        debut_carriere=2018,
        a_verifier="9 ans annoncés pour une licence de 2018",
    )
    Diplome.objects.create(expert=keita, intitule="Licence génie civil", niveau="bac+3")
    Expert.objects.create(nom="ANCIEN", prenoms="Expert", statut=Expert.Statut.ANCIEN)
    return dicko, keita


def test_poste_vivier_et_expert_retenu(client, unicef, vivier):
    dicko, keita = vivier
    poste = {
        "poste": "Contrôleur principal",
        "ordre": "1",
        "niveau_min": "bac+5",
        "annees_experience_min": "5",
        "nb_references_min": "1",
        "specialites": "génie civil, hydraulique",
        "natures": ["CTR", "ETC"],
    }
    assert client.post(f"/avis/{unicef.pk}/besoin", poste, **DIR).status_code == 302
    b = unicef.besoins.get()
    assert b.filtre_references == {"natures": ["CTR", "ETC"]}
    fiche = html(client.get(f"/avis/{unicef.pk}/", **DIR))
    assert "Aucun expert retenu pour ce poste." in fiche
    assert "1 expert du vivier répond à tout" in fiche and "ANCIEN" not in fiche

    (ligne,) = services.experts_pour(unicef)
    assert [x.profil.nom for x in ligne["classement"]] == ["DICKO Oumar", "KEITA Ousmane"]
    assert ligne["classement"][1].ecarts == (
        "diplôme bac+3, bac+5 demandé",
        "0 référence(s) pour 1 demandée(s)",
    )

    client.post(f"/avis/{unicef.pk}/besoin/{b.pk}/retenir", {"expert": keita.pk}, **DIR)
    fiche = html(client.get(f"/avis/{unicef.pk}/", **DIR))
    assert "Retenu : KEITA Ousmane" in fiche and "points à vérifier sur sa fiche" in fiche
    client.post(f"/avis/{unicef.pk}/besoin/{b.pk}/retenir", {"expert": dicko.pk}, **DIR)
    fiche = html(client.get(f"/avis/{unicef.pk}/", **DIR))
    assert "Retenu : DICKO Oumar" in fiche and "répond au profil" in fiche
    assert client.post(f"/avis/{unicef.pk}/besoin/{b.pk}/retenir", **VUE).status_code == 403


def test_poste_que_personne_ne_remplit(client, unicef, vivier):
    BesoinExpert.objects.create(
        avis=unicef, poste="Spécialiste QHSE", annees_experience_min=5, specialites="QHSE"
    )
    fiche = html(client.get(f"/avis/{unicef.pk}/", **DIR))
    assert "Spécialiste QHSE" in fiche and "0 experts du vivier répondent à tout" in fiche
    b = unicef.besoins.get()
    assert client.post(f"/avis/{unicef.pk}/besoin/{b.pk}/retirer", **DIR).status_code == 302
    assert not unicef.besoins.exists()
