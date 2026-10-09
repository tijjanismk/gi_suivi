from datetime import timedelta

import pytest
from django.contrib import admin
from django.http import HttpResponse
from django.test import RequestFactory, override_settings
from django.urls import path
from django.utils import timezone

from identite.decorateurs import consultation_requise, groupe_requis
from identite.models import Utilisateur
from identite.services import obtenir_utilisateur

pytestmark = pytest.mark.django_db


@groupe_requis("GI-Direction")
def vue_direction(request):
    return HttpResponse("ok")


@consultation_requise
def vue_consultation(request):
    return HttpResponse("ok")


urlpatterns = [
    path("essai-direction/", vue_direction),
    path("essai-consultation/", vue_consultation),
    path("admin/", admin.site.urls),  # la page de refus (thème Unfold) lie vers l'admin
]

IIS = {
    "IDENTITE_SOURCE": "iis",
    "IDENTITE_LECTEUR_GROUPES": "identite.tests.test_identite.groupes_fictifs",
}


def groupes_fictifs(login: str) -> list[str]:
    return {
        "giconseils\\directrice": ["GI-Direction", "Utilisateurs du domaine"],
        "giconseils\\visionneuse": ["GI-Direction-Lecture", "Utilisateurs du domaine"],
    }.get(login, ["Utilisateurs du domaine"])


@override_settings(**IIS)
def test_visionneuse_consulte_sans_pouvoir_agir(client):
    # l'accueil et une liste : oui ; l'ajout : non
    assert client.get("/admin/", REMOTE_USER="giconseils\\visionneuse").status_code == 200
    assert (
        client.get("/admin/suivi/racine/", REMOTE_USER="giconseils\\visionneuse").status_code == 200
    )
    assert (
        client.get("/admin/suivi/racine/add/", REMOTE_USER="giconseils\\visionneuse").status_code
        == 403
    )
    u = Utilisateur.objects.get(login_windows="giconseils\\visionneuse")
    assert u.lecture_seule and not u.direction
    assert u.has_perm("suivi.view_racine") and not u.has_perm("suivi.change_racine")
    assert not u.has_perm("suivi.add_racine") and not u.has_perm("suivi.delete_racine")


@override_settings(**IIS)
def test_direction_garde_toutes_les_actions(client):
    assert (
        client.get("/admin/suivi/racine/add/", REMOTE_USER="giconseils\\directrice").status_code
        == 200
    )
    u = Utilisateur.objects.get(login_windows="giconseils\\directrice")
    assert u.direction and not u.lecture_seule and u.has_perm("suivi.delete_racine")


@override_settings(**IIS, ROOT_URLCONF=__name__)
def test_consultation_requise_accepte_les_deux_groupes(client):
    assert (
        client.get("/essai-consultation/", REMOTE_USER="giconseils\\visionneuse").status_code == 200
    )
    assert (
        client.get("/essai-consultation/", REMOTE_USER="giconseils\\directrice").status_code == 200
    )
    assert (
        client.get("/essai-consultation/", REMOTE_USER="giconseils\\stagiaire").status_code == 403
    )
    # l'action reste réservée à la direction
    assert client.get("/essai-direction/", REMOTE_USER="giconseils\\visionneuse").status_code == 403


def test_dev_utilisateur_fictif_cree_a_la_premiere_requete(client):
    r = client.get("/identite/qui-suis-je")
    assert r.status_code == 200
    u = Utilisateur.objects.get()
    assert u.login_windows == "giconseils\\essai" and u.groupes == ["GI-Direction"]
    assert not u.has_usable_password()
    assert "giconseils\\essai" in r.content.decode()


@override_settings(**IIS)
def test_iis_sans_identite_401(client):
    assert client.get("/identite/qui-suis-je").status_code == 401


@override_settings(**IIS)
def test_iis_remote_user_cree_l_utilisateur_et_lit_ses_groupes(client):
    r = client.get("/identite/qui-suis-je", REMOTE_USER="GICONSEILS\\Directrice")
    assert r.status_code == 200
    assert Utilisateur.objects.get().groupes == ["GI-Direction", "Utilisateurs du domaine"]


