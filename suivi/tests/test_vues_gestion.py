import pytest
from django.test import override_settings

from suivi.models import DemandeRecalcul, Dossier, JournalAcces

pytestmark = pytest.mark.django_db

IIS = {
    "IDENTITE_SOURCE": "iis",
    "IDENTITE_LECTEUR_GROUPES": "suivi.tests.test_vues_gestion.groupes",
}
DIR = {"REMOTE_USER": "GICONSEILS\\directrice"}
VUE = {"REMOTE_USER": "GICONSEILS\\visionneuse"}
AWA = {"REMOTE_USER": "GICONSEILS\\a.traore"}
URL = "/suivi/gestion-dossiers/"


def groupes(login: str) -> list[str]:
    return {
        "giconseils\\directrice": ["GI-Direction"],
        "giconseils\\visionneuse": ["GI-Direction-Lecture"],
    }.get(login, [])


@override_settings(**IIS)
def test_ecran_gestion(client, jeu_de_segments, dossiers, racines):
    assert client.get(URL, **AWA).status_code == 403
    html = client.get(URL, **DIR).content.decode()
    assert "Gestion des dossiers" in html
    assert (
        "Dossiers détectés à valider" in html
        and "2026-SOMAPEP-001" in html
        and "7 h 00 déjà enregistrées" in html
    )
    assert "Dossiers actifs" in html and "Bargondaga" in html and "21 h 00" in html
    assert (
        r"\\AD-SERVEUR\GIC\MISSIONS_EN_COURS" in html
        and "profondeur 1" in html
        and "1 dossier" in html
    )
    assert 'name="nom"' in html and ">Valider<" in html and ">Enregistrer<" in html
    assert JournalAcces.objects.filter(action="consulter:gestion_dossiers").exists()


@override_settings(**IIS)
def test_consultation_seule_voit_sans_boutons(client, jeu_de_segments, dossiers):
    html = client.get(URL, **VUE).content.decode()
    assert "Consultation seule" in html and ">Valider<" not in html and ">Enregistrer<" not in html
    assert "2026-SOMAPEP-001" in html  # voit quand même les détectés


@override_settings(**IIS)
def test_valider_depuis_l_ecran(client, dossiers, employes):
    detecte = dossiers[1]
    DemandeRecalcul.objects.all().delete()
    r = client.post(
        f"{URL}{detecte.pk}/valider",
        {"nom": "Recharge de nappe — SOMAPEP", "client": "SOMAPEP", "responsable": employes[1].pk},
        follow=True,
        **DIR,
    )
    assert r.status_code == 200 and r.redirect_chain[-1][0] == URL
    html = r.content.decode()
    assert "validé ; le recalcul est demandé" in html
    detecte.refresh_from_db()
    assert detecte.valide and detecte.statut == "actif" and detecte.client == "SOMAPEP"
    assert (
        detecte.responsable == employes[1]
        and detecte.valide_par.login_windows == "giconseils\\directrice"
    )
    assert DemandeRecalcul.objects.filter(traitee_le=None).count() == 1
    assert JournalAcces.objects.filter(action="valider_dossier").exists()
    # un second clic : déjà validé, message d'avertissement, rien ne change
    r = client.post(f"{URL}{detecte.pk}/valider", {"nom": "x"}, follow=True, **DIR)
    assert "déjà validé" in r.content.decode()
    detecte.refresh_from_db()
    assert detecte.nom == "Recharge de nappe — SOMAPEP"


@override_settings(**IIS)
def test_valider_nom_vide_refuse(client, dossiers):
    r = client.post(f"{URL}{dossiers[1].pk}/valider", {"nom": "  "}, follow=True, **DIR)
    assert "ne peut pas être vide" in r.content.decode()
    assert not Dossier.objects.get(pk=dossiers[1].pk).valide


@override_settings(**IIS)
def test_modifier_clore_et_rouvrir(client, dossiers, employes):
    d = dossiers[0]
    r = client.post(
        f"{URL}{d.pk}/modifier",
        {"nom": "Bargondaga — APD", "client": "DNH", "responsable": employes[0].pk},
        follow=True,
        **DIR,
    )
    assert "mis à jour" in r.content.decode()
    d.refresh_from_db()
    assert d.nom == "Bargondaga — APD" and d.client == "DNH" and d.responsable == employes[0]
    client.post(f"{URL}{d.pk}/modifier", {"nom": d.nom, "statut": "clos"}, **DIR)
    d.refresh_from_db()
    assert d.statut == "clos"
    html = client.get(URL, **DIR).content.decode()
    assert "Dossiers clos" in html and ">Rouvrir<" in html
    client.post(f"{URL}{d.pk}/modifier", {"statut": "actif"}, **DIR)
    d.refresh_from_db()
    assert d.statut == "actif"
    r = client.post(f"{URL}{d.pk}/modifier", {"statut": "detecte"}, follow=True, **DIR)
    assert "Statut inconnu" in r.content.decode()
    r = client.post(f"{URL}{d.pk}/modifier", {}, follow=True, **DIR)
    assert "Rien à modifier" in r.content.decode()
    r = client.post(f"{URL}{d.pk}/modifier", {"responsable": "9999"}, follow=True, **DIR)
    assert "Responsable inconnu" in r.content.decode()


@override_settings(**IIS)
def test_actions_interdites_a_la_consultation(client, dossiers):
    assert client.post(f"{URL}{dossiers[1].pk}/valider", {"nom": "x"}, **VUE).status_code == 403
    assert client.post(f"{URL}{dossiers[0].pk}/modifier", {"client": "x"}, **VUE).status_code == 403
    assert client.get(f"{URL}{dossiers[0].pk}/modifier", **DIR).status_code == 405
    assert client.post(f"{URL}9999/valider", {"nom": "x"}, **DIR).status_code == 404
    assert not Dossier.objects.get(pk=dossiers[1].pk).valide


@override_settings(**IIS)
def test_sans_racine_ni_dossier(client):
    html = client.get(URL, **DIR).content.decode()
    assert (
        "Aucune racine déclarée" in html
        and "Aucun dossier détecté" in html
        and "Aucun dossier actif" in html
    )
