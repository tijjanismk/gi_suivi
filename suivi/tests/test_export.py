from io import BytesIO

import pytest
from django.test import override_settings
from openpyxl import load_workbook

from suivi.models import JournalAcces

pytestmark = pytest.mark.django_db

IIS = {"IDENTITE_SOURCE": "iis", "IDENTITE_LECTEUR_GROUPES": "suivi.tests.test_export.groupes"}
DIR = {"REMOTE_USER": "GICONSEILS\\directrice"}
VUE = {"REMOTE_USER": "GICONSEILS\\visionneuse"}
AWA = {"REMOTE_USER": "GICONSEILS\\a.traore"}
URL = "/suivi/export.xlsx?debut=2026-10-05&fin=2026-10-07"


def groupes(login: str) -> list[str]:
    return {
        "giconseils\\directrice": ["GI-Direction"],
        "giconseils\\visionneuse": ["GI-Direction-Lecture"],
    }.get(login, [])


def classeur(client, **meta):
    r = client.get(URL, **meta)
    assert r.status_code == 200
    assert r["Content-Type"].startswith("application/vnd.openxmlformats")
    assert r["Content-Disposition"] == 'attachment; filename="GI-Suivi_2026-10-05_2026-10-07.xlsx"'
    return load_workbook(BytesIO(r.content))


@override_settings(**IIS)
def test_six_feuilles_et_acces(client, jeu_de_segments):
    assert client.get(URL, **AWA).status_code == 403
    wb = classeur(client, **VUE)
    assert wb.sheetnames == ["Synthèse", "Dossiers", "Journées", "Fichiers", "À classer", "Postes"]
    assert JournalAcces.objects.filter(
        action="exporter:excel", cible="2026-10-05..2026-10-07"
    ).exists()


@override_settings(**IIS)
def test_synthese_valeurs_et_formules(client, jeu_de_segments):
    f = classeur(client, **DIR)["Synthèse"]
    assert [c.value for c in f[1]] == [
        "Personne",
        "Heures effectives",
        "Heures prévues",
        "% du prévu",
        "Jours travaillés",
    ]
    assert (
        f["A2"].value == "Awa Traoré"
        and f["B2"].value == 18.0
        and f["C2"].value == 24.0
        and f["E2"].value == 3
    )
    assert f["D2"].value == '=IF(C2=0,"",B2/C2)' and f["D2"].number_format == "0.0%"
    assert f["A3"].value == "Moussa Keïta" and f["B3"].value == 12.0
    assert (
        f["A4"].value == "Total"
        and f["B4"].value == "=SUM(B2:B3)"
        and f["C4"].value == "=SUM(C2:C3)"
    )
    assert f["B2"].number_format == "0.00" and f.freeze_panes == "A2" and f["A1"].font.bold
    assert f.column_dimensions["A"].width == 28
    assert "Période du 05/10/2026 au 07/10/2026" in f["A6"].value


@override_settings(**IIS)
def test_dossiers_journees_fichiers(client, jeu_de_segments):
    wb = classeur(client, **DIR)
    d = wb["Dossiers"]
    assert [c.value for c in d[1]] == [
        "Code",
        "Nom",
        "Statut",
        "Heures",
        "Awa Traoré",
        "Moussa Keïta",
    ]
    assert (
        d["A2"].value == "GIC-HYD-ETU-052"
        and d["D2"].value == 21.0
        and d["E2"].value == 13.0
        and d["F2"].value == 8.0
    )
    assert d["A3"].value == "2026-SOMAPEP-001" and d["D3"].value == 7.0
    assert d["A4"].value == "Total dossiers" and d["D4"].value == "=SUM(D2:D3)"
    assert d["E4"].value == "=SUM(E2:E3)"
    assert d["A5"].value == "À classer" and d["D5"].value == 1.0
    assert d["A6"].value == "Brouillons" and d["A7"].value == "Sans fichier"
    assert d["D7"].value == 0.5

    j = wb["Journées"]
    assert j["A2"].value == "Awa Traoré" and j["B2"].value == "2026-10-05" and j["C2"].value == 7.0
    assert j["F2"].value == "08:00" and j["G2"].value == "17:00" and j["H2"].value == 9.0
    assert j["E2"].value == '=IF(D2=0,"",C2/D2)' and j["I2"].value == '=IF(H2=0,"",C2/H2)'
    assert j["A8"].value == "Total" and j["C8"].value == "=SUM(C2:C7)"  # 2 personnes × 3 jours

    fi = wb["Fichiers"]
    assert (
        fi["B2"].value == "rapport.docx"
        and fi["F2"].value == 13.0
        and fi["D2"].value == "GIC-HYD-ETU-052"
    )
    fichiers = {
        (r[0].value, r[1].value): r[5].value
        for r in fi.iter_rows(min_row=2, max_row=fi.max_row - 1)
    }
    assert (
        fichiers[("Awa Traoré", "notes.pdf")] == 1.0
        and fichiers[("Awa Traoré", "Document1")] == 0.5
    )
    assert fi.cell(row=fi.max_row, column=6).value.startswith("=SUM(F2:F")


@override_settings(**IIS)
def test_a_classer_et_postes(client, jeu_de_segments):
    wb = classeur(client, **DIR)
    a = wb["À classer"]
    assert (
        a["A2"].value == "Awa Traoré"
        and a["B2"].value == "notes.pdf"
        and a["D2"].value == 1.0
        and a["E2"].value == 2
    )
    assert a["A3"].value == "Total" and a["D3"].value == "=SUM(D2:D2)"
    p = wb["Postes"]
    lignes = {r[0].value: r for r in p.iter_rows(min_row=2)}
    assert lignes["PC-ETUDES-01"][1].value == "sain" and lignes["PC-ETUDES-02"][1].value == "rouge"
    assert lignes["PC-ETUDES-02"][5].value == 14


@override_settings(**IIS)
def test_export_sans_donnees(client):
    wb = classeur(client, **DIR)
    assert wb["Synthèse"].max_row >= 1 and wb["Dossiers"]["A2"].value == "À classer"
    assert wb["Journées"].max_row == 1 and wb["Postes"].max_row == 1


@override_settings(**IIS)
def test_bouton_export_sur_les_ecrans(client, jeu_de_segments):
    html = client.get("/suivi/?debut=2026-10-05&fin=2026-10-07", **DIR).content.decode()
    assert "/suivi/export.xlsx?debut=2026-10-05" in html and "> Excel" in html
