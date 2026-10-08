from datetime import date
from io import StringIO

import pytest
from django.core.management import call_command
from django.test import override_settings
from django.utils import timezone

from suivi.models import Dossier, JournalAcces, Poste, Segment
from suivi.vues.direction import _couleur
from suivi.vues.periode import selection_de

pytestmark = pytest.mark.django_db

IIS = {
    "IDENTITE_SOURCE": "iis",
    "IDENTITE_LECTEUR_GROUPES": "suivi.tests.test_vues_direction.groupes",
}
DIR = {"REMOTE_USER": "GICONSEILS\\directrice"}
VUE = {"REMOTE_USER": "GICONSEILS\\visionneuse"}
AWA = {"REMOTE_USER": "GICONSEILS\\a.traore"}
PERIODE = "?debut=2026-10-05&fin=2026-10-07"


def groupes(login: str) -> list[str]:
    return {
        "giconseils\\directrice": ["GI-Direction"],
        "giconseils\\visionneuse": ["GI-Direction-Lecture"],
    }.get(login, [])


@override_settings(**IIS)
def test_vue_ensemble_reservee_puis_affichee(client, jeu_de_segments):
    assert client.get("/suivi/", **AWA).status_code == 403
    assert client.get("/suivi/", **VUE).status_code == 200
    r = client.get("/suivi/" + PERIODE, **DIR)
    assert r.status_code == 200
    html = r.content.decode()
    assert "Vue d'ensemble" in html and "30 h 00" in html and "62.5 %" in html
    assert "Awa Traoré" in html and "Moussa Keïta" in html
    assert "18 h 00" in html and "12 h 00" in html  # barres
    assert "08:00–17:00" in html  # lundi d'Awa dans le tableau
    assert "gic:bg-green-100" in html and "gic:bg-red-100" in html  # 87.5 % et 0 %
    assert JournalAcces.objects.filter(
        action="consulter:vue_ensemble", cible="2026-10-05..2026-10-07"
    ).exists()


@override_settings(**IIS)
def test_ecran_dossiers(client, jeu_de_segments):
    assert client.get("/suivi/dossiers/", **AWA).status_code == 403
    r = client.get("/suivi/dossiers/" + PERIODE, **VUE)
    assert r.status_code == 200
    html = r.content.decode()
    assert "Dossiers" in html and "GIC-HYD-ETU-052" in html and "2026-SOMAPEP-001" in html
    assert "21 h 00" in html and "7 h 00" in html and "28 h 00" in html  # dossiers et total
    assert "détecté" in html  # SOMAPEP n'est pas encore validé
    assert "13 h 00" in html and "8 h 00" in html  # Awa et Moussa sur 052
    assert "93.3 %" in html  # 28 h rattachées sur 30 h actives
    assert (
        "à classer 1 h 00" in html and "brouillons 0 h 30" in html and "sans fichier 0 h 30" in html
    )
    assert JournalAcces.objects.filter(action="consulter:dossiers").exists()


@override_settings(**IIS)
def test_ecran_personnes(client, jeu_de_segments, employes):
    assert client.get("/suivi/personnes/", **AWA).status_code == 403
    html = client.get("/suivi/personnes/" + PERIODE, **VUE).content.decode()
    assert "Personnes suivies" in html and "Awa Traoré" in html and "Moussa Keïta" in html
    assert "18 h 00" in html and "75.0 %" in html and "12 h 00" in html and "50.0 %" in html
    assert "en dessous" in html  # Awa 75 % → moyen ; Moussa 50 % → moyen
    assert f"/suivi/personnes/{employes[0].pk}/?debut=2026-10-05" in html
    assert "mer. 7 oct. 16:30" in html.lower() or "16:30" in html  # dernière activité d'Awa


@override_settings(**IIS)
def test_fiche_personne(client, jeu_de_segments, employes):
    awa = employes[0]
    assert client.get(f"/suivi/personnes/{awa.pk}/", **AWA).status_code == 403
    r = client.get(f"/suivi/personnes/{awa.pk}/{PERIODE}&jour=2026-10-06", **DIR)
    assert r.status_code == 200
    html = r.content.decode()
    assert "Awa Traoré" in html and "Chronologie du 2026-10-06" in html
    assert "09:00 → 09:30" in html and "notes.pdf" in html and "a_classer" in html
    assert "Document1" in html and "chrome.exe" in html
    assert "GIC-HYD-ETU-052" in html and "13 h 00" in html  # fichier rapport.docx sur la période
    assert "WINWORD.EXE" in html and "Acrobat.exe" in html  # applications
    assert 'style="background: #2563eb"' in html  # légende du premier dossier
    assert "gic:ring-2" in html  # le jour choisi est marqué
    # jour par défaut : dernier jour de la période ; jour invalide : idem, pas d'erreur
    assert (
        "Chronologie du 2026-10-07"
        in client.get(f"/suivi/personnes/{awa.pk}/{PERIODE}", **DIR).content.decode()
    )
    assert client.get(f"/suivi/personnes/{awa.pk}/{PERIODE}&jour=hier", **DIR).status_code == 200
    assert client.get("/suivi/personnes/9999/", **DIR).status_code == 404
    assert JournalAcces.objects.filter(
        action="consulter:employe", cible__startswith=f"employé {awa.pk}"
    ).exists()