@override_settings(**IIS)
def test_iis_en_tete_cru_seulement_depuis_iis_local(client):
    assert (
        client.get(
            "/identite/qui-suis-je", HTTP_X_REMOTE_USER="giconseils\\x", REMOTE_ADDR="127.0.0.1"
        ).status_code
        == 200
    )
    # Le même en-tête venu d'un poste du réseau est une tentative d'usurpation : ignoré
    assert (
        client.get(
            "/identite/qui-suis-je", HTTP_X_REMOTE_USER="giconseils\\x", REMOTE_ADDR="192.168.2.40"
        ).status_code
        == 401
    )


@override_settings(**IIS, ROOT_URLCONF=__name__)
def test_hors_groupe_403_dans_le_groupe_200(client):
    assert client.get("/essai-direction/", REMOTE_USER="giconseils\\stagiaire").status_code == 403
    assert client.get("/essai-direction/", REMOTE_USER="giconseils\\directrice").status_code == 200


@override_settings(**IIS)
def test_admin_refuse_hors_direction_sans_demander_de_mot_de_passe(client):
    r = client.get("/admin/", REMOTE_USER="giconseils\\stagiaire", follow=True)
    assert r.status_code == 403 and "Accès réservé" in r.content.decode()
    assert client.get("/admin/", REMOTE_USER="giconseils\\directrice").status_code == 200


def test_sante_sans_identite(client, settings):
    settings.IDENTITE_SOURCE = "iis"
    assert client.get("/sante/").json() == {"etat": "ok"}
    # diagnostic de la chaîne IIS -> ARR -> application : ce que l'application voit de l'appelant
    d = client.get(
        "/api/sante?identite=1",
        HTTP_X_REMOTE_USER="giconseils\\x",
        HTTP_X_FORWARDED_PROTO="https",
        REMOTE_ADDR="127.0.0.1",
    ).json()
    assert d["etat"] == "ok" and d["identite"]["remote_addr"] == "127.0.0.1"
    assert d["identite"]["x_remote_user"] == "giconseils\\x"
    assert d["identite"]["x_forwarded_proto"] == "https" and d["identite"]["remote_user"] is None


@override_settings(**IIS)
def test_groupes_rafraichis_apres_dix_minutes_seulement():
    u = obtenir_utilisateur("giconseils\\directrice")
    Utilisateur.objects.filter(pk=u.pk).update(groupes=["ancien"])
    assert obtenir_utilisateur("giconseils\\directrice").groupes == ["ancien"]  # encore valables
    Utilisateur.objects.filter(pk=u.pk).update(
        groupes_lus_le=timezone.now() - timedelta(minutes=11)
    )
    assert "GI-Direction" in obtenir_utilisateur("giconseils\\directrice").groupes


@override_settings(
    IDENTITE_SOURCE="iis", IDENTITE_LECTEUR_GROUPES="identite.tests.test_identite.annuaire_en_panne"
)
def test_annuaire_injoignable_garde_les_groupes_connus():
    u = Utilisateur.objects.create(login_windows="giconseils\\x", groupes=["GI-Direction"])
    Utilisateur.objects.filter(pk=u.pk).update(groupes_lus_le=timezone.now() - timedelta(hours=1))
    assert obtenir_utilisateur("GICONSEILS\\X").groupes == ["GI-Direction"]


@override_settings(IDENTITE_SOURCE="iis", IDENTITE_LECTEUR_GROUPES=None)
def test_sans_source_de_groupes_aucun_droit(client):
    assert client.get("/admin/", REMOTE_USER="giconseils\\x", follow=True).status_code == 403


def annuaire_en_panne(login: str) -> list[str]:
    raise ConnectionError("annuaire injoignable")


def test_login_normalise():
    assert (
        obtenir_utilisateur("  GICONSEILS\\Jean.Traore ").login_windows == "giconseils\\jean.traore"
    )


def test_requete_factory_dev():
    # le middleware n'est pas sollicité par RequestFactory : la vue décorée refuse un anonyme
    from django.contrib.auth.models import AnonymousUser

    r = RequestFactory().get("/")
    r.user = AnonymousUser()
    assert vue_direction(r).status_code == 403
