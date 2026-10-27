"""ADR 0014 § 3 — recodage des références VRD avant la production : la base."""

from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from references import recodage
from references.models import Mission, PieceJustificative
from referentiel.models import Domaine
from suivi.models import JournalAcces

pytestmark = pytest.mark.django_db
TABLE = "﻿Ancien;Nouveau;Domaine;Secondaires\nGIC-VRD-ETC-001;GIC-RTE-ETC-001;RTE;AEP\n"
QUAI = "Études et contrôle de la réhabilitation du quai fluvial de Gao et de 4000 ml de caniveaux"


@pytest.fixture
def quai():
    vrd = Domaine.objects.create(code="VRD", libelle="Voirie et réseaux divers", ordre=70)
    m = Mission.objects.create(code="GIC-VRD-ETC-001", domaine=vrd, nature="ETC", intitule=QUAI)
    for i, type_ in enumerate(("garde", "signature", "attestation")):
        PieceJustificative.objects.create(
            mission=m,
            type=type_,
            chemin=f"REFERENCES\\02_JUSTIFICATIFS\\GIC-VRD-ETC-001\\{type_.upper()}.pdf",
            empreinte=f"{i:064d}",
        )
    return m


def test_lire_la_table():
    (ligne,) = recodage.lire_table(TABLE)
    assert ligne == recodage.Ligne("GIC-VRD-ETC-001", "GIC-RTE-ETC-001", "RTE", ("AEP",))
    with pytest.raises(ValueError, match="Secondaires"):
        recodage.lire_table("Ancien;Nouveau;Domaine\n")


def test_simulation_puis_recodage(quai):
    lignes = recodage.lire_table(TABLE)
    simule = recodage.recoder(lignes, simuler=True)
    assert simule.faits == ["GIC-VRD-ETC-001 -> GIC-RTE-ETC-001 (3 pièce(s))"]
    assert simule.retires == ["VRD"] and Mission.objects.filter(code="GIC-VRD-ETC-001").exists()

    rapport = recodage.recoder(lignes, par="GICONSEILS\\administrateur")
    assert rapport.resume == "1 recodée(s), 0 déjà faite(s), 0 erreur(s)"
    m = Mission.objects.get(pk=quai.pk)
    assert m.code == "GIC-RTE-ETC-001" and m.domaine.code == "RTE"
    assert list(m.domaines_secondaires.values_list("code", flat=True)) == ["AEP"]
    chemins = sorted(m.pieces.values_list("chemin", flat=True))
    assert chemins[0] == "REFERENCES\\02_JUSTIFICATIFS\\GIC-RTE-ETC-001\\ATTESTATION.pdf"
    assert not Domaine.objects.filter(code="VRD").exists()
    journal = JournalAcces.objects.get(action="reference:recodage")
    assert journal.cible == "GIC-VRD-ETC-001 -> GIC-RTE-ETC-001"

    deja = recodage.recoder(lignes)
    assert deja.passes == ["GIC-VRD-ETC-001 : déjà GIC-RTE-ETC-001"] and not deja.faits


def test_lignes_refusees(quai):
    erreurs = recodage.recoder(
        [
            recodage.Ligne("GIC-VRD-ETC-001", "GIC-RTE-CTR-099", "RTE"),
            recodage.Ligne("GIC-VRD-ETC-001", "GIC-AEP-ETC-001", "RTE"),
            recodage.Ligne("GIC-VRD-ETC-001", "GIC-XYZ-ETC-001", "XYZ"),
            recodage.Ligne("GIC-VRD-ETU-404", "GIC-BAT-ETU-404", "BAT"),
        ]
    ).erreurs
    assert erreurs == [
        "GIC-RTE-CTR-099 : nature CTR, la référence est ETC",
        "GIC-AEP-ETC-001 : le code ne commence pas par le domaine RTE",
        "GIC-VRD-ETC-001 : domaine inconnu XYZ",
        "GIC-VRD-ETU-404 : référence introuvable",
    ]
    assert Mission.objects.get(pk=quai.pk).code == "GIC-VRD-ETC-001"


def test_refuse_en_production(quai, settings):
    settings.ENVIRONNEMENT = "prod"
    with pytest.raises(recodage.RecodageRefuseError):
        recodage.recoder(recodage.lire_table(TABLE))


def test_commande(quai, tmp_path):
    table = tmp_path / "table.csv"
    table.write_text(TABLE, encoding="utf-8")
    sortie = StringIO()
    call_command("references_recoder", str(table), "--simuler", stdout=sortie)
    assert "SIMULÉ GIC-VRD-ETC-001 -> GIC-RTE-ETC-001" in sortie.getvalue()
    assert "SERAIT RETIRÉ domaine VRD" in sortie.getvalue()
    call_command("references_recoder", str(table), stdout=StringIO())
    assert Mission.objects.filter(code="GIC-RTE-ETC-001").exists()
    with pytest.raises(CommandError):
        call_command("references_recoder", str(tmp_path / "absente.csv"))
