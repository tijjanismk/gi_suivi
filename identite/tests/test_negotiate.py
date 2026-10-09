"""Mode « negotiate » : l'application valide elle-même le ticket Kerberos (via un authentificateur
remplaçable ; ici un faux, le vrai exige Windows et un compte porteur de SPN)."""

import pytest
from django.test import override_settings

from identite.models import Utilisateur

pytestmark = pytest.mark.django_db

NEGOTIATE = {
    "IDENTITE_SOURCE": "negotiate",
    "IDENTITE_AUTHENTIFICATEUR_NEGOTIATE": "identite.tests.test_negotiate.faux_authentifier",
    "IDENTITE_LECTEUR_GROUPES": "identite.tests.test_identite.groupes_fictifs",
}


def faux_authentifier(entete):
    if entete == "Negotiate TICKET-DIRECTRICE":
        return "GICONSEILS\\directrice", "REPONSE-MUTUELLE"
    if entete == "Negotiate TICKET-SANS-REPONSE":
        return "GICONSEILS\\visionneuse", None
    return None, None


@override_settings(**NEGOTIATE)
def test_sans_ticket_le_serveur_reclame_negotiate(client):
    r = client.get("/identite/qui-suis-je")
    assert r.status_code == 401 and r["WWW-Authenticate"] == "Negotiate"
    assert "Kerberos" in r.content.decode()
    # un ticket refusé (NTLM, horloge, autre service) : même réponse, aucune identité créée
    r = client.get("/identite/qui-suis-je", HTTP_AUTHORIZATION="Negotiate N-IMPORTE-QUOI")
    assert r.status_code == 401 and not Utilisateur.objects.exists()


@override_settings(**NEGOTIATE)
def test_ticket_accepte_identifie_et_repond_au_client(client):
    r = client.get("/identite/qui-suis-je", HTTP_AUTHORIZATION="Negotiate TICKET-DIRECTRICE")
    assert r.status_code == 200
    assert r["WWW-Authenticate"] == "Negotiate REPONSE-MUTUELLE"
    u = Utilisateur.objects.get(login_windows="giconseils\\directrice")
    assert u.direction and "GI-Direction" in u.groupes
    r = client.get("/identite/qui-suis-je", HTTP_AUTHORIZATION="Negotiate TICKET-SANS-REPONSE")
    assert r.status_code == 200 and not r.has_header("WWW-Authenticate")


@override_settings(**NEGOTIATE)
def test_x_remote_user_ignore_en_mode_negotiate(client):
    # l'en-tête posé par un proxy ne suffit plus : seul le ticket compte
    r = client.get(
        "/identite/qui-suis-je",
        HTTP_X_REMOTE_USER="giconseils\\directrice",
        REMOTE_ADDR="127.0.0.1",
    )
    assert r.status_code == 401


@override_settings(**NEGOTIATE)
def test_sante_reste_publique(client):
    assert client.get("/api/sante").json() == {"etat": "ok"}


def test_authentifier_sans_entete_ou_illisible():
    from identite.negotiate import authentifier

    assert authentifier(None) == (None, None)
    assert authentifier("Basic abc") == (None, None)
    assert authentifier("Negotiate %%%pas-du-base64") == (None, None)
