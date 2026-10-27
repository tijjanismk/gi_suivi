"""AV05 (ADR 0013 § 4) — les pièces exigées par un avis, jugées à sa date limite de dépôt."""

from __future__ import annotations

from datetime import date
from html import unescape

import pytest
from django.test import override_settings

from administratif.models import PieceAdministrative, TypePiece
from administratif.services import controle_a_la_date
from administratif.tests.conftest import DIR, IIS
from avis import services
from avis.models import Avis, PieceExigee

pytestmark = pytest.mark.django_db


@pytest.fixture
def unicef():
    a = Avis.objects.create(
        reference="LRPS-MLI-2026-9206428",
        objet="Suivi et contrôle des forages",
        type=Avis.Type.DP,
        date_limite=date(2026, 10, 28),
    )
    PieceExigee.objects.create(avis=a, type=TypePiece.objects.get(code="NON-FAILLITE"))
    return a


def version(code: str, emise: date, valide: date) -> PieceAdministrative:
    return PieceAdministrative.objects.create(
        type=TypePiece.objects.get(code=code),
        chemin=f"ADMINISTRATIF\\PIECES\\{code}\\{code} {emise}.pdf",
        empreinte=f"{code}{emise}".ljust(64, "0"),
        date_emission=emise,
        valide_jusqu_au=valide,
    )


def test_etat_a_la_date_limite(unicef):
    version("NON-FAILLITE", date(2026, 7, 21), date(2026, 10, 21))
    etats = {x.type.code: x for x in services.controle_pieces(unicef)}
    assert set(etats) == set(unicef.pieces_exigees.values_list("type__code", flat=True))
    assert etats["NON-FAILLITE"].libelle_etat == "périmée 7 j avant le dépôt"
    assert etats["QUITUS-FISCAL"].a_regler  # aucune version enregistrée
    version("NON-FAILLITE", date(2026, 10, 16), date(2027, 1, 16))
    etats = {x.type.code: x for x in services.controle_pieces(unicef)}
    assert etats["NON-FAILLITE"].libelle_etat == "valide · 80 j de marge"


def test_seulement_les_pieces_de_l_avis():
    lignes = controle_a_la_date(date(2026, 10, 28), seulement=["NON-FAILLITE", "NIF"])
    assert sorted(x.type.code for x in lignes) == ["NIF", "NON-FAILLITE"]


@override_settings(**IIS)
def test_fiche_et_lien_vers_le_controle(client, unicef):
    version("NON-FAILLITE", date(2026, 7, 21), date(2026, 10, 21))
    lien = services.lien_controle(unicef)
    assert "date=2026-10-28" in lien and "avec=NON-FAILLITE" in lien
    assert "avis=LRPS-MLI-2026-9206428" in lien
    page = unescape(client.get(f"/avis/{unicef.pk}/", **DIR).content.decode())
    assert "périmée 7 j avant le dépôt" in page and f"/administratif/controle?{lien}" in page
