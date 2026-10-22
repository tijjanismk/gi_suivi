"""ADR 0008 — une référence = un contrat : import de la liste maîtresse, code immuable,
doublons arbitrés par une personne, écrans et commande."""

from __future__ import annotations

from decimal import Decimal
from html import unescape
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from references import services
from references.models import DecisionDoublon, Mission
from referentiel.models import Categorie, Client, Domaine
from suivi.models import JournalAcces

pytestmark = pytest.mark.django_db

IIS = {
    "IDENTITE_SOURCE": "iis",
    "IDENTITE_LECTEUR_GROUPES": "references.tests.test_references.groupes",
}
DIR = {"REMOTE_USER": "GICONSEILS\\directrice"}
VUE = {"REMOTE_USER": "GICONSEILS\\visionneuse"}
AWA = {"REMOTE_USER": "GICONSEILS\\a.traore"}
SAME = "Étude d'avant-projet détaillé de la réhabilitation du barrage de Samé Ouolof"

LISTE = (
    "\n".join(
        [
            "code;statut_code;absorbe_par;intitule_court;client;annee;nature;categorie;montant;"
            "source_word;numero_source;observations",
            f"GIC-HYD-ETU-033;existant;;{SAME};WHH;2016;ETU;Barrages;12 500 000;refs_2016.docx;33;",
            f"GIC-ENV-ETU-020;existant;;{SAME};WHH;2016;ETU;;12 500 000;refs_env.docx;20;",
            f"GIC-HYD-ETU-032;absorbé;GIC-HYD-ETU-033;{SAME};Welthungerhilfe;2016;;;;"
            "refs_2016.docx;32;doublon vu sur SOMAPEP",
            "GIC-AEP-CTR-003;nouveau;;Contrôle des travaux d'AEP de Kayes;SOMAGEP;2020;CTR;AEP;"
            "45000000,00;;;",
            "GIC-AEP-ETU-001;existant;;Études d'AEP de Kayes;SOMAGEP;2019;;AEP;45 000 000 FCFA;;;",
        ]
    )
    + "\n"
)


def groupes(login: str) -> list[str]:
    return {
        "giconseils\\directrice": ["GI-Direction"],
        "giconseils\\visionneuse": ["GI-Direction-Lecture"],
    }.get(login, [])


@pytest.fixture
def liste():
    return services.importer(services.lire_csv(LISTE))


def mission(code: str) -> Mission:
    return Mission.objects.get(code=code)


def test_domaines_de_depart():
    assert list(Domaine.objects.values_list("code", flat=True)) == [
        "HYD", "AEP", "ENV", "BAT", "RTE", "AQA", "VRD",
    ]  # fmt: skip
    assert str(Domaine.objects.get(code="HYD")) == "HYD — Hydraulique"


def test_import_de_la_liste_maitresse(liste):
    assert liste.resume == "5 créée(s), 0 mise(s) à jour, 1 absorbée(s), 0 erreur(s)"
    m = mission("GIC-HYD-ETU-033")
    assert m.domaine.code == "HYD" and m.nature == "ETU" and m.annee == 2016
    assert m.montant == Decimal("12500000") and m.client.nom == "WHH" and str(m.client) == "WHH"
    assert m.categorie.libelle == "Barrages" and m.statut_verification == "importee"
    assert str(m).startswith("GIC-HYD-ETU-033 — Étude")
    assert mission("GIC-AEP-CTR-003").statut_code == "nouveau"
    assert mission("GIC-AEP-CTR-003").montant == Decimal("45000000.00")
    assert mission("GIC-AEP-ETU-001").nature == "ETU"  # tirée du code quand la colonne est vide
    assert mission("GIC-HYD-ETU-032").absorbee_par.code == "GIC-HYD-ETU-033"
    assert Categorie.objects.count() == 2 and Client.objects.count() == 3


