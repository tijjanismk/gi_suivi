from io import BytesIO

import pytest
from django.test import override_settings
from openpyxl import load_workbook

from suivi.vues.periode import selection_de

pytestmark = pytest.mark.django_db

IIS = {
    "IDENTITE_SOURCE": "iis",
    "IDENTITE_LECTEUR_GROUPES": "suivi.tests.test_filtre_dossier.groupes",
}
DIR = {"REMOTE_USER": "GICONSEILS\\directrice"}
PERIODE = "debut=2026-10-05&fin=2026-10-07"


def groupes(login: str) -> list[str]:
    return ["GI-Direction"] if login == "giconseils\\directrice" else []


def test_selection_porte_le_dossier():
    s = selection_de({"p": "7j", "dossier": "12"})
    assert s.dossier_id == 12 and s.requete == "p=7j&dossier=12"
    assert all(lien["url"].endswith("&dossier=12") for lien in s.liens())
    assert selection_de({"dossier": "x"}).dossier_id is None
    assert selection_de({"dossier": "0"}).dossier_id is None
    assert selection_de({"debut": "2026-10-05", "fin": "2026-10-07", "dossier": "3"}).requete == (
        "debut=2026-10-05&fin=2026-10-07&dossier=3"
    )


@override_settings(**IIS)
def test_vue_ensemble_filtree_par_dossier(client, jeu_de_segments, dossiers):
    d052 = dossiers[0]
    html = client.get(f"/suivi/?{PERIODE}&dossier={d052.pk}", **DIR).content.decode()
    assert "21 h 00" in html and "13 h 00" in html and "8 h 00" in html  # 052 seulement
    assert "18 h 00" not in html  # le total d'Awa toutes activités confondues n'apparaît plus
    assert "Dossier : <strong" in html and "GIC-HYD-ETU-052</strong>" in html
    assert f'<option value="{d052.pk}" selected>' in html
    # les liens de période gardent le filtre
    assert f"?p=semaine&amp;dossier={d052.pk}" in html or f"?p=semaine&dossier={d052.pk}" in html


@override_settings(**IIS)
def test_personnes_et_fiche_filtrees(client, jeu_de_segments, dossiers, employes):
    dsom = dossiers[1]
    html = client.get(f"/suivi/personnes/?{PERIODE}&dossier={dsom.pk}", **DIR).content.decode()
    assert "3 h 00" in html and "4 h 00" in html  # Awa et Moussa sur SOMAPEP
    assert (
        f"/suivi/personnes/{employes[0].pk}/?debut=2026-10-05&amp;fin=2026-10-07&amp;dossier={dsom.pk}"
        in html
    )
    html = client.get(
        f"/suivi/personnes/{employes[0].pk}/?{PERIODE}&dossier={dsom.pk}&jour=2026-10-05", **DIR
    ).content.decode()
    assert "methodo.docx" in html and "rapport.docx" not in html
    assert "14:00 → 14:30" in html and "08:00 → 08:30" not in html


@override_settings(**IIS)
def test_dossier_inconnu_ignore(client, jeu_de_segments):
    html = client.get(f"/suivi/?{PERIODE}&dossier=9999", **DIR).content.decode()
    assert "Dossier : <strong" not in html and "Tous les dossiers" in html
    assert "30 h 00" in html


@override_settings(**IIS)
def test_export_filtre(client, jeu_de_segments, dossiers):
    r = client.get(f"/suivi/export.xlsx?{PERIODE}&dossier={dossiers[0].pk}", **DIR)
    f = load_workbook(BytesIO(r.content))["Synthèse"]
    assert f["A2"].value == "Awa Traoré" and f["B2"].value == 13.0 and f["B3"].value == 8.0


@override_settings(**IIS)
def test_ecrans_sans_filtre_dossier_n_affichent_pas_le_selecteur(client, jeu_de_segments):
    html = client.get(f"/suivi/dossiers/?{PERIODE}", **DIR).content.decode()
    assert "Tous les dossiers" not in html
