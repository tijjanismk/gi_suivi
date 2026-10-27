"""AV02 (ADR 0013 § 2) — avis, barème, sélection, pièces exigées, administration."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import override_settings

from administratif.models import TypePiece
from administratif.tests.conftest import AWA, DIR, IIS
from avis.models import Avis, Critere, PieceExigee, Selection
from moteur.avis.filtres import Preuve
from moteur.avis.notation import Mode
from references.models import Mission
from referentiel.models import Domaine

pytestmark = pytest.mark.django_db


def unicef() -> Avis:
    return Avis.objects.create(
        reference="LRPS-MLI-2026-9206428",
        objet="Suivi et contrôle des forages équipés d'AES, des latrines et du génie civil",
        type=Avis.Type.DP,
        date_limite=date(2026, 10, 28),
    )


def test_un_avis_reprend_les_pieces_exigees_par_defaut():
    TypePiece.objects.filter(code="NIF").update(actif=False)  # un type désactivé n'est pas repris
    par_defaut = set(
        TypePiece.objects.filter(exigee_par_defaut=True, actif=True).values_list("code", flat=True)
    )
    avis = unicef()
    exigees = avis.pieces_exigees.all()
    assert {p.type.code for p in exigees} == par_defaut and "NIF" not in par_defaut
    assert {p.origine for p in exigees} == {PieceExigee.Origine.PAR_DEFAUT}
    avis.objet += " (lots A à D)"
    avis.save()
    assert avis.pieces_exigees.count() == len(par_defaut)  # pas reprises une seconde fois
    non_faillite = TypePiece.objects.get(code="NON-FAILLITE")
    PieceExigee.objects.create(avis=avis, type=non_faillite)
    assert avis.pieces_exigees.get(type=non_faillite).origine == PieceExigee.Origine.AVIS
    with pytest.raises(IntegrityError), transaction.atomic():
        PieceExigee.objects.create(avis=avis, type=non_faillite)


def test_le_filtre_et_le_mode_d_un_critere_sont_verifies():
    avis = unicef()
    references = Critere(
        avis=avis,
        code="2",
        libelle="Contrôleur principal, dix dernières années, 2 points par référence",
        mode=Critere.Mode.PAR_MISSION,
        points_par_mission=Decimal(2),
        plafond=Decimal(25),
        filtre={"natures": ["CTR", "ETC"], "pieces_requises": ["bonne_fin|pv_reception"]},
    )
    references.full_clean()
    references.save()
    references.filtre = {"nature": ["CTR"]}
    with pytest.raises(ValidationError) as erreur:
        references.full_clean()
    assert erreur.value.message_dict == {"filtre": ["clé inconnue : nature"]}
    forfait = Critere(avis=avis, code="4", libelle="Agence au Mali", mode=Critere.Mode.FORFAIT)
    with pytest.raises(ValidationError) as erreur:
        forfait.full_clean()
    assert set(erreur.value.message_dict) == {"plafond"}
    doublon = Critere(avis=avis, code="2", libelle="Moyens", mode=Critere.Mode.MANUEL)
    with pytest.raises(ValidationError) as erreur:
        doublon.full_clean()
    assert set(erreur.value.message_dict) == {"__all__"}


def test_les_choix_suivent_le_moteur():
    assert set(Critere.Mode.values) == {m.value for m in Mode}
    assert set(Selection.Preuve.values) == {p.value for p in Preuve}


def test_une_reference_par_critere():
    avis = unicef()
    critere = Critere.objects.create(
        avis=avis, code="2", libelle="Références", mode=Critere.Mode.PAR_MISSION
    )
    mission = Mission.objects.create(
        code="GIC-AEP-CTR-015",
        domaine=Domaine.objects.get(code="AEP"),
        nature="CTR",
        intitule="Contrôle des travaux d'hydraulique dans les écoles des régions de Koulikoro",
    )
    selection = Selection.objects.create(critere=critere, mission=mission, preuve="a_auditer")
    assert str(selection) == "2 — GIC-AEP-CTR-015" and not selection.choix_d_une_personne
    with pytest.raises(IntegrityError), transaction.atomic():
        Selection.objects.create(critere=critere, mission=mission, preuve="prouvee")


@override_settings(**IIS)
def test_administration_sans_suppression(client):
    avis = unicef()
    assert client.get("/avis/", **DIR).url == "/admin/avis/avis/"
    assert client.get("/admin/avis/avis/", **DIR).status_code == 200
    assert client.get(f"/admin/avis/avis/{avis.pk}/change/", **DIR).status_code == 200
    assert client.get(f"/admin/avis/avis/{avis.pk}/delete/", **DIR).status_code == 403
    assert client.get("/admin/avis/avis/", **AWA).status_code != 200


@override_settings(**IIS)
def test_creation_dans_l_administration(client):
    donnees = {
        "reference": "09/2026/001/MI/SOMAPEP/DG",
        "objet": "Études d'ouvrages de recharge de la nappe",
        "type": "AMI",
        "statut": "recu",
        "pays": "Mali",
        "date_limite": "2026-10-30",
        "criteres-TOTAL_FORMS": "1",
        "criteres-INITIAL_FORMS": "0",
        "criteres-MIN_NUM_FORMS": "0",
        "criteres-MAX_NUM_FORMS": "1000",
        "criteres-0-code": "3",
        "criteres-0-libelle": "Organisation et moyens",
        "criteres-0-ordre": "3",
        "criteres-0-mode": "manuel",
        "criteres-0-points_par_mission": "0",
        "criteres-0-nb_min_missions": "0",
        "criteres-0-annees_seuil": "0",
        "criteres-0-points_socle": "0",
        "criteres-0-points_par_annee": "0",
        "criteres-0-filtre": "{}",
        "criteres-0-note_manuelle": "10",
    }
    reponse = client.post("/admin/avis/avis/add/", donnees, **DIR)
    assert reponse.status_code == 302, reponse.content.decode()[:2000]
    avis = Avis.objects.get(reference="09/2026/001/MI/SOMAPEP/DG")
    assert avis.cree_par.login_windows == "giconseils\\directrice"
    assert avis.criteres.get().note_manuelle == 10
    assert avis.pieces_exigees.count() == TypePiece.objects.filter(
        exigee_par_defaut=True, actif=True
    ).count()
