"""ADR 0012 — vivier, affectations prouvées, contrôles, import du registre, écrans."""

from __future__ import annotations

from datetime import date
from html import unescape
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from freezegun import freeze_time

from experts import services
from experts.models import Affectation, Diplome, ExperienceExterne, Expert
from references import services as refs
from references.models import Mission
from references.tests.test_references import DIR, IIS, LISTE, VUE
from referentiel.models import Domaine
from suivi.models import JournalAcces

pytestmark = pytest.mark.django_db
AWA = {"REMOTE_USER": "GICONSEILS\\a.traore"}
REGISTRE = (
    "Dossier;Catégorie;Spécialité;Actif\n"
    "TRAORÉ Awa Mariam;Ingénieurs;Hydraulique;oui\n"
    "DIARRA-COULIBALY Fanta;Techniciens supérieurs;Topographie;oui\n"
    "KEITA Moussa;Techniciens;SIG;non\n"
)


@pytest.fixture(autouse=True)
def le_22_octobre():
    with freeze_time("2026-10-22 10:00"):
        yield


@pytest.fixture
def liste():
    refs.importer(refs.lire_csv(LISTE))


@pytest.fixture
def awa(liste):
    e = Expert.objects.create(
        nom="TRAORÉ", prenoms="Awa", specialite="Hydraulique", debut_carriere=2011
    )
    e.domaines.add(Domaine.objects.get(code="HYD"))
    return e


def test_nom_et_import_du_registre():
    assert services.separer_nom("TRAORÉ Awa Mariam") == ("TRAORÉ", "Awa Mariam")
    assert services.separer_nom("DIARRA-COULIBALY Fanta") == ("DIARRA-COULIBALY", "Fanta")
    assert services.separer_nom("Moussa") == ("Moussa", "")
    rapport = services.importer(services.lire_csv(REGISTRE))
    assert rapport.resume == "3 créé(s), 0 mis à jour, 0 erreur(s)"
    awa = Expert.objects.get(nom="TRAORÉ")
    assert awa.prenoms == "Awa Mariam" and awa.categorie == "ingenieur"
    assert (
        awa.dossier == "EXPERTS\\TRAORÉ Awa Mariam"
        and awa.mobilisable
        and str(awa) == "TRAORÉ Awa Mariam"
    )
    assert Expert.objects.get(nom="DIARRA-COULIBALY").categorie == "technicien_superieur"
    keita = Expert.objects.get(nom="KEITA")
    assert keita.statut == "ancien" and not keita.disponible and not keita.mobilisable
    rapport = services.importer(services.lire_csv(REGISTRE.replace("Hydraulique", "Hydrogéologie")))
    assert (
        len(rapport.mis_a_jour) == 3
        and Expert.objects.get(nom="TRAORÉ").specialite == "Hydrogéologie"
    )
    rapport = services.importer(services.lire_csv("nom,prenoms\n,\nSANOGO,Ali\n"), simuler=True)
    assert rapport.erreurs == ["ligne 2 : nom vide"] and rapport.crees == ["SANOGO Ali"]
    assert not Expert.objects.filter(nom="SANOGO").exists()
    with pytest.raises(ValueError, match="dossier"):
        services.lire_csv("qui;quoi\nx;y\n")
    with pytest.raises(ValueError, match="vide"):
        services.lire_csv("")


def test_annees_et_alertes(awa):
    assert services.annees(awa) == 15
    m1, m2 = (
        Mission.objects.get(code="GIC-HYD-ETU-033"),
        Mission.objects.get(code="GIC-AEP-CTR-003"),
    )
    Affectation.objects.create(
        expert=awa,
        mission=m1,
        poste="chef de mission",
        du=date(2020, 1, 1),
        au=date(2020, 12, 31),
        preuve="contrat",
    )
    Affectation.objects.create(
        expert=awa,
        mission=m2,
        poste="hydraulicien",
        du=date(2020, 11, 1),
        au=date(2021, 3, 31),
        preuve="rapport",
    )
    (alerte,) = services.alertes(awa)
    assert "GIC-HYD-ETU-033 (chef de mission) et GIC-AEP-CTR-003 (hydraulicien)" in alerte.message
    assert "61 jours" in alerte.message
    assert str(Affectation.objects.first()).startswith("TRAORÉ Awa — ")


