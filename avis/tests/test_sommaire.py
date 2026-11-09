"""Sommaire, intercalaires et dossier d'un AMI (AV11, AV14) : la carte de la fiche et les pages à
imprimer, tirées du même plan, part du bureau. Cas d'essai : le barème FIER II (Ségou, 2026),
puis un AMI de type PISEN (Niger) dont la simulation est enregistrée, pour les listes."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from html import unescape

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone
from freezegun import freeze_time

from administratif.models import PieceAdministrative, TypePiece
from administratif.tests.conftest import AWA, DIR, IIS, VUE
from avis import outils_mcp as outils
from avis import services
from avis.models import Avis, Critere, Selection
from references.models import Mission, PieceJustificative
from referentiel.models import Client, Domaine
from suivi.models import JournalAcces

pytestmark = pytest.mark.django_db

OBJET = "Sélection d'un cabinet pour l'EIES et les PAR des ouvrages de mobilisation des eaux"
EIES = "Au moins trois (3) EIES de projets hydrauliques"
GARDE = "REFERENCES\\02_JUSTIFICATIFS\\GIC-HYD-ETU-033\\GARDE.pdf"
NIF = "ADMINISTRATIF\\PIECES\\NIF\\nif.pdf"
INTERCALAIRES = ("A", "A.1", "A.2", "B", "C", "D", "D.1", "D.2", "D.2.1", "D.2.2", "E", "F")


def html(r) -> str:
    return unescape(r.content.decode())


@pytest.fixture(autouse=True)
def le_28_octobre():
    with freeze_time("2026-10-28 10:00"), override_settings(**IIS):
        yield


@pytest.fixture
def fier_ii():
    a = Avis.objects.create(
        reference="AMI-FIER-II-SEGOU",
        objet="Études techniques et contrôle des travaux des infrastructures du projet FIER II",
        type=Avis.Type.AMI,
        groupement=True,
        date_limite=date(2026, 11, 15),
    )
    for ordre, code, libelle in (
        (1, "1", "Expériences générales en rapport avec la mission"),
        (2, "2", "Expériences spécifiques"),
        (3, "2.1", "Expériences spécifiques dans les études hydroagricoles\n2 points par étude"),
    ):
        Critere.objects.create(
            avis=a, code=code, ordre=ordre, libelle=libelle, mode=Critere.Mode.MANUEL
        )
    Critere.objects.create(
        avis=a, code="3", ordre=4, libelle="Contrôles", mode=Critere.Mode.MANUEL, brouillon=True
    )
    return a


def test_la_fiche_d_un_ami_donne_son_sommaire(client, fier_ii):
    page = html(client.get(f"/avis/{fier_ii.pk}/", **DIR))
    assert "Sommaire de la manifestation d'intérêt" in page
    codes = ("A", "A.1", "A.2", "A.3", "A.4", "B", "C", "D", "D.1", "D.2", "D.2.1", "E", "F")
    for code in codes:
        assert f'data-rubrique="{code}"' in page
    assert "ACCORD DE GROUPEMENT" in page and "DU GROUPEMENT" not in page  # la part du bureau
    assert "Expériences spécifiques dans les études hydroagricoles<" in page  # première ligne
    assert 'data-rubrique="D.2.2"' not in page  # critère en brouillon, pas encore validé
    assert "présentation du bureau non cochée dans les pièces exigées" in page
    assert "aucun poste saisi" in page
    assert f'href="/avis/{fier_ii.pk}/dossier"' in page
    assert f'href="/avis/{fier_ii.pk}/intercalaires"' in page


def test_les_intercalaires_une_feuille_par_ligne_du_plan(client, fier_ii):
    page = html(client.get(f"/avis/{fier_ii.pk}/intercalaires", **VUE))
    assert page.count('class="page page-intercalaire"') == 13  # 5 A, B, C, 4 D, E, F
    assert page.count("<li class=") == 9  # au sommaire, les A.x n'ont pas de ligne
    assert "SOMMAIRE DE LA MANIFESTATION D’INTERET" in page
    titre = "D.2.1. Expériences spécifiques dans les études hydroagricoles"
    assert f'<h2 class="banniere">{titre}</h2>' in page
    assert '<h2 class="banniere">B. PIÈCES ADMINISTRATIVES DE ' in page
    assert 'data-genre="lettre"' not in page  # le sommaire et les intercalaires seulement
    assert JournalAcces.objects.filter(cible=f"{fier_ii.pk} intercalaires").exists()
    assert client.get(f"/avis/{fier_ii.pk}/intercalaires", **AWA).status_code == 403


def test_dossier_entete_pied_et_logo_lu_sur_le_partage(client, fier_ii, settings, tmp_path):
    settings.PARTAGE_GIC = str(tmp_path)
    page = html(client.get(f"/avis/{fier_ii.pk}/intercalaires", **DIR))
    pied = '<footer class="hf-bas">Études techniques et contrôle'
    assert page.count('<header class="hf-haut">') == page.count(pied) == 14  # sommaire + 13
    url = f"/avis/{fier_ii.pk}/dossier"
    page = html(client.get(url, **DIR))
    assert 'data-genre="lettre"' in page and 'data-genre="organigramme"' in page
    assert 'src="/avis/logo"' not in page and "le nom du bureau est écrit à sa place" in page
    assert 'class="adresse-bureau"' in page  # sans logo, l'adresse en texte sous le nom
    assert client.get("/avis/logo", **VUE).status_code == 404
    assert JournalAcces.objects.filter(cible=f"{fier_ii.pk} dossier").exists()

    (tmp_path / "ADMINISTRATIF" / "LOGOS").mkdir(parents=True)
    (tmp_path / "ADMINISTRATIF" / "LOGOS" / "LOGO.png").write_bytes(b"\x89PNG\r\n\x1a\nlogo")
    page = html(client.get(url, **DIR))
    assert 'src="/avis/logo"' in page
    assert 'class="adresse-bureau"' not in page  # le logo porte déjà l'adresse ext sud
    r = client.get("/avis/logo", **VUE)
    assert r.status_code == 200 and r["Content-Type"] == "image/png"
    assert client.get("/avis/logo", **AWA).status_code == 403
    assert client.get(url, **AWA).status_code == 403


def test_outil_mcp_plan_du_dossier(fier_ii):
    r = outils.plan_dossier(fier_ii.pk)
    assert r["adresse"] == f"/avis/{fier_ii.pk}/dossier"
    codes = [s["code"] for s in r["sommaire"]]
    assert codes == ["A", "B", "C", "D", "D.1", "D.2", "D.2.1", "E", "F"]
    assert r["pages"][0] == {"page": 1, "genre": "couverture", "etat": "redigee"}
    assert sum(r["compte"].values()) == len(r["pages"])
    fier_ii.type = Avis.Type.DP
    fier_ii.save()
    assert "AMI" in outils.plan_dossier(fier_ii.pk)["erreur"]


def test_ni_sommaire_ni_dossier_hors_ami(client, fier_ii):
    fier_ii.type = Avis.Type.DP
    fier_ii.save()
    assert "Sommaire de la manifestation" not in html(client.get(f"/avis/{fier_ii.pk}/", **DIR))
    assert client.get(f"/avis/{fier_ii.pk}/intercalaires", **DIR).status_code == 404
    assert client.get(f"/avis/{fier_ii.pk}/dossier", **DIR).status_code == 404


@pytest.fixture
def pisen():
    a = Avis.objects.create(
        reference="N°005/MEHA/PISEN/2026",
        objet=OBJET,
        type=Avis.Type.AMI,
        pays="Niger",
        maitre_ouvrage=Client.objects.create(nom="Unité de gestion du projet PISEN"),
        date_limite=date(2026, 11, 12),
        destinataire="Monsieur le Coordonnateur National du PISEN, Niamey",
        formule_appel="Monsieur le Coordonnateur National",
    )
    bareme = (
        ("1", "Être légalement constitué depuis dix (10) ans", "", Critere.Mode.ANCIENNETE),
        ("2", "Au moins cinq (5) études environnementales", "generale", Critere.Mode.PAR_MISSION),
        ("5", EIES, "", Critere.Mode.PAR_MISSION),
        ("6", "Au moins trois (3) PAR", "", Critere.Mode.PAR_MISSION),
    )
    for ordre, (code, libelle, experience, mode) in enumerate(bareme, start=1):
        Critere.objects.create(
            avis=a,
            code=code,
            ordre=ordre,
            libelle=libelle,
            experience=experience,
            mode=mode,
            points_par_mission=Decimal(1),
            points_socle=Decimal(1),
        )
    Critere.objects.create(
        avis=a, code="7", ordre=5, libelle="Zones sahéliennes", mode="manuel", brouillon=True
    )
    return a


def justifier(m: Mission) -> None:
    """La page de garde, la page de signature et l'attestation de la référence."""
    for type_ in ("garde", "signature", "attestation"):
        PieceJustificative.objects.create(
            mission=m,
            type=type_,
            chemin=f"REFERENCES\\02_JUSTIFICATIFS\\{m.code}\\{type_.upper()}.pdf",
            empreinte=f"{m.code}-{type_}".ljust(64, "0"),
        )


