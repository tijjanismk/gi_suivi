"""AV09 (docs/outils-mcp.md, ADR 0016) — les outils MCP du module avis, appelés comme Claude les
appellera : réponses compactes, erreurs dites en clair, écriture bornée aux propositions et aux
critères en brouillon."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from avis import outils_mcp as outils
from avis import services
from avis.models import Avis, Critere, Proposition
from experts.models import Diplome, Expert
from references.models import Mission, PieceJustificative, Quantite
from referentiel.models import Client, Domaine, TypeOuvrage, TypeQuantite

pytestmark = pytest.mark.django_db


@pytest.fixture
def references():
    same = Mission.objects.create(
        code="GIC-HYD-ETU-033",
        domaine=Domaine.objects.get(code="HYD"),
        nature="ETU",
        annee=2016,
        intitule="Étude APD du barrage de Samé Ouolof",
        client=Client.objects.create(nom="Welthungerhilfe", sigle="WHH"),
    )
    same.types_ouvrage.add(TypeOuvrage.objects.get(cle="micro-barrage"))
    Quantite.objects.create(
        mission=same, type=TypeQuantite.objects.get(cle="superficie-ha"), valeur=Decimal(30)
    )
    for type_ in ("garde", "signature", "attestation"):
        PieceJustificative.objects.create(
            mission=same,
            type=type_,
            chemin=f"REFERENCES\\02_JUSTIFICATIFS\\GIC-HYD-ETU-033\\{type_.upper()}.pdf",
            empreinte=f"same-{type_}".ljust(64, "0"),
            lisible="oui",
            coherente="oui",
        )
    Mission.objects.create(
        code="GIC-AEP-CTR-015",
        domaine=Domaine.objects.get(code="AEP"),
        nature="CTR",
        annee=2019,
        intitule="Contrôle des forages dans les écoles",
    )


@pytest.fixture
def avis(references):
    a = Avis.objects.create(
        reference="AMI-ESSAI", objet="Essai", type=Avis.Type.AMI, date_limite=date(2026, 10, 30)
    )
    Critere.objects.create(
        avis=a,
        code="1",
        libelle="Études",
        mode="par_mission",
        points_par_mission=Decimal(10),
        plafond=Decimal(20),
        filtre={"natures": ["ETU", "ETC"]},
    )
    Critere.objects.create(
        avis=a,
        code="2",
        libelle="Contrôles",
        mode="par_mission",
        points_par_mission=Decimal(5),
        plafond=Decimal(10),
        filtre={"natures": ["CTR"]},
    )
    return a


def test_rechercher_missions(references):
    r = outils.rechercher_missions(natures=["ETU"])
    assert r["total"] == 1
    (m,) = r["missions"]
    assert m["code"] == "GIC-HYD-ETU-033" and m["preuve"] == "prouvee"
    assert m["quantites"] == {"superficie-ha": "30"} and m["clients"] == ["WHH", "Welthungerhilfe"]
    forages = outils.rechercher_missions(texte="forages")["missions"]
    assert [x["code"] for x in forages] == ["GIC-AEP-CTR-015"]
    assert outils.rechercher_missions(pieces_completes_requises=True)["total"] == 1
    erreur = outils.rechercher_missions(nature=["ETU"])
    assert erreur == {"erreur": "filtre : clé inconnue : nature"}


def test_detail_et_referentiel(references):
    d = outils.detail_mission("gic-hyd-etu-033")
    assert d["types_ouvrage"] == ["micro-barrage"] and len(d["pieces"]) == 3
    assert d["client"] == "Welthungerhilfe" and d["quantites"] == {"superficie-ha": "30"}
    inconnue = outils.detail_mission("GIC-XXX-ETU-001")
    assert inconnue == {"erreur": "référence inconnue : GIC-XXX-ETU-001"}
    assert len(outils.lister_referentiel("domaines")["domaines"]) == 5  # ADR 0017
    barrages = outils.lister_referentiel("types_ouvrage", "barrage")["types_ouvrage"]
    assert [o["cle"] for o in barrages] == ["micro-barrage"]
    assert "table inconnue" in outils.lister_referentiel("localites")["erreur"]


def test_simuler_et_pieces_manquantes(avis):
    s = outils.simuler_avis(avis.pk)
    notes = {c["code"]: (c["note_sure"], c["note_possible"]) for c in s["criteres"]}
    assert notes == {"1": ("10", "10"), "2": ("0", "0")}
    assert s["note_sure"] == "10" and s["verdict"] is None
    (piece,) = outils.pieces_manquantes(avis.pk)["pieces"]
    assert piece["code"] == "GIC-AEP-CTR-015" and piece["critere"] == "2"
    assert [m["piece"] for m in piece["manques"]] == ["garde", "signature", "attestation"]
    assert piece["dossier"] == "REFERENCES\\02_JUSTIFICATIFS\\GIC-AEP-CTR-015"
    assert outils.simuler_avis(999999) == {"erreur": "avis inconnu : 999999"}


def test_rechercher_experts():
    e = Expert.objects.create(nom="TOGOLA", prenoms="Youssouf", specialite="Hydrogéologie")
    Diplome.objects.create(expert=e, intitule="Ingénieur des mines", niveau="bac+5", annee=1996)
    trouves = outils.rechercher_experts(
        niveau_min="bac+5", annees_experience_min=5, specialites="hydrogéologie"
    )
    (x,) = trouves["experts"]
    assert x["nom"] == "TOGOLA Youssouf" and x["ecarts"] == [] and x["annees_estimees"]
    erreur = outils.rechercher_experts(filtre_references={"nature": ["CTR"]})
    assert erreur == {"erreur": "filtre des références : clé inconnue : nature"}


def test_proposer_filtre_critere():
    v = outils.proposer_filtre_critere("Études d'ouvrages de recharge de nappe au Mali")
    evoques = {o["cle"] for o in v["types_ouvrage"] if o["evoque"]}
    assert {"micro-barrage", "seuil-epandage", "digue-filtrante"} <= evoques
    assert v["texte_critere"].startswith("Études") and "natures" in v


def test_creer_proposition_jamais_un_avis():
    r = outils.creer_proposition({"reference": "AMI-2026-17", "type": "AMI"}, par="essai")
    p = Proposition.objects.get(pk=r["proposition_id"])
    assert p.origine == "claude" and p.statut == "a_valider" and not Avis.objects.exists()
    assert r["adresse"] == f"/avis/propositions/{p.pk}"
    assert "erreur" in outils.creer_proposition(["pas", "un", "objet"])


def test_brouillon_de_critere_ne_compte_pas(avis):
    brouillon = {
        "code": "3",
        "libelle": "Contrôles de forages",
        "mode": "par_mission",
        "points_par_mission": "5",
        "plafond": "5",
        "filtre": {"natures": ["CTR"]},
    }
    r = outils.enregistrer_brouillon_critere(avis.pk, brouillon)
    c = Critere.objects.get(pk=r["critere_id"])
    assert c.brouillon and r["adresse"] == f"/avis/{avis.pk}/critere/{c.pk}"
    assert [rc.critere.code for rc in services.calculer(avis).criteres] == ["1", "2"]
    assert "existe déjà" in outils.enregistrer_brouillon_critere(avis.pk, brouillon)["erreur"]
    faux = {**brouillon, "code": "4", "filtre": {"nature": ["CTR"]}}
    assert "filtre" in outils.enregistrer_brouillon_critere(avis.pk, faux)["erreur"]
    assert len(outils.OUTILS) == 9
