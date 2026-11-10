"""AV15 (ADR 0019) — les mots-clés d'un critère trouvent aussi les termes validés du même type
d'ouvrage, dans le pays de l'avis : « AEPS » au Burkina retrouve nos AES du Mali."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from html import unescape

import pytest
from django.test import override_settings
from freezegun import freeze_time

from administratif.tests.conftest import DIR, IIS
from avis import services
from avis.models import Avis, Critere
from references.models import Mission
from referentiel.models import Domaine, Terme, TypeOuvrage

pytestmark = pytest.mark.django_db
SANS_PIECES = {"pieces_completes_requises": False}


def html(r) -> str:
    return unescape(r.content.decode())


@pytest.fixture(autouse=True)
def le_10_novembre():
    with freeze_time("2026-11-10 10:00"), override_settings(**IIS):
        yield


@pytest.fixture
def references():
    aep = Domaine.objects.get(code="AEP")
    gao = Mission.objects.create(
        code="GIC-AEP-CTR-902",
        domaine=aep,
        nature="CTR",
        annee=2025,
        intitule="Contrôle de forages, d'un CSCOM et d'adductions d'eau sommaire autour de Gao",
    )
    Mission.objects.create(
        code="GIC-RTE-ETU-901",
        domaine=Domaine.objects.get(code="RTE"),
        nature="ETU",
        annee=2012,
        intitule="Études de 67 km de pistes rurales à Do",
    )
    return gao


@pytest.fixture
def termes():
    aes = TypeOuvrage.objects.get(cle="aes")
    valide = {"statut": Terme.Statut.VALIDE, "origine": Terme.Origine.COLLECTE}
    Terme.objects.create(type_ouvrage=aes, terme="AEPS", pays="Burkina Faso", **valide)
    Terme.objects.create(type_ouvrage=aes, terme="mini-adduction d'eau potable", **valide)
    # proposé par la collecte, pas encore validé : il ne compte pas (règle 3)
    Terme.objects.create(type_ouvrage=aes, terme="PEA", pays="Togo", origine="collecte")


def un_avis(pays: str, mots_cles: list[str]) -> Avis:
    a = Avis.objects.create(
        reference=f"AMI-{pays}",
        objet="Contrôle d'ouvrages d'eau",
        type=Avis.Type.AMI,
        pays=pays,
        date_limite=date(2026, 12, 15),
    )
    Critere.objects.create(
        avis=a,
        code="1",
        libelle=f"Expériences : {', '.join(mots_cles)}",
        mode="par_mission",
        points_par_mission=Decimal(2),
        plafond=Decimal(10),
        filtre={"mots_cles": mots_cles, **SANS_PIECES},
    )
    return a


def test_le_lexique_reprend_libelles_sigles_et_termes_valides(termes):
    lexique = {(t.texte, t.type_ouvrage, t.pays) for t in services.lexique()}
    assert ("Adduction d'eau sommaire", "aes", "") in lexique  # libellé sans la parenthèse
    assert ("AES", "aes", "") in lexique  # sigle du libellé
    assert ("AEPS", "aes", "Burkina Faso") in lexique
    assert not any(t[0] == "PEA" for t in lexique)  # proposé : pas encore


def test_un_avis_du_burkina_trouve_nos_aes(references, termes):
    resultat = services.calculer(un_avis("Burkina Faso", ["AEPS"]))
    (rc,) = resultat.criteres
    assert [x.reference.code for x in rc.candidates] == ["GIC-AEP-CTR-902"]
    assert rc.candidates[0].par_termes == ("Adduction d'eau sommaire",)
    assert resultat.note_possible == Decimal(2)


def test_le_meme_terme_ne_vaut_pas_dans_un_autre_pays(references, termes):
    (rc,) = services.calculer(un_avis("Niger", ["AEPS"])).criteres
    assert rc.candidates == []


def test_un_terme_propose_ne_compte_pas(references, termes):
    (rc,) = services.calculer(un_avis("Togo", ["PEA"])).criteres
    assert rc.candidates == []


def test_un_terme_sans_pays_vaut_partout(references, termes):
    (rc,) = services.calculer(un_avis("Cameroun", ["mini-adductions d'eau potable"])).criteres
    assert [x.reference.code for x in rc.candidates] == ["GIC-AEP-CTR-902"]


def test_la_simulation_et_la_fiche_disent_par_quel_terme(client, references, termes):
    a = un_avis("Burkina Faso", ["AEPS"])
    page = html(client.get(f"/avis/{a.pk}/simulation", **DIR))
    assert "GIC-AEP-CTR-902" in page
    assert "trouvée par le terme « Adduction d'eau sommaire », équivalent du mot-clé" in page
    assert "dont 1 par un terme équivalent" in html(client.get(f"/avis/{a.pk}/", **DIR))


def test_l_apercu_d_un_critere_compte_les_termes_equivalents(client, references, termes):
    a = un_avis("Burkina Faso", ["AEPS"])
    donnees = {
        "code": "2",
        "ordre": "2",
        "libelle": "Contrôle d'AEPS",
        "mode": "par_mission",
        "experience": "specifique",
        "points_par_mission": "2",
        "plafond": "10",
        "nb_min_missions": "0",
        "annees_seuil": "0",
        "points_socle": "0",
        "points_par_annee": "0",
        "mots_cles": "AEPS",
        "pieces": "aucune",
        "action": "apercu",
    }
    page = html(client.post(f"/avis/{a.pk}/critere", donnees, **DIR))
    assert "1 référence retenue" in page
    assert "Dont 1 trouvée par un terme équivalent d'un mot-clé" in page


def test_la_recherche_des_outils_mcp_lit_les_termes_sans_pays(references, termes):
    total, candidates = services.rechercher({"mots_cles": ["AES"], **SANS_PIECES})
    assert total == 1 and candidates[0].par_termes == ("Adduction d'eau sommaire",)
    total, _ = services.rechercher({"mots_cles": ["AEPS"], **SANS_PIECES})
    assert total == 0  # un terme du Burkina : le pays de l'avis n'est pas connu ici
