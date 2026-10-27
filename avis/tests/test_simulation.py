"""AV04 (ADR 0013 § 2 et 3) — simulation d'un avis : note sûre et possible, verdict, sélection
enregistrée, choix d'une personne qui survit à la simulation suivante."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from html import unescape

import pytest
from django.test import override_settings
from freezegun import freeze_time

from administratif.tests.conftest import AWA, DIR, IIS, VUE
from avis import services
from avis.models import Avis, Critere, Selection
from references.models import Mission, PieceJustificative
from referentiel.models import Domaine

pytestmark = pytest.mark.django_db


def html(r) -> str:
    return unescape(r.content.decode())


@pytest.fixture(autouse=True)
def le_27_octobre():
    with freeze_time("2026-10-27 10:00"), override_settings(**IIS):
        yield


def mission(code: str, nature: str = "CTR", pieces: tuple[str, ...] = (), lue: bool = True):
    m = Mission.objects.create(
        code=code,
        domaine=Domaine.objects.get(code="AEP"),
        nature=nature,
        annee=2020,
        intitule=f"Contrôle des forages {code}",
    )
    for type_ in pieces:
        PieceJustificative.objects.create(
            mission=m,
            type=type_,
            chemin=f"REFERENCES\\02_JUSTIFICATIFS\\{code}\\{type_.upper()}.pdf",
            empreinte=f"{code}-{type_}".ljust(64, "0"),
            lisible="oui" if lue else "",
            coherente="oui" if lue else "",
        )
    return m


@pytest.fixture
def avis():
    a = Avis.objects.create(
        reference="LRPS-MLI-2026-9206428",
        objet="Suivi et contrôle des forages",
        type=Avis.Type.DP,
        date_limite=date(2026, 10, 28),
        seuil_eligibilite=Decimal(12),
    )
    Critere.objects.create(
        avis=a,
        code="2",
        libelle="Références de contrôle",
        mode="par_mission",
        points_par_mission=Decimal(2),
        plafond=Decimal(4),
        filtre={"natures": ["CTR"]},
    )
    Critere.objects.create(
        avis=a,
        code="3",
        libelle="Organisation",
        mode="manuel",
        plafond=Decimal(10),
        note_manuelle=Decimal(10),
    )
    trois = ("garde", "signature", "attestation")
    mission("GIC-AEP-CTR-001", pieces=trois)  # prouvée
    mission("GIC-AEP-CTR-002", pieces=trois, lue=False)  # à auditer
    mission("GIC-AEP-CTR-003")  # sans pièce
    mission("GIC-AEP-ETU-004", nature="ETU", pieces=trois)  # hors du filtre
    return a


def test_simulation_affichee_sans_rien_enregistrer(client, avis):
    page = html(client.get(f"/avis/{avis.pk}/simulation", **DIR))
    assert "éligible" in page and 'id="note-sure">12<' in page and 'id="note-possible">14<' in page
    assert "GIC-AEP-CTR-002" in page and "pièce manquante" in page
    assert not Selection.objects.exists()
    avis.refresh_from_db()
    assert avis.simulee_le is None
    assert html(client.get(f"/avis/{avis.pk}/simulation", **VUE)).count("GIC-AEP-CTR-001") >= 1
    assert client.get(f"/avis/{avis.pk}/simulation", **AWA).status_code == 403
    assert client.post(f"/avis/{avis.pk}/simulation/enregistrer", **VUE).status_code == 403


def test_enregistrer_puis_choix_qui_survit(client, avis):
    r = client.post(f"/avis/{avis.pk}/simulation/enregistrer", follow=True, **DIR)
    assert "note sûre / possible 12 / 14" in html(r)
    avis.refresh_from_db()
    assert (avis.note_sure, avis.note_possible) == (12, 14) and avis.simulee_le is not None
    selection = {s.mission.code: s for s in Selection.objects.filter(critere__code="2")}
    assert selection["GIC-AEP-CTR-001"].retenue and selection["GIC-AEP-CTR-001"].points == 2
    assert selection["GIC-AEP-CTR-002"].points_en_jeu == 2
    assert not selection["GIC-AEP-CTR-003"].retenue
    assert selection["GIC-AEP-CTR-003"].preuve == Selection.Preuve.MANQUANTE

    critere = avis.criteres.get(code="2")
    choix = f"/avis/{avis.pk}/simulation/choix"
    exclure = {"critere": critere.pk, "code": "GIC-AEP-CTR-001", "decision": "exclure"}
    sans_motif = html(client.post(choix, exclure, follow=True, **DIR))
    assert "Indiquez le motif" in sans_motif
    client.post(choix, {**exclure, "motif": "contrat contesté"}, **DIR)
    page = html(client.get(f"/avis/{avis.pk}/simulation", **DIR))
    assert "incertain" in page and "contrat contesté" in page

    client.post(f"/avis/{avis.pk}/simulation/enregistrer", **DIR)
    exclue = Selection.objects.get(critere=critere, mission__code="GIC-AEP-CTR-001")
    assert not exclue.retenue and exclue.motif == "contrat contesté" and exclue.retenue_par
    avis.refresh_from_db()
    assert (avis.note_sure, avis.note_possible) == (10, 12)

    forcer = {**exclure, "code": "GIC-AEP-ETU-004", "decision": "forcer", "motif": "même objet"}
    client.post(choix, forcer, **DIR)
    resultat = services.calculer(avis)
    (bloc,) = [rc for rc in resultat.criteres if rc.critere.code == "2"]
    assert [x.reference.code for x in bloc.candidates if x.forcee] == ["GIC-AEP-ETU-004"]

    # GIC-AEP-CTR-001 rendue au calcul et GIC-AEP-ETU-004 forcée : le plafond est atteint
    client.post(choix, {**exclure, "decision": "annuler"}, **DIR)
    assert services.calculer(avis).note_sure == 14
    inconnue = {**exclure, "code": "GIC-XXX-CTR-999", "motif": "?"}
    assert "Référence introuvable" in html(client.post(choix, inconnue, follow=True, **DIR))


def test_deux_simulations_donnent_la_meme_note(avis):
    une, deux = services.calculer(avis), services.calculer(avis)
    assert (une.note_sure, une.note_possible) == (deux.note_sure, deux.note_possible) == (12, 14)
    assert [p.code for p in une.en_jeu] == ["GIC-AEP-CTR-002"]
