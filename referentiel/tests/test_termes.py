"""ADR 0019 — les termes des types d'ouvrages par pays : la reprise des anciens synonymes, un
terme par type et par pays, la validation humaine (règle 3), les termes qui servent selon le pays
et la portée, l'import des décisions du porteur sur la collecte du 06/11/2026."""

from __future__ import annotations

import importlib

import pytest
from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction

from referentiel import services
from referentiel.admin import TermeForm
from referentiel.models import Terme, TypeOuvrage

pytestmark = pytest.mark.django_db
MIGRATION = importlib.import_module("referentiel.migrations.0007_termes")

ENTETE = (
    "type_ouvrage;synonyme;recommandation;pays_propose;portee_proposee;nb_avis;nb_avis_api_bm;"
    "exemple;decision (oui / non / autre type)\n"
)
DECISIONS = ENTETE + (
    "aes;AEPS;ajouter;Burkina Faso;;3;0;https://exemple.org/aeps;oui\n"
    "aes;PEA;ajouter;Burkina Faso, Niger, Togo;;6;2;;oui\n"
    "dalot;OF;déconseillé;;;4;166;;non\n"
    "aes;mini-AEP;à discuter;;;13;4;;aep\n"
    "nouveau: centre de santé;CSI;ajouter;Niger, Cameroun;;5;1;;oui\n"
    "aes;MAEP;ajouter;Bénin;;1;0;;oui\n"
    "aep;SAEP;ajouter;Sénégal;;1;2;;\n"
)


LOGIN = "GICONSEILS\\porteur"


@pytest.fixture
def porteur():
    return get_user_model().objects.create_user(LOGIN)


def test_reprise_des_synonymes_en_termes_valides():
    aes = Terme.objects.filter(type_ouvrage__cle="aes", origine=Terme.Origine.REPRISE)
    assert set(aes.values_list("terme", flat=True)) == {"AES", "adduction d'eau sommaire"}
    assert {(t.statut, t.pays, t.portee) for t in aes} == {("valide", "", "partout")}
    assert Terme.objects.filter(type_ouvrage__cle="seuil-epandage", terme="recharge de nappe")
    avant = Terme.objects.count()
    MIGRATION.reprendre(apps, None)  # rejouable : rien n'est créé deux fois
    assert Terme.objects.count() == avant


def test_un_terme_par_type_et_par_pays():
    aes, aep = TypeOuvrage.objects.get(cle="aes"), TypeOuvrage.objects.get(cle="aep")
    t = Terme.objects.create(type_ouvrage=aes, terme=" mini-AEP ", pays="Niger")
    assert t.terme == "mini-AEP" and t.cle == "mini aep"
    Terme.objects.create(type_ouvrage=aes, terme="mini-AEP", pays="Cameroun")  # autre pays
    Terme.objects.create(type_ouvrage=aep, terme="Mini AEP", pays="Niger")  # autre type
    with pytest.raises(IntegrityError), transaction.atomic():
        Terme.objects.create(type_ouvrage=aes, terme="Mini AEP", pays="Niger")  # même clé


def test_proposer_puis_valider_ou_rejeter(porteur):
    t, cree = services.proposer("aes", " AEPS ", origine="claude", pays="burkina faso", par="C")
    assert cree and (t.terme, t.pays, t.statut, t.propose_par) == (
        "AEPS",
        "Burkina Faso",
        "propose",
        "C",
    )
    assert services.proposer("aes", "aeps", origine="claude", pays="Burkina Faso")[1] is False
    assert t not in services.termes_valides()
    with pytest.raises(ValueError, match="motif"):
        services.rejeter(t, " ", porteur)
    services.valider(t, porteur)
    t.refresh_from_db()
    assert t.statut == "valide" and t.decide_par == porteur and t.decide_le is not None
    for type_ouvrage, terme, pays, portee in (
        ("inconnu", "x", "", "partout"),
        ("aes", " ", "", "partout"),
        ("aes", "PEA", "Bénin", "partout"),
        ("aes", "PEA", "", "ailleurs"),
    ):
        with pytest.raises(ValueError):
            services.proposer(type_ouvrage, terme, origine="saisie", pays=pays, portee=portee)