@pytest.fixture
def retenues(pisen):
    """La simulation enregistrée : deux références au critère général, deux au critère 5 (une
    seule y porte les points)."""
    hyd = Domaine.objects.get(code="HYD")
    eies = Mission.objects.create(
        code="GIC-HYD-ETU-033",
        domaine=hyd,
        nature="ETU",
        annee=2016,
        intitule="EIES du barrage de Samé",
        montant=Decimal(25000000),
    )
    par = Mission.objects.create(
        code="GIC-HYD-ETU-040", domaine=hyd, nature="ETU", annee=2021, intitule="PAR de Kouriba"
    )
    for m in (eies, par):  # justifiées : garde, signature et attestation (règle du 09/11/2026)
        justifier(m)
    c2, c5 = pisen.criteres.get(code="2"), pisen.criteres.get(code="5")
    for rang, (c, m) in enumerate(((c2, par), (c2, eies), (c5, eies)), start=1):
        Selection.objects.create(critere=c, mission=m, rang=rang, preuve="a_auditer", retenue=True)
    # sans points, mais elle répond au critère : jointe en D.2.1 (règle du 09/11/2026)
    Selection.objects.create(critere=c5, mission=par, rang=9, preuve="a_auditer")
    PieceAdministrative.objects.create(
        type=TypePiece.objects.get(code="NIF"),
        chemin=NIF,
        empreinte="nif".ljust(64, "0"),
        date_emission=date(2020, 1, 6),
    )
    pisen.simulee_le = timezone.now()
    pisen.save()
    return eies, par


