import json
import time
from datetime import datetime

import pytest
from django.test import override_settings

from conftest import PROJET_052
from suivi.models import Employe, Poste, Segment

pytestmark = pytest.mark.django_db

URL = "/api/segments"
IIS = {"IDENTITE_SOURCE": "iis", "IDENTITE_LECTEUR_GROUPES": None}
AWA = {"REMOTE_USER": "GICONSEILS\\a.traore"}


def poster(client, lot, **meta):
    return client.post(URL, data=json.dumps(lot), content_type="application/json", **meta)


@override_settings(**IIS)
def test_lot_valide_insere_classe_et_met_le_poste_a_jour(client, dossiers, faire_lot):
    r = poster(client, faire_lot(3), **AWA)
    assert r.status_code == 200 and r.json() == {"recu": True, "deja_recu": False, "segments": 3}
    segs = list(Segment.objects.order_by("debut"))
    assert len(segs) == 3
    assert all(s.statut_classement == "dossier" and s.dossier == dossiers[0] for s in segs)
    assert segs[0].duree_s == 600 and segs[0].etat == "ACTIF"
    employe = Employe.objects.get()
    assert (
        employe.login == "giconseils\\a.traore"
        and employe.utilisateur.login_windows == "giconseils\\a.traore"
    )
    assert employe.sid_ad is None  # l'agent 0.2 n'envoie pas le SID
    poste = Poste.objects.get(nom="PC-ETUDES-01")
    assert poste.version_agent == "0.2.0" and poste.dernier_envoi is not None


@override_settings(**IIS)
def test_meme_lot_deux_fois_une_seule_insertion(client, dossiers, faire_lot):
    lot = faire_lot(2)
    assert poster(client, lot, **AWA).json()["segments"] == 2
    r = poster(client, lot, **AWA)
    assert r.status_code == 200 and r.json() == {"recu": True, "deja_recu": True, "segments": 0}
    assert Segment.objects.count() == 2


@override_settings(**IIS)
def test_usurpation_refusee(client, dossiers, faire_lot):
    # le lot dit « m.keita », la requête est authentifiée a.traore
    r = poster(client, faire_lot(1, utilisateur="m.keita"), **AWA)
    assert r.status_code == 403 and Segment.objects.count() == 0 and Employe.objects.count() == 0


@override_settings(**IIS)
def test_utilisateur_avec_domaine_accepte(client, dossiers, faire_lot):
    assert (
        poster(client, faire_lot(1, utilisateur="GICONSEILS\\A.Traore"), **AWA).status_code == 200
    )


@override_settings(**IIS)
def test_lot_vide_tient_le_poste_vivant(client, faire_lot):
    r = poster(client, faire_lot(0, poste="PC-TERRAIN-03"), **AWA)
    assert r.status_code == 200 and r.json()["segments"] == 0
    assert Poste.objects.get(nom="PC-TERRAIN-03").dernier_envoi is not None
    assert Segment.objects.count() == 0


@override_settings(**IIS)
def test_lot_invalide_400_avec_le_detail(client, faire_lot):
    lot = faire_lot(2)
    lot["segments"][0]["fin"] = "2026-10-07T07:00:00"  # avant debut
    lot["segments"][1]["etat"] = "PAUSE"
    r = poster(client, lot, **AWA)
    assert r.status_code == 400
    erreurs = r.json()["erreurs"]
    assert any("segments[0]" in e and "fin avant debut" in e for e in erreurs)
    assert any("segments[1]" in e and "PAUSE" in e for e in erreurs)
    assert Segment.objects.count() == 0 and Poste.objects.count() == 0

    assert poster(client, {**faire_lot(0), "lot_id": "pas-un-uuid"}, **AWA).status_code == 400
    r = client.post(URL, data="{ pas du json", content_type="application/json", **AWA)
    assert r.status_code == 400 and r.json() == {"erreurs": ["JSON invalide"]}


@override_settings(**IIS)
def test_sans_identite_401_et_get_405(client, faire_lot):
    assert poster(client, faire_lot(1)).status_code == 401
    assert client.get(URL, **AWA).status_code == 405


@override_settings(**IIS)
def test_classement_a_la_reception(client, dossiers, faire_lot):
    bureau = faire_lot(1, chemin=r"C:\Users\awa\Desktop\notes.pdf", application="Acrobat.exe")
    sans_fichier = faire_lot(1, chemin=None, application="explorer.exe")
    brouillon = faire_lot(1, chemin=None)
    brouillon["segments"][0]["fichier"] = "Document1"
    inconnu = faire_lot(
        1, chemin=r"\\AD-SERVEUR\GIC\MISSIONS_EN_COURS\GIC-AEP-CTR-003_Kayes\a.docx"
    )
    for lot in (bureau, sans_fichier, brouillon, inconnu):
        assert poster(client, lot, **AWA).status_code == 200
    statuts = {
        s.chemin or s.fichier or s.application: s.statut_classement for s in Segment.objects.all()
    }
    assert statuts[r"C:\Users\awa\Desktop\notes.pdf"] == "a_classer"
    assert statuts["explorer.exe"] == "application"
    assert statuts["Document1"] == "brouillon"
    # dossier conforme mais jamais vu : à classer jusqu'à A02 (dossiers détectés)
    assert statuts[inconnu["segments"][0]["chemin"]] == "a_classer"


@override_settings(**IIS)
def test_sid_envoye_devient_la_cle_et_le_login_suit(client, dossiers, faire_lot):
    lot = {**faire_lot(1), "sid": "S-1-5-21-1000-1101"}
    assert poster(client, lot, **AWA).status_code == 200
    e = Employe.objects.get()
    assert e.sid_ad == "S-1-5-21-1000-1101" and e.login == "giconseils\\a.traore"
    # la personne change de login mais garde son SID : même employé
    lot2 = {**faire_lot(1, utilisateur="awa.traore"), "sid": "S-1-5-21-1000-1101"}
    assert poster(client, lot2, REMOTE_USER="GICONSEILS\\awa.traore").status_code == 200
    assert Employe.objects.count() == 1 and Employe.objects.get().login == "giconseils\\awa.traore"


@override_settings(**IIS)
def test_mille_segments_en_moins_d_une_seconde(client, dossiers, faire_lot):
    lot = faire_lot(1000, debut=datetime(2026, 10, 1, 8, 0), duree_s=30)
    t = time.perf_counter()
    r = poster(client, lot, **AWA)
    duree = time.perf_counter() - t
    assert r.status_code == 200 and Segment.objects.count() == 1000
    assert duree < 1.0, f"{duree:.2f} s"


@override_settings(**IIS)
def test_trop_de_segments_refuse(client, faire_lot):
    lot = faire_lot(0)
    lot["segments"] = [{}] * 5001
    assert poster(client, lot, **AWA).status_code == 400


def test_conftest_lot_dossier_052(faire_lot):
    assert faire_lot(1)["segments"][0]["chemin"].startswith(PROJET_052)
