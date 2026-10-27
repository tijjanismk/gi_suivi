"""Justificatifs d'un expert (dossier du partage, à ouvrir depuis sa fiche) et import des
diplômes lus sur les scans."""

from __future__ import annotations

from html import unescape
from io import StringIO

import pytest
from django.core.management import call_command
from django.test import override_settings

from administratif.demo import pdf
from experts import justificatifs as js
from experts import services
from experts.models import Diplome, Expert
from references.tests.test_references import DIR, IIS, VUE
from suivi.models import JournalAcces

pytestmark = pytest.mark.django_db
DIPLOME = "EXPERTS\\TRAORÉ Awa\\Diplome ingenieur 2iE.pdf"


@pytest.fixture
def awa(tmp_path, settings):
    """Une experte et son dossier sur un partage temporaire."""
    settings.PARTAGE_GIC = str(tmp_path)
    d = tmp_path / "EXPERTS" / "TRAORÉ Awa"
    (d / "anciens").mkdir(parents=True)
    (d / "CV Awa Traoré.docx").write_bytes(b"PK cv")
    (d / "Diplome ingenieur 2iE.pdf").write_bytes(pdf("diplome"))
    (d / "Attestation de travail SAED.pdf").write_bytes(pdf("attestation"))
    (d / "anciens" / "C_V 2019.doc").write_bytes(b"ancien cv")
    (d / "photo.jpg").write_bytes(b"jpg")
    (d / "~$brouillon.docx").write_bytes(b"x")  # fichier de travail : ignoré
    return Expert.objects.create(nom="TRAORÉ", prenoms="Awa", dossier="EXPERTS\\TRAORÉ Awa")


def test_type_d_apres_le_nom():
    assert js.type_de("CV Adama Diakité.docx") == "cv"
    assert js.type_de("C_V Seydou Coulibaly.doc") == "cv"
    assert js.type_de("CV-Djire.docx") == "cv"
    assert js.type_de("Diplôme bachelor 2iE.pdf") == "diplome"
    assert js.type_de("Attestation de réussite DUTS.jpg") == "diplome"
    assert js.type_de("Attestation de travail SAED.pdf") == "attestation"
    assert js.type_de("photo.jpg") == "autre"


def test_fichiers_du_dossier(awa):
    Diplome.objects.create(expert=awa, intitule="Ingénieur hydraulicien", justificatif=DIPLOME)
    f = js.fichiers(awa)
    assert [(x.type, x.dans_dossier) for x in f] == [
        ("cv", "anciens\\C_V 2019.doc"),
        ("cv", "CV Awa Traoré.docx"),
        ("diplome", "Diplome ingenieur 2iE.pdf"),
        ("attestation", "Attestation de travail SAED.pdf"),
        ("autre", "photo.jpg"),
    ]
    assert f[0].sous_dossier == "anciens" and f[0].libelle_type == "CV"
    assert f[1].chemin == "EXPERTS\\TRAORÉ Awa\\CV Awa Traoré.docx"
    assert f[2].diplome.intitule == "Ingénieur hydraulicien" and f[1].diplome is None
    assert js.fichiers(Expert.objects.create(nom="SANS", prenoms="Dossier")) == []
    with pytest.raises(js.PartageIndisponibleError, match="introuvable"):
        js.fichiers(Expert.objects.create(nom="ABSENT", dossier="EXPERTS\\ABSENT"))
    assert js.chemin_du_fichier(awa, "anciens\\C_V 2019.doc").name == "C_V 2019.doc"
    with pytest.raises(ValueError, match="refusé"):
        js.chemin_du_fichier(awa, "..\\..\\secret.txt")
    with pytest.raises(js.PartageIndisponibleError):
        js.chemin_du_fichier(awa, "~$brouillon.docx")


@override_settings(**IIS)
def test_fiche_montre_et_ouvre_les_justificatifs(client, awa):
    Diplome.objects.create(expert=awa, intitule="Ingénieur hydraulicien", justificatif=DIPLOME)
    page = unescape(client.get(f"/experts/{awa.pk}/", **VUE).content.decode())
    assert 'data-type="cv"' in page and "Attestation de travail SAED.pdf" in page
    assert "voir le diplôme" in page and "pas encore enregistré" not in page
    url = f"/experts/{awa.pk}/fichier"
    r = client.get(url, {"f": "Diplome ingenieur 2iE.pdf"}, **VUE)
    assert r.status_code == 200 and b"".join(r.streaming_content).startswith(b"%PDF")
    assert client.get(url, {"f": "..\\x.pdf"}, **VUE).status_code == 404
    assert client.get(url, {"f": "absent.pdf"}, **VUE).status_code == 404
    assert JournalAcces.objects.filter(action="consulter:fichier_expert").exists()
    absent = Expert.objects.create(nom="ABSENT", dossier="EXPERTS\\ABSENT")
    page = unescape(client.get(f"/experts/{absent.pk}/", **DIR).content.decode())
    assert "dossier introuvable sur le partage" in page


def test_importer_les_diplomes(awa):
    lignes = services.lire_csv(
        "dossier;fichier;intitule;etablissement;pays;annee;niveau\n"
        "TRAORÉ Awa;Diplome ingenieur 2iE.pdf;Ingénieur hydraulicien;2iE;Burkina Faso;2016;bac+5\n"
        "TRAORÉ Awa;;DUT génie rural;IPR Katibougou;Mali;2011;bac+2\n"
        "KEITA Moussa;d.pdf;Licence;ENI;Mali;2018;bac+3\n"
        "TRAORÉ Awa;x.pdf;Master;;;deux mille;bac+5\n"
    )
    r = services.importer_diplomes(lignes, simuler=True)
    assert len(r.crees) == 2 and not Diplome.objects.exists()
    assert r.erreurs == [
        "ligne 4 : expert inconnu au vivier (KEITA Moussa)",
        "ligne 5 (TRAORÉ Awa) : intitulé, année ou niveau illisible",
    ]
    r = services.importer_diplomes(lignes)
    d = awa.diplomes.get(niveau="bac+5")
    assert (d.intitule, d.annee, d.justificatif) == ("Ingénieur hydraulicien", 2016, DIPLOME)
    assert awa.diplomes.get(niveau="bac+2").justificatif == ""
    r = services.importer_diplomes(lignes)  # relancé : rien de neuf
    assert not r.crees and len(r.deja) == 2
    assert r.resume == "0 diplôme(s) créé(s), 2 déjà enregistré(s), 2 erreur(s)"


def test_commande_diplomes(awa, tmp_path):
    f = tmp_path / "diplomes.csv"
    f.write_text(
        "dossier;fichier;intitule;annee;niveau\n"
        "TRAORÉ Awa;Diplome ingenieur 2iE.pdf;Ingénieur hydraulicien;2016;bac+5\n",
        encoding="utf-8-sig",
    )
    sortie = StringIO()
    call_command("experts_diplomes", str(f), "--simuler", stdout=sortie)
    texte = sortie.getvalue()
    assert "Simulation, rien n'est gardé : 1 ligne(s) lue(s) ; 1 diplôme(s) créé(s)" in texte
    call_command("experts_diplomes", str(f), stdout=StringIO())
    assert Diplome.objects.get().justificatif == DIPLOME