def html(r) -> str:
    assert r.status_code == 200, r.status_code
    return unescape(r.content.decode())


@override_settings(**IIS)
def test_vivier_et_filtres(client, awa):
    services.importer(services.lire_csv(REGISTRE))
    page = html(client.get("/experts/", **DIR))
    assert "4 experts" in page and "15 ans" in page and "non mobilisable" in page
    assert "1 expert" in html(client.get("/experts/", {"q": "topo"}, **DIR))
    assert "3 experts" in html(client.get("/experts/", {"mobilisables": "1"}, **DIR))
    assert "1 expert" in html(
        client.get("/experts/", {"domaine": "HYD", "statut": "interne"}, **DIR)
    )
    assert "1 expert" in html(client.get("/experts/", {"categorie": "technicien"}, **DIR))
    lecture = html(client.get("/experts/", **VUE))
    assert "Nouvel expert" not in lecture
    assert client.get("/experts/", **AWA).status_code == 403
    Expert.objects.all().delete()
    assert "experts_importer" in html(client.get("/experts/", **DIR))


@override_settings(**IIS)
def test_creer_modifier_un_expert(client, liste):
    assert "Nouvel expert" in html(client.get("/experts/nouveau", **DIR))
    hyd = Domaine.objects.get(code="HYD")
    r = client.post(
        "/experts/nouveau",
        {
            "nom": "SANOGO",
            "prenoms": "Ali",
            "statut": "externe",
            "domaines": [hyd.pk],
            "disponible": "on",
            "debut_carriere": "2005",
        },
        follow=True,
        **DIR,
    )
    page = html(r)
    assert "SANOGO Ali enregistré" in page and "sans accord écrit" in page and "21 ans" in page
    e = Expert.objects.get(nom="SANOGO")
    r = client.post(
        f"/experts/{e.pk}/modifier",
        {
            "nom": "SANOGO",
            "prenoms": "Ali",
            "statut": "externe",
            "accord_le": "2026-10-20",
            "disponible": "on",
        },
        follow=True,
        **DIR,
    )
    assert "sans accord écrit" not in html(r) and "le 20/10/2026" in html(r)
    assert client.get(f"/experts/{e.pk}/modifier", **VUE).status_code == 403
    assert JournalAcces.objects.filter(action="expert:creer").exists()


@override_settings(**IIS)
def test_affecter_depuis_l_expert_et_la_reference(client, awa):
    m = Mission.objects.get(code="GIC-HYD-ETU-033")
    base = {
        "expert": awa.pk,
        "mission": m.pk,
        "poste": "chef de mission",
        "du": "2016-01-01",
        "au": "2016-12-31",
        "plein_temps": "1",
    }
    r = client.post("/experts/affecter", {**base, "preuve": ""}, follow=True, **DIR)
    assert "sans preuve, pas d'affectation" in html(r) and not Affectation.objects.exists()
    r = client.post(
        "/experts/affecter", {**base, "preuve": "x", "au": "2015-01-01"}, follow=True, **DIR
    )
    assert "La fin précède le début" in html(r)
    r = client.post("/experts/affecter", {**base, "preuve": "contrat annexe 2"}, follow=True, **DIR)
    page = html(r)
    assert "affecté à GIC-HYD-ETU-033 comme chef de mission" in page and "contrat annexe 2" in page
    # depuis la fiche d'une référence absorbée : l'affectation va au code gardé
    absorbee = Mission.objects.get(code="GIC-HYD-ETU-032")
    r = client.post(
        "/experts/affecter",
        {
            **base,
            "mission": absorbee.pk,
            "poste": "hydrologue",
            "preuve": "rapport",
            "retour": "/references/GIC-HYD-ETU-033/",
        },
        follow=True,
        **DIR,
    )
    page = html(r)
    assert r.redirect_chain[-1][0] == "/references/GIC-HYD-ETU-033/"
    assert "Experts affectés" in page and "hydrologue" in page
    assert Affectation.objects.filter(mission__code="GIC-HYD-ETU-033").count() == 2
    assert "Affecter un expert" in page  # formulaire sur la fiche de la référence
    a = Affectation.objects.get(poste="hydrologue")
    r = client.post(f"/experts/affectation/{a.pk}/retirer", follow=True, **DIR)
    assert "Affectation à GIC-HYD-ETU-033 retirée" in html(r)
    assert client.post("/experts/affecter", {**base, "preuve": "x"}, **VUE).status_code == 403
    assert JournalAcces.objects.filter(action="expert:retirer_affectation").exists()


