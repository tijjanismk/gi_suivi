"""ADR 0014 — les six domaines de la présentation, leurs sous-domaines, AQA et VRD retirés."""

from __future__ import annotations

import importlib

import pytest
from django.apps import apps

from references.models import Mission
from referentiel.models import Categorie, Domaine, TypeOuvrage

pytestmark = pytest.mark.django_db
MIGRATION = importlib.import_module("referentiel.migrations.0005_domaines_presentation")


def test_six_domaines_et_leurs_sous_domaines():
    libelles = dict(Domaine.objects.values_list("code", "libelle"))
    assert libelles == {
        "AEP": "Approvisionnement en eau et assainissement",
        "RUR": "Développement rural",
        "RTE": "Infrastructures de transport",
        "HYD": "Aménagements hydro-agricoles",
        "BAT": "Bâtiments civils et industriels",
        "ENV": "Environnement",
    }
    domaine = dict(Categorie.objects.values_list("cle", "domaine__code"))
    assert domaine["adductions-eau-sommaires"] == "AEP" and domaine["assainissement"] == "AEP"
    assert domaine["ponts"] == "RTE" and domaine["barrages-retenues"] == "HYD"
    assert domaine["hydraulique-villageoise-pastorale"] == "RUR"
    assert domaine["bas-fonds-et-plaines"] == "HYD"  # clé déjà créée par l'import, reprise
    assert {"aes", "pont", "dalot", "shva", "shpa"} <= set(
        TypeOuvrage.objects.values_list("cle", flat=True)
    )


def test_vrd_reste_tant_qu_une_reference_le_porte():
    vrd = Domaine.objects.create(code="VRD", libelle="Voirie et réseaux divers", ordre=70)
    Categorie.objects.filter(cle="assainissement").update(domaine=vrd)
    m = Mission.objects.create(
        code="GIC-VRD-ETC-002", domaine=vrd, nature="ETC", intitule="Assainissement d'Ansongo"
    )
    MIGRATION.appliquer(apps, None)  # rejouable : rien n'est créé deux fois
    assert Domaine.objects.filter(code="VRD").exists()
    assert Categorie.objects.get(cle="assainissement").domaine.code == "AEP"
    assert Domaine.objects.count() == 7 and Categorie.objects.filter(cle="ponts").count() == 1
    m.delete()
    MIGRATION.appliquer(apps, None)
    assert not Domaine.objects.filter(code="VRD").exists()
