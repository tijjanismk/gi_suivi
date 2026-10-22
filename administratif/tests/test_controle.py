"""AD07, étape 1 — contrôle des pièces à une date limite de dépôt (ADR 0010, § 6)."""

from __future__ import annotations

from datetime import date
from html import unescape

import pytest
from django.test import override_settings
from freezegun import freeze_time

from administratif import services
from administratif.models import PieceAdministrative
from administratif.tests.conftest import AWA, DIR, IIS, VUE
from suivi.models import JournalAcces

pytestmark = pytest.mark.django_db
URL = "/administratif/controle"
DEPOT = date(2026, 11, 12)  # trois semaines après le 22/10 : le quitus aura expiré le 06/11


@pytest.fixture(autouse=True)
def le_22_octobre():
    with freeze_time("2026-10-22 10:00"):
        yield


def par_code(lignes):
    return {x.type.code: x for x in lignes}


def test_controle_a_la_date_de_depot(jeu):
    lignes = services.controle_a_la_date(DEPOT)
    assert [x.type.code for x in lignes[:2]] == ["QUITUS-FISCAL", "MOYENS"]  # à régler d'abord
    x = par_code(lignes)
    assert x["QUITUS-FISCAL"].a_regler and x["QUITUS-FISCAL"].libelle_etat == (
        "périmée 6 j avant le dépôt"
    )
    assert x["QUITUS-FISCAL"].demande is not None
    assert x["MOYENS"].libelle_etat == "périmée 56 j avant le dépôt"
    assert x["INPS"].libelle_etat == "valide · 31 j de marge" and not x["INPS"].a_regler
    assert x["NIF"].cle_etat == "permanente" and x["NIF"].libelle_etat == "permanente"
    assert len(lignes) == 8 and not any(x.ajoutee for x in lignes)  # les exigées par défaut
    # pièces demandées en plus par l'avis
    x = par_code(services.controle_a_la_date(DEPOT, ["TVA", "NON-FAILLITE"]))
    assert x["TVA"].ajoutee and x["TVA"].cle_etat == "manquante" and x["TVA"].a_regler
    assert x["NON-FAILLITE"].libelle_etat == "valide · 66 j de marge"


def test_version_jointe_selon_la_date(jeu):
    # au 01/08, le quitus d'août n'existait pas : c'est celui de mai qu'on aurait joint
    x = par_code(services.controle_a_la_date(date(2026, 8, 1)))
    assert x["QUITUS-FISCAL"].version.pk == jeu["remplacee"]
    assert x["QUITUS-FISCAL"].libelle_etat == "valide · 4 j de marge"
    x = par_code(services.controle_a_la_date(date(2026, 8, 5)))
    assert x["QUITUS-FISCAL"].libelle_etat == "valide le jour du dépôt, pas au-delà"
    # une version retirée n'est jamais jointe
    PieceAdministrative.objects.filter(pk=jeu["en_cours"]).update(retiree=True, motif_retrait="x")
    x = par_code(services.controle_a_la_date(date(2026, 10, 25)))
    assert x["QUITUS-FISCAL"].version.pk == jeu["remplacee"] and x["QUITUS-FISCAL"].a_regler


def test_expirations_d_ici_au_depot(jeu):
    lignes = services.controle_a_la_date(DEPOT, ["NON-FAILLITE"])
    expirations = services.expirations_d_ici(DEPOT, lignes)
    assert [x.type.code for x in expirations] == [
        "QUITUS-FISCAL"
    ]  # la liste des moyens a déjà expiré
    lignes = services.controle_a_la_date(date(2027, 2, 1), ["NON-FAILLITE"])
    assert [x.type.code for x in services.expirations_d_ici(date(2027, 2, 1), lignes)] == [
        "QUITUS-FISCAL",
        "INPS",
        "NON-FAILLITE",
    ]


def html(r) -> str:
    assert r.status_code == 200, r.status_code
    return unescape(r.content.decode())


@override_settings(**IIS)
def test_ecran_controle(client, jeu):
    page = html(client.get(URL, **DIR))  # par défaut : dans 14 jours
    assert 'value="2026-11-05"' in page and "Contrôle des pièces avant un dépôt" in page
    page = html(
        client.get(
            URL,
            {"date": "2026-11-12", "avec": ["TVA", "NIF", "INCONNU"], "avis": "AMI SOMAPEP"},
            **DIR,
        )
    )
    assert 'data-compteur="a_regler">3<' in page and 'data-compteur="valides">6<' in page
    assert "périmée 6 j avant le dépôt" in page and "demandée par l'avis" in page
    assert page.count("demandée par l'avis") == 1  # NIF est déjà exigée, INCONNU ignoré
    assert (
        "fin de validité : Certificat de situation fiscale" in page
        and "dépôt : AMI SOMAPEP" in page
    )
    assert "déposer une version" in page and "Demandée le 19/10/2026" in page
    assert 'id="avec-TVA" name="avec" value="TVA" class="gic:mt-1" checked' in page
    assert "La date limite est passée" in html(client.get(URL, {"date": "2026-08-01"}, **DIR))
    assert 'value="2026-11-05"' in html(client.get(URL, {"date": "hier"}, **DIR))
    lecture = html(client.get(URL, {"date": "2026-11-12"}, **VUE))
    assert "périmée 6 j avant le dépôt" in lecture and "déposer une version" not in lecture
    assert client.get(URL, **AWA).status_code == 403
    assert JournalAcces.objects.filter(action="consulter:controle_pieces").exists()
    assert "Contrôler avant un dépôt" in html(client.get("/administratif/", **DIR))