def test_import_idempotent_et_fiche_verifiee_protegee(liste):
    m = mission("GIC-AEP-CTR-003")
    m.intitule = "Contrôle et surveillance des travaux d'AEP de Kayes, lots 1 et 2"
    m.save()
    v = mission("GIC-AEP-ETU-001")
    v.statut_verification = "verifiee"
    v.save()
    rapport = services.importer(services.lire_csv(LISTE))
    assert len(rapport.creees) == 0 and len(rapport.mises_a_jour) == 4
    assert rapport.erreurs == ["ligne 6 : GIC-AEP-ETU-001 déjà vérifiée, laissée telle quelle"]
    assert mission("GIC-AEP-CTR-003").intitule.endswith("lots 1 et 2")  # saisi à la main : gardé
    assert Mission.objects.count() == 5


def test_import_erreurs_et_simulation():
    entete = ",".join(services.COLONNES)
    contenu = (
        f"{entete}\n"
        "PAS-UN-CODE,,,Intitulé,,,,,,,,\n"
        "GIC-XYZ-ETU-001,,,Intitulé,,,,,,,,\n"
        "GIC-HYD-ETU-001,,,Intitulé,,deux mille,,,,,,\n"
        "GIC-HYD-ETU-002,,,Intitulé,,,,,12abc34,,,\n"
        "GIC-HYD-ETU-003,,GIC-HYD-ETU-999,Intitulé,,,,,,,,\n"
        "GIC-HYD-ETU-004,,,Intitulé correct,,2020,ETU,,,,,\n"
    )
    rapport = services.importer(services.lire_csv(contenu), simuler=True)
    assert [e.split(" : ")[0] for e in rapport.erreurs] == [
        "ligne 2", "ligne 3", "ligne 4", "ligne 5", "ligne 6",
    ]  # fmt: skip
    assert "invalide" in rapport.erreurs[0] and "inconnu" in rapport.erreurs[1]
    assert "introuvable" in rapport.erreurs[4]
    assert rapport.creees == ["GIC-HYD-ETU-003", "GIC-HYD-ETU-004"]
    assert not Mission.objects.exists()  # simulation : rien n'est gardé
    with pytest.raises(ValueError, match="colonnes manquantes"):
        services.lire_csv("code;client\nGIC-HYD-ETU-001;X\n")
    with pytest.raises(ValueError, match="vide"):
        services.lire_csv("")


def test_montants():
    assert services._montant("45 000 000") == Decimal("45000000")
    assert services._montant("45.000.000,50") == Decimal("45000000.50")
    assert services._montant("1 234,5 FCFA") == Decimal("1234.5")
    assert services._montant("") is None
    assert services._montant("1 500 €") == Decimal("1500")
    for illisible in ("1-2-3", "12abc34", "environ 3 millions"):
        with pytest.raises(ValueError):
            services._montant(illisible)


def test_code_immuable(liste):
    m = mission("GIC-AEP-CTR-003")
    m.code = "GIC-AEP-CTR-004"
    with pytest.raises(ValueError, match="immuable"):
        m.save()
    m = Mission(
        code=" gic-bat-etu-001 ",
        domaine=Domaine.objects.get(code="BAT"),
        nature="ETU",
        intitule="x",
    )
    m.save()
    assert m.code == "GIC-BAT-ETU-001" and m.libelle == "x"


