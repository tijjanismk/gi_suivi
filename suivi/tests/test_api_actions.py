import json

import pytest
from django.test import override_settings

from suivi.models import DemandeRecalcul, Dossier, JournalAcces, RegleException, Segment

pytestmark = pytest.mark.django_db

IIS = {"IDENTITE_SOURCE": "iis", "IDENTITE_LECTEUR_GROUPES": "suivi.tests.test_api_actions.groupes"}
DIR = {"REMOTE_USER": "GICONSEILS\\directrice", "REMOTE_ADDR": "192.168.2.40"}
VUE = {"REMOTE_USER": "GICONSEILS\\visionneuse"}


def groupes(login: str) -> list[str]:
    return {
        "giconseils\\directrice": ["GI-Direction"],
        "giconseils\\visionneuse": ["GI-Direction-Lecture"],
    }.get(login, [])


def envoyer(client, methode, url, corps=None, **meta):
    return getattr(client, methode)(
        url,
        data=json.dumps(corps) if corps is not None else None,
        content_type="application/json",
        **meta,
    )


@override_settings(**IIS)
def test_valider_dossier_detecte(client, jeu_de_segments, dossiers, employes):
    detecte = dossiers[1]
    DemandeRecalcul.objects.all().delete()
    r = envoyer(
        client,
        "post",
        f"/api/dossiers/{detecte.pk}/valider",
        {
            "nom": "Recharge de nappe — SOMAPEP",
            "client": "SOMAPEP",
            "responsable_id": employes[0].pk,
        },
        **DIR,
    )
    assert r.status_code == 200, r.content
    d = r.json()
    assert d["valide"] and d["statut"] == "actif" and d["client"] == "SOMAPEP"
    assert d["valide_par"] == "giconseils\\directrice" and d["responsable_id"] == employes[0].pk
    assert DemandeRecalcul.objects.filter(traitee_le=None).count() == 1
    j = JournalAcces.objects.get(action="valider_dossier")
    assert j.login == "giconseils\\directrice" and j.adresse_ip == "192.168.2.40"
    assert str(detecte.pk) in j.cible and j.utilisateur.login_windows == "giconseils\\directrice"
    # déjà validé → 409 ; inconnu → 404
    assert envoyer(client, "post", f"/api/dossiers/{detecte.pk}/valider", **DIR).status_code == 409
    assert envoyer(client, "post", "/api/dossiers/9999/valider", **DIR).status_code == 404


@override_settings(**IIS)
def test_consultation_seule_ne_peut_pas_agir(client, dossiers):
    assert (
        envoyer(client, "post", f"/api/dossiers/{dossiers[1].pk}/valider", **VUE).status_code == 403
    )
    assert (
        envoyer(
            client, "put", f"/api/dossiers/{dossiers[1].pk}", {"client": "x"}, **VUE
        ).status_code
        == 403
    )
    assert Dossier.objects.get(pk=dossiers[1].pk).valide is False
    assert (
        JournalAcces.objects.filter(action__in=["valider_dossier", "modifier_dossier"]).count() == 0
    )


@override_settings(**IIS)
def test_modifier_dossier(client, dossiers):
    d = dossiers[0]
    r = envoyer(client, "put", f"/api/dossiers/{d.pk}", {"client": "DNH", "statut": "clos"}, **DIR)
    assert r.status_code == 200 and r.json()["client"] == "DNH" and r.json()["statut"] == "clos"
    assert "client" in JournalAcces.objects.get(action="modifier_dossier").cible
    assert (
        envoyer(client, "put", f"/api/dossiers/{d.pk}", {"statut": "detecte"}, **DIR).status_code
        == 400
    )
    assert envoyer(client, "put", f"/api/dossiers/{d.pk}", {"nom": "  "}, **DIR).status_code == 400
    assert (
        envoyer(client, "put", f"/api/dossiers/{d.pk}", {"responsable_id": 9999}, **DIR).status_code
        == 400
    )
    assert envoyer(client, "put", f"/api/dossiers/{d.pk}", {}, **DIR).status_code == 400
    assert client.post(f"/api/dossiers/{d.pk}", **DIR).status_code == 405
    r = client.put(
        f"/api/dossiers/{d.pk}", data="{ pas du json", content_type="application/json", **DIR
    )
    assert r.status_code == 400


