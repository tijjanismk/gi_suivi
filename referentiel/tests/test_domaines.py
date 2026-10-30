"""ADR 0014 et 0017 — les cinq domaines de la présentation, leurs sous-domaines, AQA, VRD et
RUR retirés."""

from __future__ import annotations

import importlib

import pytest
from django.apps import apps

from references.models import Mission
from referentiel.models import Categorie, Domaine, TypeOuvrage

pytestmark = pytest.mark.django_db
MIGRATION = importlib.import_module("referentiel.migrations.0005_domaines_presentation")
RETRAIT_RUR = importlib.import_module("referentiel.migrations.0006_retrait_developpement_rural")


def test_cinq_domaines_et_leurs_sous_domaines():
    libelles = dict(Domaine.objects.values_list("code", "libelle"))
    assert libelles == {
        "AEP": "Approvisionnement en eau et assainissement",
        "RTE": "Infrastructures de transport",
        "HYD": "Aménagements hydro-agricoles",
        "BAT": "Bâtiments civils et industriels",
        "ENV": "Environnement",
    }
    domaine = dict(Categorie.objects.values_list("cle", "domaine__code"))
    assert domaine["adductions-eau-sommaires"] == "AEP" and domaine["assainissement"] == "AEP"
    assert domaine["ponts"] == "RTE" and domaine["barrages-retenues"] == "HYD"
    assert "hydraulique-villageoise-pastorale" not in domaine and "pistes-rurales" not in domaine
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
    # cinq domaines, VRD qui sert encore, et RUR que 0005 remet (0006 le retire)
    assert Domaine.objects.count() == 7 and Categorie.objects.filter(cle="ponts").count() == 1
    m.delete()
    MIGRATION.appliquer(apps, None)
    assert not Domaine.objects.filter(code="VRD").exists()


def test_rur_reste_tant_qu_une_reference_le_porte():
    MIGRATION.appliquer(apps, None)  # remet RUR et ses sept sous-domaines
    rur = Domaine.objects.get(code="RUR")
    m = Mission.objects.create(
        code="GIC-AEP-ETU-090", domaine=Domaine.objects.get(code="AEP"), nature="ETU", intitule="x"
    )
    m.domaines_secondaires.add(rur)
    RETRAIT_RUR.retirer(apps, None)
    assert Categorie.objects.filter(domaine=rur).count() == 7
    m.domaines_secondaires.clear()
    RETRAIT_RUR.retirer(apps, None)
    assert not Domaine.objects.filter(code="RUR").exists()
    assert not Categorie.objects.filter(cle="pistes-rurales").exists()