def test_paires_et_decisions(liste):
    paires = services.paires_a_arbitrer()
    cles = {(p.a.code, p.b.code) for p in paires} | {(p.b.code, p.a.code) for p in paires}
    assert ("GIC-HYD-ETU-033", "GIC-ENV-ETU-020") in cles  # le cas SOMAPEP
    assert ("GIC-AEP-CTR-003", "GIC-AEP-ETU-001") in cles  # même client, même montant
    assert not any("GIC-HYD-ETU-032" in c for c in cles)  # déjà absorbée
    hyd, env = mission("GIC-HYD-ETU-033"), mission("GIC-ENV-ETU-020")
    d = services.trancher(hyd, env, True, env, None, raisons="même intitulé")
    hyd.refresh_from_db()
    env.refresh_from_db()
    # le code gardé reçoit le domaine de l'autre ; la fiche qu'absorbait l'autre la suit
    assert hyd.absorbee_par == env and list(
        env.domaines_secondaires.values_list("code", flat=True)
    ) == ["HYD"]
    assert mission("GIC-HYD-ETU-032").absorbee_par == env
    assert str(d).endswith("même contrat, gardée GIC-ENV-ETU-020")
    with pytest.raises(ValueError, match="déjà tranchée"):
        services.trancher(env, hyd, False, None, None)
    # étude + contrôle du même marché : ETC
    ctr, etu = mission("GIC-AEP-CTR-003"), mission("GIC-AEP-ETU-001")
    with pytest.raises(ValueError, match="choisissez"):
        services.trancher(ctr, etu, True, None, None)
    services.trancher(ctr, etu, True, etu, None)
    assert mission("GIC-AEP-ETU-001").nature == "ETC"
    assert services.paires_a_arbitrer() == []


def test_contrats_differents_et_fiche_deja_absorbee(liste):
    ctr, etu = mission("GIC-AEP-CTR-003"), mission("GIC-AEP-ETU-001")
    d = services.trancher(ctr, etu, False, None, None, note="deux marchés")
    assert str(d).endswith("différents") and d.note == "deux marchés"
    assert not any(
        {p.a.code, p.b.code} == {ctr.code, etu.code} for p in services.paires_a_arbitrer()
    )
    with pytest.raises(ValueError, match="déjà absorbée"):
        services.trancher(mission("GIC-HYD-ETU-032"), mission("GIC-ENV-ETU-020"), False, None, None)


def html(r) -> str:
    assert r.status_code == 200, r.status_code
    return unescape(r.content.decode())


@override_settings(**IIS)
def test_ecran_liste_et_filtres(client, liste):
    page = html(client.get("/references/", **DIR))
    assert "4 références" in page and 'data-code="GIC-HYD-ETU-032"' not in page
    assert 'data-code="GIC-HYD-ETU-032"' in html(client.get("/references/?absorbees=1", **DIR))
    page = html(client.get("/references/", {"q": "kayes", "nature": "CTR"}, **DIR))
    assert "1 référence" in page and "GIC-AEP-CTR-003" in page
    page = html(client.get("/references/", {"domaine": "AEP", "verification": "importee"}, **DIR))
    assert "2 références" in page
    env, hyd = mission("GIC-ENV-ETU-020"), mission("GIC-HYD-ETU-033")
    services.trancher(hyd, env, True, env, None)
    page = html(client.get("/references/", {"domaine": "HYD"}, **DIR))  # HYD en secondaire
    assert "GIC-ENV-ETU-020" in page and "+ HYD" in page
    assert client.get("/references/", **AWA).status_code == 403
    assert JournalAcces.objects.filter(action="consulter:references").exists()


@override_settings(**IIS)
def test_ecran_liste_vide_et_pages(client, db):
    assert "references_importer" in html(client.get("/references/", **DIR))
    hyd = Domaine.objects.get(code="HYD")
    Mission.objects.bulk_create(
        Mission(code=f"GIC-HYD-ETU-{i:03d}", domaine=hyd, nature="ETU", intitule=f"m{i}")
        for i in range(105)
    )
    page = html(client.get("/references/", **DIR))
    assert "page 1 sur 2" in page and "Suivantes" in page
    assert "Précédentes" in html(client.get("/references/?page=2", **DIR))


