"""Le parcours qui résume le produit (docs/tests.md, section 3) :

trois lots d'activité d'une personne sur deux dossiers et un fichier du Bureau → la vue
d'ensemble affiche ses heures, la vue dossiers la répartition, la file « à classer » le fichier
du Bureau ; la direction rattache ce fichier → les totaux bougent ; l'export Excel contient les
mêmes chiffres. Si ce test passe, le produit fait ce qu'il promet.
"""

import json
from datetime import datetime
from io import BytesIO

import pytest
from django.test import override_settings
from openpyxl import load_workbook

from suivi.models import Dossier, RegleException, Segment

pytestmark = [pytest.mark.django_db, pytest.mark.e2e]

IIS = {"IDENTITE_SOURCE": "iis", "IDENTITE_LECTEUR_GROUPES": "tests.e2e.test_parcours.groupes"}
AWA = {"REMOTE_USER": "GICONSEILS\\a.traore"}
DIR = {"REMOTE_USER": "GICONSEILS\\directrice"}
AGENT = {"HTTP_USER_AGENT": "GiSuivi-Agent/0.2.0"}
PERIODE = "debut=2026-10-05&fin=2026-10-07"
BARGONDAGA = r"\\AD-SERVEUR\GIC\MISSIONS_EN_COURS\GIC-HYD-ETU-052_Bargondaga\Rapports\APD.docx"
KAYES = r"H:\MISSIONS_EN_COURS\GIC-AEP-CTR-003_Kayes\Plans\reseau.dwg"  # par la lettre réseau
BUREAU = r"C:\Users\a.traore\Desktop\TDR_Kayes.pdf"


def groupes(login: str) -> list[str]:
    return ["GI-Direction"] if login == "giconseils\\directrice" else []


def envoyer(client, lot):
    r = client.post(
        "/api/segments", data=json.dumps(lot), content_type="application/json", **AWA, **AGENT
    )
    assert r.status_code == 200, r.content
    return r.json()


@override_settings(**IIS)
def test_parcours_complet(client, racines, faire_lot):
    # --- 1. trois lots envoyés par l'agent d'Awa -------------------------------------------
    lundi, mardi, mercredi = (
        datetime(2026, 10, 5, 8),
        datetime(2026, 10, 6, 8),
        datetime(2026, 10, 7, 8),
    )
    assert (
        envoyer(client, faire_lot(8, debut=lundi, duree_s=1800, chemin=BARGONDAGA))["segments"] == 8
    )  # 4 h
    assert (
        envoyer(
            client, faire_lot(6, debut=mardi, duree_s=1800, chemin=KAYES, application="acad.exe")
        )["segments"]
        == 6
    )  # 3 h
    assert (
        envoyer(
            client,
            faire_lot(2, debut=mercredi, duree_s=1800, chemin=BUREAU, application="Acrobat.exe"),
        )["segments"]
        == 2
    )  # 1 h

    # les deux dossiers de projet ont été détectés, le fichier du Bureau est à classer
    assert set(Dossier.objects.values_list("code", flat=True)) == {
        "GIC-HYD-ETU-052",
        "GIC-AEP-CTR-003",
    }
    assert Segment.objects.filter(statut_classement="a_classer").count() == 2

    # Awa voit sa journée (la sienne seulement) ; la direction, tout le monde
    assert client.get("/suivi/", **AWA).status_code == 403
    assert client.get("/api/moi/aujourdhui", **AWA).json()["employe"] == "a.traore"

    # --- 2. les écrans de la direction ----------------------------------------------------
    vue = client.get(f"/suivi/?{PERIODE}", **DIR).content.decode()
    assert "8 h 00" in vue and "a.traore" in vue  # 4 + 3 + 1
    dossiers = client.get(f"/suivi/dossiers/?{PERIODE}", **DIR).content.decode()
    assert "GIC-HYD-ETU-052" in dossiers and "4 h 00" in dossiers
    assert "GIC-AEP-CTR-003" in dossiers and "3 h 00" in dossiers
    assert "à classer 1 h 00" in dossiers
    a_classer = client.get(f"/suivi/a-classer/?{PERIODE}", **DIR).content.decode()
    assert "TDR_Kayes.pdf" in a_classer and ">Rattacher<" in a_classer

    # --- 3. la direction rattache le TDR au dossier Kayes ---------------------------------
    kayes = Dossier.objects.get(code="GIC-AEP-CTR-003")
    segment = Segment.objects.filter(statut_classement="a_classer").first()
    r = client.post(
        "/suivi/a-classer/rattacher",
        {
            "segment": segment.pk,
            "dossier": kayes.pk,
            "type": "chemin",
            "retour": f"/suivi/a-classer/?{PERIODE}",
        },
        follow=True,
        **DIR,
    )
    assert "2 segment(s) rattaché(s)" in r.content.decode()
    assert RegleException.objects.filter(motif=BUREAU, dossier=kayes).exists()
    assert Segment.objects.filter(statut_classement="a_classer").count() == 0

    # les totaux ont bougé : Kayes passe de 3 h à 4 h, plus rien à classer
    dossiers = client.get(f"/suivi/dossiers/?{PERIODE}", **DIR).content.decode()
    assert "GIC-AEP-CTR-003" in dossiers and "à classer 0 h 00" in dossiers
    api = client.get(f"/api/rapports/dossiers?{PERIODE}", **DIR).json()
    par_code = {d["code"]: d["duree_s"] for d in api["dossiers"]}
    assert (
        par_code == {"GIC-HYD-ETU-052": 4 * 3600, "GIC-AEP-CTR-003": 4 * 3600}
        and api["a_classer_s"] == 0
    )

    # et le lot du Bureau renvoyé par l'agent (reprise réseau) ne crée aucun doublon
    lot_bureau = faire_lot(
        2, debut=mercredi, duree_s=1800, chemin=BUREAU, application="Acrobat.exe"
    )
    assert envoyer(client, lot_bureau)["segments"] == 2
    assert envoyer(client, lot_bureau)["deja_recu"] is True
    assert Segment.objects.count() == 18

    # --- 4. l'export Excel dit la même chose ---------------------------------------------
    r = client.get(f"/suivi/export.xlsx?{PERIODE}", **DIR)
    wb = load_workbook(BytesIO(r.content))
    synthese = wb["Synthèse"]
    assert (
        synthese["A2"].value == "a.traore" and synthese["B2"].value == 9.0
    )  # 8 h + le lot renvoyé (1 h)
    feuille = wb["Dossiers"]
    lignes = {
        feuille.cell(row=i, column=1).value: feuille.cell(row=i, column=4).value
        for i in range(2, 4)
    }
    assert lignes == {"GIC-HYD-ETU-052": 4.0, "GIC-AEP-CTR-003": 5.0}
    assert feuille["A4"].value == "Total dossiers" and feuille["D4"].value == "=SUM(D2:D3)"
    assert wb["À classer"].max_row == 1  # plus rien