@override_settings(**IIS)
def test_rattacher_par_chemin_exact(client, jeu_de_segments, dossiers):
    seg = Segment.objects.filter(statut_classement="a_classer").first()
    r = envoyer(
        client, "post", f"/api/aclasser/{seg.pk}/rattacher", {"dossier_id": dossiers[0].pk}, **DIR
    )
    assert r.status_code == 200, r.content
    d = r.json()
    assert d["type"] == "chemin" and d["motif"] == r"C:\Users\awa\Desktop\notes.pdf"
    assert d["segments_reclasses"] == 2  # les deux segments de 30 min du groupe
    assert Segment.objects.filter(statut_classement="a_classer").count() == 0
    assert all(s.dossier == dossiers[0] for s in Segment.objects.filter(fichier="notes.pdf"))
    regle = RegleException.objects.get()
    assert regle.cree_par.login_windows == "giconseils\\directrice" and regle.dossier == dossiers[0]
    assert "rattacher" in JournalAcces.objects.get(action="rattacher").action
    # le même segment n'est plus à classer → 400
    assert (
        envoyer(
            client,
            "post",
            f"/api/aclasser/{seg.pk}/rattacher",
            {"dossier_id": dossiers[0].pk},
            **DIR,
        ).status_code
        == 400
    )


@override_settings(**IIS)
def test_rattacher_par_prefixe_couvre_le_dossier_entier(client, jeu_de_segments, dossiers):
    seg = Segment.objects.filter(statut_classement="a_classer").first()
    r = envoyer(
        client,
        "post",
        f"/api/aclasser/{seg.pk}/rattacher",
        {"dossier_id": dossiers[1].pk, "type": "prefixe"},
        **DIR,
    )
    assert r.status_code == 200 and r.json()["motif"] == r"C:\Users\awa\Desktop"
    assert RegleException.objects.get().type == "prefixe"


@override_settings(**IIS)
def test_rattacher_un_pdf_de_navigateur_par_mot_cle(client, employes, postes, dossiers):
    from datetime import datetime, timedelta
    from uuid import uuid4

    from django.utils import timezone

    t = timezone.make_aware(datetime(2026, 10, 6, 9, 0))
    seg = Segment.objects.create(
        employe=employes[0],
        poste=postes[0],
        debut=t,
        fin=t + timedelta(minutes=5),
        duree_s=300,
        etat="ACTIF",
        application="chrome.exe",
        fichier="TDR_Bargondaga.pdf",
        chemin="",
        statut_classement="a_classer",
        lot_id=uuid4(),
    )
    r = envoyer(
        client, "post", f"/api/aclasser/{seg.pk}/rattacher", {"dossier_id": dossiers[0].pk}, **DIR
    )
    assert (
        r.status_code == 200
        and r.json()["type"] == "mot_cle"
        and r.json()["motif"] == "TDR_Bargondaga"
    )
    seg.refresh_from_db()
    assert seg.statut_classement == "a_classer"  # nom seul : le moteur ne rattache que par chemin


@override_settings(**IIS)
def test_rattacher_erreurs(client, jeu_de_segments, dossiers):
    seg = Segment.objects.filter(statut_classement="a_classer").first()
    assert (
        envoyer(client, "post", f"/api/aclasser/{seg.pk}/rattacher", {}, **DIR).status_code == 404
    )  # dossier absent
    assert (
        envoyer(
            client,
            "post",
            f"/api/aclasser/{seg.pk}/rattacher",
            {"dossier_id": dossiers[0].pk, "type": "regex"},
            **DIR,
        ).status_code
        == 400
    )
    assert (
        envoyer(
            client, "post", "/api/aclasser/9999/rattacher", {"dossier_id": dossiers[0].pk}, **DIR
        ).status_code
        == 404
    )
    assert (
        envoyer(
            client,
            "post",
            f"/api/aclasser/{seg.pk}/rattacher",
            {"dossier_id": dossiers[0].pk},
            **VUE,
        ).status_code
        == 403
    )


@override_settings(**IIS)
def test_consultations_journalisees(client, jeu_de_segments):
    client.get("/api/rapports/synthese?debut=2026-10-05&fin=2026-10-07", **DIR)
    client.get("/api/postes/etat", **VUE)
    actions = list(
        JournalAcces.objects.order_by("horodatage").values_list("action", "login", "cible")
    )
    assert actions[0] == (
        "consulter:rapport_synthese",
        "giconseils\\directrice",
        "2026-10-05..2026-10-07",
    )
    assert actions[1][:2] == ("consulter:postes_etat", "giconseils\\visionneuse")


@override_settings(IDENTITE_SOURCE="iis", IDENTITE_LECTEUR_GROUPES=None)
def test_segments_refuses_sans_l_en_tete_de_l_agent(client, faire_lot):
    lot = json.dumps(faire_lot(1))
    r = client.post(
        "/api/segments",
        data=lot,
        content_type="application/json",
        REMOTE_USER="GICONSEILS\\a.traore",
    )
    assert r.status_code == 403 and "agent" in r.json()["erreur"]
    r = client.post(
        "/api/segments",
        data=lot,
        content_type="application/json",
        REMOTE_USER="GICONSEILS\\a.traore",
        HTTP_USER_AGENT="GiSuivi-Agent/0.2.0",
    )
    assert r.status_code == 200