def test_la_fiche_compte_les_references_retenues(client, pisen, retenues):
    page = html(client.get(f"/avis/{pisen.pk}/", **DIR))
    for code in INTERCALAIRES:
        assert f'data-rubrique="{code}"' in page
    assert 'data-rubrique="A.3"' not in page  # sans groupement : ni accord ni procuration
    assert 'data-rubrique="D.2.3"' not in page  # le critère 7 est en brouillon
    assert f"{EIES}<" in page  # le libellé tel quel, sans capitales
    assert "2 références du bureau" in page  # D.1 : toutes les références
    assert "aucune référence ne répond" in page  # D.2.2


def test_le_dossier_page_par_page(client, pisen, retenues):
    page = html(client.get(f"/avis/{pisen.pk}/dossier", **VUE))
    assert "<title>Dossier · N°005/MEHA/PISEN/2026</title>" in page
    assert page.count('data-genre="intercalaire"') == len(INTERCALAIRES)
    assert page.count('data-genre="liste"') == 2  # D.1 et D.2.1 ; D.2.2 n'a rien de retenu
    assert page.count('data-genre="fiche"') == 4  # les deux en D.1, puis les deux en D.2.1
    assert page.count('<section class="page page-couverture"') == 1  # un seul cadre
    # en-tête et pied du dossier : sommaire, intercalaires et organigramme, pas ailleurs
    entetes = 1 + len(INTERCALAIRES) + 1
    assert page.count('<header class="hf-haut">') == entetes
    assert page.count("Manifestation d’Intérêt <small>n° 005/MEHA/PISEN/2026</small>") == entetes
    assert page.count(f'<footer class="hf-bas">{OBJET}</footer>') == entetes
    assert "RÉPUBLIQUE DU NIGER" in page and "Fraternité – Travail – Progrès" in page
    # une adresse par usage, comme dans les vrais dossiers (décision du porteur, 07/11/2026)
    siege = "Siège social : Baco-djicoroni ACI GOLF Rue : 414 Porte : 302 Bamako ;"
    assert f"{siege}<br>Contact : BP. E1773 – Tél. : 20 28 02 10/74 45 13 29</p>" in page
    assert "Bacodjicoroni-ext sud, Rue : 839 Porte : 523 ;" in page  # la page d'adresse
    assert "L’attention de Monsieur le Coordonnateur National du PISEN, Niamey" in page
    assert "Veuillez agréer, Monsieur le Coordonnateur National, l'assurance" in page
    assert "Bamako, le ____ novembre 2026" in page and "Oumar Almahamoudou DICKO" in page
    assert "ADRESSE ET CONTACT DU CONSULTANT" in page
    # les listes : la plus récente d'abord, colonnes des listes du bureau
    assert '<td>01</td><td class="j">PAR de Kouriba</td>' in page
    assert '<td>02</td><td class="j">EIES du barrage de Samé</td>' in page
    assert "25 000 000 F CFA" in page
    assert "Baco-djicoroni aci GOLF Rue : 414 Porte : 302 Bamako ; Mali" in page
    # les pièces à leur place, avec leur chemin ; ce qui manque, marqué
    assert page.count(GARDE) == 2 and NIF in page
    assert "PIÈCE À INSÉRER" in page and "PAGE MANQUANTE" in page
    assert "fiche au format Banque mondiale pas encore au registre" in page


