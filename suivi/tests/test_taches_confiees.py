"""F01 — tâches confiées : calcul du temps passé, écran direction, « Mes tâches » dans /moi."""

from datetime import date, datetime, timedelta

import pytest
from django.test import override_settings
from django.utils import timezone
from freezegun import freeze_time

from suivi.models import JournalAcces, Tache
from suivi.taches import temps_tache

pytestmark = pytest.mark.django_db

IIS = {
    "IDENTITE_SOURCE": "iis",
    "IDENTITE_LECTEUR_GROUPES": "suivi.tests.test_taches_confiees.groupes",
}
DIR = {"REMOTE_USER": "GICONSEILS\\directrice"}
VUE = {"REMOTE_USER": "GICONSEILS\\visionneuse"}
AWA = {"REMOTE_USER": "GICONSEILS\\a.traore"}
MOUSSA = {"REMOTE_USER": "GICONSEILS\\m.keita"}
URL = "/suivi/taches/"
LUNDI = datetime(2026, 10, 5, 7, 0)


def groupes(login: str) -> list[str]:
    return {
        "giconseils\\directrice": ["GI-Direction"],
        "giconseils\\visionneuse": ["GI-Direction-Lecture"],
    }.get(login, [])


def tache(employe, dossier, **champs):
    """Une tâche créée le lundi 5 octobre 2026 à 7 h (avant les segments du jeu d'essai)."""
    with freeze_time(timezone.make_aware(LUNDI)):
        return Tache.objects.create(
            titre="Rapport APD", dossier=dossier, personne=employe, **champs
        )


# -- calcul du temps passé ---------------------------------------------------------------


def test_temps_par_dossier_et_par_fichier(jeu_de_segments, employes, dossiers):
    awa, moussa = employes
    d052, dsom = dossiers
    fin = timezone.make_aware(datetime(2026, 10, 8))
    # Awa sur le dossier 052 : lun 4 h + mar 1 h + mer 8 h = 13 h
    assert temps_tache(tache(awa, d052), fin) == 13 * 3600
    # Moussa sur 052 : lun 8 h ; sur SOMAPEP : mar 4 h
    assert temps_tache(tache(moussa, d052), fin) == 8 * 3600
    assert temps_tache(tache(moussa, dsom), fin) == 4 * 3600
    # Par fichier, quel que soit le classement : notes.pdf (à classer) compte pour Awa
    assert temps_tache(tache(awa, d052, fichiers="notes.pdf"), fin) == 3600
    assert temps_tache(tache(awa, d052, fichiers="methodo.docx\nnotes.pdf"), fin) == 4 * 3600
    # l'inactif ne compte jamais
    assert temps_tache(tache(awa, d052, fichiers="session"), fin) == 0


def test_temps_borne_par_creation_et_cloture(jeu_de_segments, employes, dossiers):
    awa, d052 = employes[0], dossiers[0]
    # créée le mercredi : seul le mercredi compte (8 h)
    with freeze_time(timezone.make_aware(datetime(2026, 10, 7, 9, 0))):
        t = Tache.objects.create(titre="x", dossier=d052, personne=awa)
    assert temps_tache(t, timezone.make_aware(datetime(2026, 10, 8))) == 8 * 3600
    # faite le lundi midi : le reste de la semaine ne compte plus
    t2 = tache(awa, d052, etat=Tache.Etat.FAITE)
    t2.faite_le = timezone.make_aware(datetime(2026, 10, 5, 12, 0))
    t2.save()
    assert temps_tache(t2, timezone.make_aware(datetime(2026, 10, 8))) == 4 * 3600


def test_retard(employes, dossiers):
    t = Tache(titre="x", dossier=dossiers[0], personne=employes[0], echeance=date(2026, 10, 6))
    assert t.en_retard(date(2026, 10, 7)) and not t.en_retard(date(2026, 10, 6))
    t.etat = Tache.Etat.FAITE
    assert not t.en_retard(date(2026, 10, 7))


# -- écran direction ---------------------------------------------------------------------


@override_settings(**IIS)
def test_confier_puis_suivre(client, jeu_de_segments, employes, dossiers):
    awa, d052 = employes[0], dossiers[0]
    assert client.get(URL, **AWA).status_code == 403
    r = client.post(
        f"{URL}creer",
        {
            "titre": "Mettre à jour le rapport APD",
            "dossier": d052.pk,
            "personne": awa.pk,
            "fichiers": "rapport.docx",
            "echeance": "2026-10-20",
        },
        follow=True,
        **DIR,
    )
    html = r.content.decode()
    assert "confiée à Awa Traoré" in html and "Mettre à jour le rapport APD" in html
    t = Tache.objects.get()
    assert t.creee_par.login_windows == "giconseils\\directrice" and t.motifs == ["rapport.docx"]
    assert JournalAcces.objects.filter(action="creer_tache").exists()
    # changer l'état : faite → date de clôture posée ; rouvrir → effacée
    client.post(f"{URL}{t.pk}/modifier", {"etat": "faite"}, **DIR)
    t.refresh_from_db()
    assert t.etat == "faite" and t.faite_le is not None
    client.post(f"{URL}{t.pk}/modifier", {"etat": "en_cours"}, **DIR)
    t.refresh_from_db()
    assert t.etat == "en_cours" and t.faite_le is None
    r = client.post(f"{URL}{t.pk}/modifier", {"etat": "inventé"}, follow=True, **DIR)
    assert "État inconnu" in r.content.decode()