@override_settings(**IIS)
def test_diplomes_et_experiences(client, awa):
    url = f"/experts/{awa.pk}/"
    r = client.post(
        url + "diplome",
        {
            "intitule": "Ingénieur hydraulicien",
            "niveau": "bac+5",
            "annee": "2010",
            "etablissement": "ENI-ABT",
        },
        follow=True,
        **DIR,
    )
    assert "Diplôme ajouté" in html(r) and "ENI-ABT" in html(r)
    assert "Intitulé obligatoire" in html(
        client.post(url + "diplome", {"intitule": "x", "annee": "deux"}, follow=True, **DIR)
    )
    r = client.post(
        url + "experience",
        {"employeur": "DNH", "poste": "ingénieur", "du": "2011-01-01", "au": "2014-12-31"},
        follow=True,
        **DIR,
    )
    assert "Expérience ajoutée" in html(r) and "ingénieur · DNH" in html(r)
    assert "obligatoires" in html(
        client.post(url + "experience", {"employeur": "DNH"}, follow=True, **DIR)
    )
    assert "précède" in html(
        client.post(
            url + "experience",
            {"employeur": "A", "poste": "B", "du": "2020-01-01", "au": "2019-01-01"},
            follow=True,
            **DIR,
        )
    )
    d, x = Diplome.objects.get(), ExperienceExterne.objects.get()
    assert str(d) == "Ingénieur hydraulicien (2010)" and str(x).endswith("DNH (ingénieur)")
    client.post(f"/experts/diplome/{d.pk}/retirer", **DIR)
    client.post(f"/experts/experience/{x.pk}/retirer", **DIR)
    assert not Diplome.objects.exists() and not ExperienceExterne.objects.exists()
    assert "inconnu" in html(client.post("/experts/autre/1/retirer", follow=True, **DIR))
    assert client.get(url, **VUE).status_code == 200 and client.get(url, **AWA).status_code == 403


def test_commande_importer(tmp_path, db):
    f = tmp_path / "experts.csv"
    f.write_text(REGISTRE, encoding="utf-8-sig")
    sortie = StringIO()
    call_command("experts_importer", str(f), "--simuler", stdout=sortie)
    assert (
        "Simulation, rien n'est gardé : 3 ligne(s)" in sortie.getvalue()
        and not Expert.objects.exists()
    )
    call_command("experts_importer", str(f), stdout=StringIO())
    assert Expert.objects.count() == 3
    mauvais = tmp_path / "m.csv"
    mauvais.write_text("nom;prenoms\n;x\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        call_command("experts_importer", str(mauvais), stdout=StringIO())
    with pytest.raises(CommandError, match="introuvable"):
        call_command("experts_importer", str(tmp_path / "absent.csv"))
    (tmp_path / "v.csv").write_text("qui\nx\n", encoding="utf-8")
    with pytest.raises(CommandError, match="attendue"):
        call_command("experts_importer", str(tmp_path / "v.csv"))
