"""ADR 0011 — justificatifs (rattachement, audit, réclamations), ouvrages et quantités."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from html import unescape
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from administratif.demo import pdf
from references import justificatifs as js
from references import services
from references.models import Mission, PieceJustificative, Quantite, Reclamation
from references.tests.test_references import DIR, IIS, LISTE, VUE
from referentiel.models import Livrable, TypeOuvrage, TypeQuantite
from suivi.models import JournalAcces

pytestmark = pytest.mark.django_db
CODE = "GIC-HYD-ETU-033"


@pytest.fixture
def dossier(tmp_path, settings):
    """Le partage temporaire, la liste fictive et trois scans posés pour GIC-HYD-ETU-033."""
    settings.PARTAGE_GIC = str(tmp_path)
    services.importer(services.lire_csv(LISTE))
    d = tmp_path / "REFERENCES" / "02_JUSTIFICATIFS" / CODE
    d.mkdir(parents=True)
    (d / "GARDE.pdf").write_bytes(pdf("garde Samé"))
    (d / "SIGNATURE.pdf").write_bytes(pdf("signature Samé"))
    (d / "ATTESTATION.pdf").write_bytes(pdf("attestation WHH", pages=2))
    (d / "copie GARDE.pdf").write_bytes(pdf("garde Samé"))  # doublon
    (d / "~$brouillon.docx").write_bytes(b"x")  # fichier de travail ignoré
    return d


def m(code: str = CODE) -> Mission:
    return Mission.objects.get(code=code)


def fichier(nom: str, code: str = CODE) -> js.Fichier:
    return next(f for f in js.fichiers(m(code)) if f.nom == nom)


def test_types_de_depart():
    assert TypeOuvrage.objects.count() == 12 and Livrable.objects.count() == 6
    assert TypeQuantite.objects.count() == 5
    seuil = TypeOuvrage.objects.get(cle="seuil-epandage")
    assert "recharge de nappe" in seuil.synonymes and seuil.famille.startswith("mobilisation")
    assert str(TypeQuantite.objects.get(cle="superficie-ha")) == "Superficie aménagée (ha)"
    assert str(Livrable.objects.get(cle="apd")).startswith("Avant-projet détaillé")


def test_type_propose_d_apres_le_nom():
    assert js.type_propose("GARDE.pdf") == "garde"
    assert js.type_propose("Page de garde du contrat.pdf") == "garde"
    assert js.type_propose("SIGNATURE.pdf") == "signature"
    assert js.type_propose("ATTESTATION.pdf") == "attestation"
    assert js.type_propose("PV reception.pdf") == "attestation"
    assert js.type_propose("CONTRAT_COMPLET.pdf") == "contrat_complet"
    assert js.type_propose("Avenant n°1.pdf") == "avenant"
    assert js.type_propose("photo.jpg") == "autre"


def test_fichiers_rattacher_auditer_complet(dossier):
    fichiers = {f.nom: f for f in js.fichiers(m())}
    assert set(fichiers) == {"ATTESTATION.pdf", "GARDE.pdf", "SIGNATURE.pdf", "copie GARDE.pdf"}
    assert (
        fichiers["copie GARDE.pdf"].statut == "doublon"
        and fichiers["ATTESTATION.pdf"].nb_pages == 2
    )
    for nom in ("GARDE.pdf", "SIGNATURE.pdf", "ATTESTATION.pdf"):
        f = fichier(nom)
        js.rattacher(m(), f, f.type_propose, None)
    assert fichier("GARDE.pdf").statut == "rattache"
    etat = js.etat_justificatifs(m())
    assert [e.etat for e in etat.emplacements] == ["a_auditer"] * 3 and not etat.complete
    for p in m().pieces.all():
        js.auditer(
            p, {"lisible": "oui", "coherente": "oui", "nature_exacte": "bonne_execution"}, None
        )
    etat = js.etat_justificatifs(m())
    assert etat.complete and etat.nb_bonnes == 3
    assert js.avec_nb_bonnes(Mission.objects.filter(code=CODE)).get().nb_bonnes == 3
    p = m().pieces.get(type="attestation")
    js.auditer(
        p, {"lisible": "moyen", "coherente": "doute", "date_document": date(2017, 1, 5)}, None
    )
    assert js.etat_justificatifs(m()).emplacements[2].etat == "faible"
    assert p.nom_fichier == "ATTESTATION.pdf" and str(p).endswith("attestation")


def test_rattacher_refus(dossier, tmp_path):
    js.rattacher(m(), fichier("GARDE.pdf"), "garde", None)
    with pytest.raises(ValueError, match="rattache"):  # même contenu que la garde rattachée
        js.rattacher(m(), fichier("copie GARDE.pdf"), "garde", None)
    with pytest.raises(ValueError, match="déjà une page de garde"):
        js.rattacher(m(), fichier("SIGNATURE.pdf"), "garde", None)
    with pytest.raises(ValueError, match="inconnu"):
        js.rattacher(m(), fichier("SIGNATURE.pdf"), "photo", None)
    f = fichier("SIGNATURE.pdf")
    (dossier / "SIGNATURE.pdf").write_bytes(pdf("modifiée"))
    with pytest.raises(ValueError, match="changé ou disparu"):
        js.rattacher(m(), f, "signature", None)
    # le même scan posé dans le dossier d'une autre référence : déjà rattaché ailleurs
    autre = tmp_path / "REFERENCES" / "02_JUSTIFICATIFS" / "GIC-ENV-ETU-020"
    autre.mkdir()
    (autre / "GARDE.pdf").write_bytes(pdf("garde Samé"))
    f = fichier("GARDE.pdf", "GIC-ENV-ETU-020")
    assert f.statut == "ailleurs" and f.piece.mission.code == CODE
    with pytest.raises(js.PartageIndisponibleError, match="introuvable"):
        js.fichiers(m("GIC-AEP-CTR-003"))


def test_rattacher_dossiers_complets_seulement(dossier):
    racine = dossier.parent
    (racine / "GIC-ENV-ETU-020").mkdir()
    (racine / "GIC-ENV-ETU-020" / "GARDE.pdf").write_bytes(pdf("garde Kayes"))
    (racine / "GIC-HYD-ETU-032").mkdir()  # absorbée par GIC-HYD-ETU-033
    (racine / "GIC-INCONNU").mkdir()
    (racine / "lisez-moi.txt").write_bytes(b"x")  # pas un dossier : ignoré
    r = js.rattacher_dossiers(simuler=True)
    assert r.rattachees == [f"{CODE} : garde", f"{CODE} : signature", f"{CODE} : attestation"]
    assert r.incompletes == ["GIC-ENV-ETU-020 : manque signature, attestation"]
    assert r.erreurs == [
        "GIC-HYD-ETU-032 : absorbée par GIC-HYD-ETU-033, ses pièces vont dans son dossier",
        "GIC-INCONNU : référence inconnue",
    ]
    assert not PieceJustificative.objects.exists()  # simulation : rien n'est gardé
    r = js.rattacher_dossiers()
    assert len(r.rattachees) == 3 and m().pieces.count() == 3
    assert [e.etat for e in js.etat_justificatifs(m()).emplacements] == ["a_auditer"] * 3
    assert m().pieces.get(type="garde").nom_fichier == "GARDE.pdf"  # pas « copie GARDE.pdf »
    assert not m("GIC-ENV-ETU-020").pieces.exists()
    # relancée : rien de neuf
    r = js.rattacher_dossiers()
    assert not r.rattachees
    assert r.deja == [f"{CODE} : {t}" for t in ("garde", "signature", "attestation")]
    # trois fichiers posés, mais la garde est celle d'une autre référence : rien n'est rattaché
    autre = racine / "GIC-AEP-CTR-003"
    autre.mkdir()
    (autre / "GARDE.pdf").write_bytes(pdf("garde Samé"))
    (autre / "SIGNATURE.pdf").write_bytes(pdf("signature Kayes"))
    (autre / "ATTESTATION.pdf").write_bytes(pdf("attestation SOMAGEP"))
    r = js.rattacher_dossiers()
    assert f"GIC-AEP-CTR-003 : « GARDE.pdf » déjà rattaché à {CODE}" in r.erreurs
    assert "GIC-AEP-CTR-003 : manque garde" in r.incompletes
    assert not m("GIC-AEP-CTR-003").pieces.exists()


def test_commande_rattacher(dossier, settings):
    sortie = StringIO()
    call_command("references_rattacher", "--simuler", stdout=sortie)
    assert "Simulation, rien n'est gardé : 3 pièce(s) rattachée(s)" in sortie.getvalue()
    assert not PieceJustificative.objects.exists()
    (dossier.parent / "GIC-ENV-ETU-020").mkdir()
    sortie = StringIO()
    call_command("references_rattacher", "--detail", stdout=sortie)
    assert "INCOMPLÈTE GIC-ENV-ETU-020 : manque garde, signature, attestation" in sortie.getvalue()
    assert PieceJustificative.objects.count() == 3
    (dossier.parent / "GIC-INCONNU").mkdir()
    sortie = StringIO()
    with pytest.raises(SystemExit):
        call_command("references_rattacher", stdout=sortie)
    assert "ERREUR GIC-INCONNU : référence inconnue" in sortie.getvalue()
    settings.PARTAGE_GIC = str(dossier / "absent")
    with pytest.raises(CommandError, match="introuvable"):
        call_command("references_rattacher")
    settings.PARTAGE_GIC = ""
    with pytest.raises(CommandError, match="pas configuré"):
        call_command("references_rattacher")


def test_audit_et_reclamation_refus(dossier):
    p = js.rattacher(m(), fichier("GARDE.pdf"), "garde", None)
    with pytest.raises(ValueError, match="lisible"):
        js.auditer(p, {"lisible": "peut-être"}, None)
    with pytest.raises(ValueError, match="inconnu"):
        js.reclamer(m(), "attestation", "perdue", None, "", "", None)
    r = js.reclamer(
        m(), "attestation", "demandee", date(2026, 10, 20), " M. Traoré, WHH ", "lettre", None
    )
    js.reclamer(m(), "attestation", "relancee", date(2026, 10, 27), "", "", None)
    e = js.etat_justificatifs(m()).emplacements[2]
    assert e.reclamation.etat == "relancee" and r.contact_client == "M. Traoré, WHH"
    assert str(r).endswith("attestation : demandée")


def test_ouvrages_et_quantites():
    services.importer(services.lire_csv(LISTE))
    seuil, piv = TypeOuvrage.objects.get(cle="seuil-epandage"), TypeOuvrage.objects.get(cle="piv")
    apd = Livrable.objects.get(cle="apd")
    ha, km = (
        TypeQuantite.objects.get(cle="superficie-ha"),
        TypeQuantite.objects.get(cle="longueur-km"),
    )
    js.enregistrer_ouvrages(
        m(), [seuil.pk, piv.pk], [apd.pk], {ha.pk: ("30,5", " contrat p. 4 "), km.pk: ("", "")}
    )
    q = Quantite.objects.get()
    assert q.valeur == Decimal("30.5") and q.source == "contrat p. 4" and "30,5 ha" in str(q)
    assert set(m().types_ouvrage.values_list("cle", flat=True)) == {"seuil-epandage", "piv"}
    js.enregistrer_ouvrages(m(), [seuil.pk], [], {ha.pk: ("", "")})  # valeur vide : retirée
    assert not Quantite.objects.exists() and not m().livrables.exists()
    for illisible in ("trente", "-3"):
        with pytest.raises(ValueError):
            js.enregistrer_ouvrages(m(), [], [], {ha.pk: (illisible, "")})
    assert m().types_ouvrage.count() == 1  # rien n'est gardé après une erreur
    assert js.lire_quantite("1 250,75") == Decimal("1250.75")


def html(r) -> str:
    assert r.status_code == 200, r.status_code
    return unescape(r.content.decode())


@override_settings(**IIS)
def test_ecran_justificatifs(client, dossier):
    url = f"/references/{CODE}/justificatifs"
    page = html(client.get(url, **DIR))
    assert "0 pièces bonnes sur 3" in page and 'data-statut="doublon"' in page
    empreinte = fichier("GARDE.pdf").empreinte
    r = client.post(
        url + "/rattacher", {"empreinte": empreinte, "type": "garde"}, follow=True, **DIR
    )
    assert "rattaché comme page de garde" in html(r)
    r = client.post(
        url + "/rattacher", {"empreinte": "0" * 64, "type": "garde"}, follow=True, **DIR
    )
    assert "fichier introuvable" in html(r)
    p = PieceJustificative.objects.get()
    r = client.post(
        f"/references/piece/{p.pk}/auditer",
        {
            "lisible": "oui",
            "coherente": "oui",
            "nature_exacte": "garde_contrat",
            "date_document": "2016-03-01",
        },
        follow=True,
        **DIR,
    )
    assert "Audit de la page de garde enregistré" in html(r)
    p.refresh_from_db()
    assert p.date_document == date(2016, 3, 1) and p.bonne
    r = client.post(f"/references/piece/{p.pk}/auditer", {"lisible": "?"}, follow=True, **DIR)
    assert "inconnu" in html(r)
    r = client.post(
        url + "/reclamer",
        {"type": "attestation", "etat": "demandee", "le": "2026-10-20"},
        follow=True,
        **DIR,
    )
    assert "Réclamation notée : attestation, demandée" in html(r) and Reclamation.objects.exists()
    r = client.post(url + "/reclamer", {"type": "attestation", "etat": "?"}, follow=True, **DIR)
    assert "inconnu" in html(r)
    f = client.get(f"/references/piece/{p.pk}/fichier", **VUE)
    assert f.status_code == 200 and b"".join(f.streaming_content).startswith(b"%PDF")
    r = client.post(f"/references/piece/{p.pk}/detacher", follow=True, **DIR)
    assert "le fichier reste dans le dossier" in html(r) and not PieceJustificative.objects.exists()
    assert (dossier / "GARDE.pdf").is_file()
    lecture = html(client.get(url, **VUE))
    assert "Rattacher" not in lecture and "Enregistrer l'audit" not in lecture
    assert (
        client.post(
            url + "/rattacher", {"empreinte": empreinte, "type": "garde"}, **VUE
        ).status_code
        == 403
    )
    assert JournalAcces.objects.filter(action="reference:rattacher").exists()


@override_settings(**IIS)
def test_ecran_justificatifs_partage_et_fichier_absents(client, dossier, settings):
    p = js.rattacher(m(), fichier("GARDE.pdf"), "garde", None)
    (dossier / "GARDE.pdf").unlink()
    assert client.get(f"/references/piece/{p.pk}/fichier", **DIR).status_code == 404
    assert "introuvable" in html(client.get("/references/GIC-AEP-CTR-003/justificatifs", **DIR))
    settings.PARTAGE_GIC = ""
    assert client.get(f"/references/piece/{p.pk}/fichier", **DIR).status_code == 404
    assert "pas configuré" in html(client.get(f"/references/{CODE}/justificatifs", **DIR))


@override_settings(**IIS)
def test_ecran_ouvrages_fiche_et_liste(client, dossier):
    seuil, ha = (
        TypeOuvrage.objects.get(cle="seuil-epandage"),
        TypeQuantite.objects.get(cle="superficie-ha"),
    )
    url = f"/references/{CODE}/ouvrages"
    assert "Seuil d'épandage" in html(client.get(url, **DIR))
    r = client.post(
        url, {"types_ouvrage": [seuil.pk, "x"], f"q-{ha.pk}": "trente"}, follow=True, **DIR
    )
    assert "quantité illisible" in html(r)
    r = client.post(
        url,
        {"types_ouvrage": [seuil.pk], f"q-{ha.pk}": "45", f"s-{ha.pk}": "rapport"},
        follow=True,
        **DIR,
    )
    page = html(r)
    assert "enregistrés" in page and "Superficie aménagée : 45 ha" in page and "(rapport)" in page
    assert "Seuil d'épandage" in page and "Page de garde : manquante" in page
    assert client.get(url, **VUE).status_code == 403
    page = html(client.get("/references/", {"ouvrage": "seuil-epandage"}, **DIR))
    assert "1 référence" in page and CODE in page
    for f in ("GARDE.pdf", "SIGNATURE.pdf", "ATTESTATION.pdf"):
        p = js.rattacher(m(), fichier(f), js.type_propose(f), None)
        js.auditer(p, {"lisible": "oui", "coherente": "oui"}, None)
    page = html(client.get("/references/", {"pieces": "completes"}, **DIR))
    assert "1 référence" in page and "3 / 3" in page
    assert "3 références" in html(client.get("/references/", {"pieces": "incompletes"}, **DIR))