@override_settings(**IIS)
def test_formulaire_incomplet_refuse(client, employes, dossiers):
    for donnees, message in [
        ({"titre": " ", "dossier": dossiers[0].pk, "personne": employes[0].pk}, "titre ne peut"),
        ({"titre": "x", "personne": employes[0].pk}, "Choisissez un dossier"),
        ({"titre": "x", "dossier": dossiers[0].pk}, "Choisissez la personne"),
        (
            {
                "titre": "x",
                "dossier": dossiers[0].pk,
                "personne": employes[0].pk,
                "echeance": "20/10",
            },
            "Échéance illisible",
        ),
    ]:
        r = client.post(f"{URL}creer", donnees, follow=True, **DIR)
        assert message in r.content.decode()
    assert not Tache.objects.exists()


@override_settings(**IIS)
def test_consultation_seule_voit_sans_agir(client, employes, dossiers):
    t = tache(employes[0], dossiers[0], echeance=date(2026, 10, 6))
    html = client.get(URL, **VUE).content.decode()
    assert "Rapport APD" in html and "Consultation seule" in html
    assert "Confier la tâche" not in html and ">Enregistrer<" not in html
    assert "en retard" in html  # échéance passée
    assert client.post(f"{URL}creer", {"titre": "x"}, **VUE).status_code == 403
    assert client.post(f"{URL}{t.pk}/modifier", {"etat": "faite"}, **VUE).status_code == 403


@override_settings(**IIS)
def test_filtres(client, employes, dossiers):
    awa, moussa = employes
    tache(awa, dossiers[0])
    faite = tache(moussa, dossiers[0], etat=Tache.Etat.FAITE)
    faite.titre = "Note de calcul"
    faite.save()
    html = client.get(URL, **DIR).content.decode()
    assert "Rapport APD" in html and "Note de calcul" not in html  # ouvertes par défaut
    assert "Note de calcul" in client.get(f"{URL}?etat=faites", **DIR).content.decode()
    html = client.get(f"{URL}?etat=toutes&personne={moussa.pk}", **DIR).content.decode()
    assert "Note de calcul" in html and "Rapport APD" not in html


# -- « Mes tâches » dans /moi ------------------------------------------------------------


@override_settings(**IIS)
def test_mes_taches_et_changement_d_etat(client, jeu_de_segments, employes, dossiers):
    awa, moussa = employes
    t = tache(awa, dossiers[0], description="Version pour le client")
    autre = tache(moussa, dossiers[0])
    autre.titre = "Tâche de Moussa"
    autre.save()
    html = client.get("/moi", **AWA).content.decode()
    assert "Mes tâches" in html and "Rapport APD" in html and "Version pour le client" in html
    assert "Tâche de Moussa" not in html  # chacun ne voit que les siennes
    assert ">Commencer<" in html and "13 h 00" in html  # temps passé calculé
    client.post(f"/moi/taches/{t.pk}", {"etat": "en_cours"}, **AWA)
    t.refresh_from_db()
    assert t.etat == "en_cours"
    client.post(f"/moi/taches/{t.pk}", {"etat": "faite"}, **AWA)
    t.refresh_from_db()
    assert t.etat == "faite" and t.faite_le is not None
    assert JournalAcces.objects.filter(action="ma_tache").count() == 2
    # une tâche faite reste visible 7 jours, puis disparaît de /moi
    assert "faite" in client.get("/moi", **AWA).content.decode()
    with freeze_time(timezone.now() + timedelta(days=8)):
        assert "Rapport APD" not in client.get("/moi", **AWA).content.decode()


@override_settings(**IIS)
def test_on_ne_touche_pas_aux_taches_des_autres(client, employes, dossiers):
    t = tache(employes[1], dossiers[0])
    assert client.post(f"/moi/taches/{t.pk}", {"etat": "faite"}, **AWA).status_code == 403
    assert client.post(f"/moi/taches/{t.pk}", {"etat": "annulee"}, **MOUSSA).status_code == 403
    assert client.get(f"/moi/taches/{t.pk}", **MOUSSA).status_code == 405
    t.refresh_from_db()
    assert t.etat == "a_faire"
    # pas de section « Mes tâches » pour qui n'a rien à faire
    assert "Mes tâches" not in client.get("/moi", **AWA).content.decode()