@override_settings(**IIS)
def test_ecran_fiche(client, liste):
    env, hyd = mission("GIC-ENV-ETU-020"), mission("GIC-HYD-ETU-033")
    services.trancher(hyd, env, True, env, None, note="vu sur SOMAPEP")
    page = html(client.get("/references/GIC-ENV-ETU-020/", **VUE))
    assert "Fiches absorbées" in page and "GIC-HYD-ETU-033" in page and "vu sur SOMAPEP" in page
    assert "12 500 000 FCFA" in page or "12 500 000 FCFA" in page.replace("\xa0", " ")
    page = html(client.get("/references/GIC-HYD-ETU-033/", **VUE))
    assert 'id="absorbee"' in page and "GIC-ENV-ETU-020" in page
    assert "attribué au chantier 2" in html(client.get("/references/GIC-AEP-CTR-003/", **VUE))
    assert client.get("/references/INCONNU/", **DIR).status_code == 404


@override_settings(**IIS)
def test_ecran_doublons_et_decisions(client, liste):
    page = html(client.get("/references/doublons/", **DIR))
    assert "2 paires à arbitrer" in page and "Même contrat : garder GIC-HYD-ETU-033" in page
    assert "Proposition : garder GIC-ENV-ETU-020" in page  # le plus petit numéro
    lecture = html(client.get("/references/doublons/", **VUE))
    assert "Consultation seule" in lecture and "Contrats différents" not in lecture
    hyd, env = mission("GIC-HYD-ETU-033"), mission("GIC-ENV-ETU-020")
    r = client.post(
        "/references/doublons/trancher",
        {"a": hyd.pk, "b": env.pk, "choix": "garder_b", "raisons": "même intitulé"},
        follow=True,
        **DIR,
    )
    assert "GIC-HYD-ETU-033 est absorbée par GIC-ENV-ETU-020" in html(r)
    assert DecisionDoublon.objects.get().raisons == "même intitulé"
    ctr, etu = mission("GIC-AEP-CTR-003"), mission("GIC-AEP-ETU-001")
    r = client.post(
        "/references/doublons/trancher",
        {"a": ctr.pk, "b": etu.pk, "choix": "differents"},
        follow=True,
        **DIR,
    )
    assert "contrats différents" in html(r) and "Aucune paire suspecte" in html(r)
    r = client.post(
        "/references/doublons/trancher",
        {"a": ctr.pk, "b": etu.pk, "choix": "differents"},
        follow=True,
        **DIR,
    )
    assert "déjà tranchée" in html(r)
    r = client.post(
        "/references/doublons/trancher",
        {"a": ctr.pk, "b": etu.pk, "choix": "?"},
        follow=True,
        **DIR,
    )
    assert "Décision inconnue" in html(r)
    assert (
        client.post(
            "/references/doublons/trancher",
            {"a": ctr.pk, "b": etu.pk, "choix": "differents"},
            **VUE,
        ).status_code
        == 403
    )
    assert JournalAcces.objects.filter(action="reference:doublon").exists()


def test_commande_importer(tmp_path, db):
    f = tmp_path / "liste.csv"
    f.write_text(LISTE, encoding="utf-8-sig")
    sortie = StringIO()
    call_command("references_importer", str(f), "--simuler", stdout=sortie)
    assert "Simulation, rien n'est gardé : 5 ligne(s) lue(s)" in sortie.getvalue()
    assert not Mission.objects.exists()
    sortie = StringIO()
    call_command("references_importer", str(f), stdout=sortie)
    assert "ABSORBÉE GIC-HYD-ETU-032 → GIC-HYD-ETU-033" in sortie.getvalue()
    assert Mission.objects.count() == 5
    mauvais = tmp_path / "mauvais.csv"
    mauvais.write_text("code;intitule_court\nXX;y\n", encoding="utf-8")
    with pytest.raises(SystemExit):
        call_command("references_importer", str(mauvais), stdout=StringIO())
    with pytest.raises(CommandError, match="introuvable"):
        call_command("references_importer", str(tmp_path / "absent.csv"))
    (tmp_path / "vide.csv").write_text("code;client\n", encoding="utf-8")
    with pytest.raises(CommandError, match="colonnes manquantes"):
        call_command("references_importer", str(tmp_path / "vide.csv"))