@override_settings(**IIS)
def test_fiche_personne_jour_sans_activite(client, jeu_de_segments, employes):
    html = client.get(
        f"/suivi/personnes/{employes[1].pk}/{PERIODE}&jour=2026-10-07", **DIR
    ).content.decode()
    assert "Rien de mesuré ce jour-là" in html


@override_settings(**IIS)
def test_etat_des_postes(client, jeu_de_segments):
    assert client.get("/suivi/postes/", **AWA).status_code == 403
    html = client.get("/suivi/postes/", **VUE).content.decode()
    assert "État des postes" in html and "PC-ETUDES-01" in html and "PC-ETUDES-02" in html
    assert "rouge — muet" in html and "sain" in html and "Versions en service : 0.2.0" in html
    assert "Awa Traoré" in html and "Moussa Keïta" in html  # dernière personne sur chaque poste
    assert "h ouvrées" in html and ">14<" in html  # démarrages de PC-ETUDES-02
    assert JournalAcces.objects.filter(action="consulter:postes").exists()
    html = client.get("/suivi/" + PERIODE, **DIR).content.decode()
    assert 'href="/suivi/postes/"' in html


@override_settings(**IIS)
def test_etat_des_postes_vide(client):
    html = client.get("/suivi/postes/", **DIR).content.decode()
    assert "Aucun poste" in html


@override_settings(**IIS)
def test_ecran_dossiers_vide(client):
    html = client.get("/suivi/dossiers/", **DIR).content.decode()
    assert "Aucun temps rattaché" in html


@override_settings(**IIS)
def test_racine_redirige_vers_la_vue_d_ensemble(client):
    r = client.get("/", **DIR)
    assert r.status_code == 302 and r["Location"] == "/suivi/journee/"  # accueil : la journée


@override_settings(**IIS)
def test_prereglages_de_periode(client):
    aujourd_hui = timezone.localdate()
    s = selection_de({"p": "7j"})
    assert s.periode.jours == 7 and s.periode.fin == aujourd_hui and s.prereglage == "7j"
    s = selection_de({"p": "semaine"})
    assert s.periode.debut.weekday() == 0 and s.periode.fin == aujourd_hui
    s = selection_de({"p": "mois"})
    assert s.periode.debut == aujourd_hui.replace(day=1)
    assert selection_de({"p": "30j"}).periode.jours == 30
    s = selection_de({"debut": "2026-10-05", "fin": "2026-10-07"})
    assert (
        s.prereglage is None
        and s.periode == s.periode
        and s.requete == "debut=2026-10-05&fin=2026-10-07"
    )
    assert selection_de({}).prereglage == "7j" and selection_de({"p": "inconnu"}).prereglage == "7j"
    # période invalide : repli sur 7 jours avec un message, pas d'erreur 400 sur un écran
    s = selection_de({"debut": "2026-10-07", "fin": "2026-10-05"})
    assert s.prereglage == "7j" and "fin avant debut" in s.erreur
    html = client.get("/suivi/?debut=2026-10-07&fin=2026-10-05", **DIR).content.decode()
    assert "7 derniers jours affichés" in html


def test_couleurs_des_cellules():
    assert _couleur("87.5", 7 * 3600) == "bien"
    assert _couleur("62.5", 5 * 3600) == "moyen"
    assert _couleur("20.0", 3600) == "faible"
    assert _couleur("0.0", 0) == "absent"
    assert _couleur(None, 0) == "repos"  # week-end sans travail
    assert _couleur(None, 3600) == "hors_prevu"  # travail un samedi


@override_settings(**IIS)
def test_vue_ensemble_sans_donnees(client):
    html = client.get("/suivi/", **DIR).content.decode()
    assert "Aucune personne active" in html and "0 h 00" in html


def test_jeu_demo_idempotent_et_effacable():
    sortie = StringIO()
    call_command("suivi_jeu_demo", "--jours", "7", stdout=sortie)
    assert "créé" in sortie.getvalue()
    n = Segment.objects.count()
    assert n > 50 and Poste.objects.filter(nom__startswith="DEMO-").count() == 4
    assert Dossier.objects.filter(code="GIC-HYD-ETU-052", valide=True).exists()
    assert Dossier.objects.filter(statut="detecte").count() == 1
    assert Segment.objects.filter(statut_classement="a_classer").exists()
    sortie = StringIO()
    call_command("suivi_jeu_demo", stdout=sortie)
    assert "existe déjà" in sortie.getvalue() and Segment.objects.count() == n
    call_command("suivi_jeu_demo", "--effacer", stdout=StringIO())
    assert (
        Segment.objects.count() == 0 and Poste.objects.filter(nom__startswith="DEMO-").count() == 0
    )
    assert Dossier.objects.count() == 4  # les dossiers restent (ils ne sont pas marqués démo)


def test_jeu_demo_deterministe():
    call_command("suivi_jeu_demo", "--jours", "5", stdout=StringIO())
    a = sorted(Segment.objects.values_list("debut", "duree_s", "application"))
    call_command("suivi_jeu_demo", "--effacer", stdout=StringIO())
    call_command("suivi_jeu_demo", "--jours", "5", stdout=StringIO())
    assert sorted(Segment.objects.values_list("debut", "duree_s", "application")) == a
    assert date.today() is not None