def test_d1_et_d2_les_references_justifiees_sauf_les_exclues(pisen, retenues):
    """Règles du porteur (09/11/2026), comme dans SOMAPEP : D.1 donne toutes les références du
    bureau, sauf les absorbées ; D.2.x toutes celles qui répondent, sauf les exclues ; en D.1
    comme en D.2, seulement les justifiées (garde, signature et attestation)."""
    eies, par = retenues
    hyd = Domaine.objects.get(code="HYD")
    sans_pieces = Mission.objects.create(
        code="GIC-HYD-CTR-001", domaine=hyd, nature="CTR", annee=2012, intitule="Contrôle"
    )
    absorbee = Mission.objects.create(
        code="GIC-HYD-ETU-041", domaine=hyd, nature="ETU", annee=2016, absorbee_par=eies
    )
    justifier(absorbee)
    c5 = pisen.criteres.get(code="5")
    Selection.objects.create(critere=c5, mission=sans_pieces, rang=10, preuve="manquante")

    def fiches(rubrique: str) -> list[str]:
        pages = services.plan_dossier(pisen).pages
        return [p.reference for p in pages if p.rubrique == rubrique and p.genre == "fiche"]

    assert fiches("D.1") == ["GIC-HYD-ETU-040", "GIC-HYD-ETU-033"]  # ni CTR-001 ni ETU-041
    assert fiches("D.2.1") == ["GIC-HYD-ETU-040", "GIC-HYD-ETU-033"]
    etats = {r.code: r.etat for r in services.sommaire(pisen)}
    hors = "1 référence sans ses trois pièces, hors du dossier"
    assert etats["D.1"] == f"2 références du bureau ; {hors}"
    assert etats["D.2.1"] == f"2 références ; {hors}"
    dicko = get_user_model().objects.create_user("GICONSEILS\\dicko")
    services.choisir(c5, par, "exclure", "hors sujet", dicko)
    assert fiches("D.2.1") == ["GIC-HYD-ETU-033"]
    assert "GIC-HYD-ETU-040" in fiches("D.1")  # exclue d'un critère, pas du bureau


def test_la_lettre_et_la_rubrique_se_saisissent(client, pisen):
    formulaire = html(client.get(f"/avis/{pisen.pk}/modifier", **DIR))
    assert 'id="avis-destinataire"' in formulaire and 'id="avis-formule_appel"' in formulaire
    c = pisen.criteres.get(code="5")
    assert 'id="critere-experience"' in html(client.get(f"/avis/{pisen.pk}/critere/{c.pk}", **DIR))