def test_termes_valides_selon_le_pays_et_la_portee():
    aes, piv = TypeOuvrage.objects.get(cle="aes"), TypeOuvrage.objects.get(cle="piv")
    Terme.objects.create(type_ouvrage=aes, terme="PEA", pays="Niger", statut="valide")
    Terme.objects.create(type_ouvrage=aes, terme="AEPS", pays="Burkina Faso")  # proposé
    ppm = Terme.objects.create(
        type_ouvrage=piv, terme="PPM", pays="Mali", portee="references", statut="valide"
    )
    niger = set(services.termes_valides(aes, pays="Niger").values_list("terme", flat=True))
    assert {"PEA", "AES"} <= niger and "AEPS" not in niger
    assert "PEA" not in services.termes_valides(aes, pays="Mali").values_list("terme", flat=True)
    assert ppm in services.termes_valides(pays="Mali")
    assert ppm not in services.termes_valides(pays="Mali", pour_avis=True)
    assert ppm not in services.termes_valides(pays="Niger")


def test_le_rejet_demande_un_motif_dans_l_administration():
    aes = TypeOuvrage.objects.get(cle="aes")
    donnees = {
        "type_ouvrage": aes.pk,
        "terme": "OF",
        "pays": "",
        "portee": "partout",
        "statut": "rejete",
        "origine": "saisie",
        "motif": "",
    }
    assert not TermeForm(data=donnees).is_valid()
    assert TermeForm(data={**donnees, "motif": "« of » des titres anglais"}).is_valid()


def test_import_des_decisions_du_porteur(porteur):
    lignes = services.lire_csv(DECISIONS)
    simule = services.importer_decisions(lignes, porteur, source="essai.csv", simuler=True)
    assert simule.valides == 4 and not Terme.objects.filter(origine="collecte").exists()

    r = services.importer_decisions(lignes, porteur, source="essai.csv")
    assert (r.valides, r.rejetes, r.deja, r.sans_decision) == (4, 1, 1, 1)
    assert len(r.types_a_creer) == 1 and "CSI" in r.types_a_creer[0]
    assert len(r.erreurs) == 1 and "Bénin" in r.erreurs[0]
    aeps = Terme.objects.get(terme="AEPS")
    assert (aeps.statut, aeps.pays, aeps.origine, aeps.nb_avis) == (
        "valide",
        "Burkina Faso",
        "collecte",
        3,
    )
    assert aeps.decide_par == porteur and aeps.source_url == "https://exemple.org/aeps"
    assert set(Terme.objects.filter(terme="PEA").values_list("pays", flat=True)) == {
        "Burkina Faso",
        "Niger",
        "Togo",
    }
    of = Terme.objects.get(terme="OF")
    assert of.statut == "rejete" and of.motif == "refusé dans essai.csv"

    rejoue = services.importer_decisions(lignes, porteur, source="essai.csv")
    assert (rejoue.valides, rejoue.rejetes, rejoue.deja) == (0, 0, 6)
    contraire = services.lire_csv(ENTETE + "aes;AEPS;;Burkina Faso;;;;;non\n")
    conflit = services.importer_decisions(contraire, porteur, source="essai.csv")
    assert len(conflit.conflits) == 1 and Terme.objects.get(terme="AEPS").statut == "valide"


def test_le_fichier_doit_avoir_sa_colonne_decision():
    with pytest.raises(ValueError, match="decision"):
        services.lire_csv("type_ouvrage;synonyme\naes;AEPS\n")
    with pytest.raises(ValueError, match="synonyme"):
        services.lire_csv("type_ouvrage;decision\naes;oui\n")


def test_commande_d_import(porteur, tmp_path, capsys):
    fichier = tmp_path / "synonymes-a-valider.csv"
    fichier.write_text(ENTETE + "aes;AEPS;;Burkina Faso;;3;0;;oui\n", encoding="utf-8-sig")
    call_command("referentiel_importer_termes", str(fichier), par=LOGIN, simuler=True)
    assert "Simulation" in capsys.readouterr().out and not Terme.objects.filter(terme="AEPS")
    call_command("referentiel_importer_termes", str(fichier), par=LOGIN)
    assert Terme.objects.get(terme="AEPS").statut == "valide"
    with pytest.raises(CommandError, match="utilisateur inconnu"):
        call_command("referentiel_importer_termes", str(fichier), par="personne")
