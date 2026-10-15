import pytest
from django.test import override_settings

from suivi.models import JournalAcces, RegleException, Segment

pytestmark = pytest.mark.django_db

IIS = {
    "IDENTITE_SOURCE": "iis",
    "IDENTITE_LECTEUR_GROUPES": "suivi.tests.test_vues_a_classer.groupes",
}
DIR = {"REMOTE_USER": "GICONSEILS\\directrice"}
VUE = {"REMOTE_USER": "GICONSEILS\\visionneuse"}
AWA = {"REMOTE_USER": "GICONSEILS\\a.traore"}
URL = "/suivi/a-classer/"
PERIODE = "?debut=2026-10-05&fin=2026-10-07"


def groupes(login: str) -> list[str]:
    return {
        "giconseils\\directrice": ["GI-Direction"],
        "giconseils\\visionneuse": ["GI-Direction-Lecture"],
    }.get(login, [])


@override_settings(**IIS)
def test_file_a_classer(client, jeu_de_segments):
    assert client.get(URL, **AWA).status_code == 403
    html = client.get(URL + PERIODE, **DIR).content.decode()
    assert "À classer" in html and "notes.pdf" in html and r"C:\Users\awa\Desktop\notes.pdf" in html
    assert "Awa Traoré · 1 h 00 sur 2 segments" in html
    assert ">Rattacher<" in html and "GIC-HYD-ETU-052 — Bargondaga" in html and "(détecté)" in html
    assert "Brouillons" in html and "1 segment (0 h 30)" in html
    assert JournalAcces.objects.filter(action="consulter:a_classer").exists()


@override_settings(**IIS)
def test_rattacher_fait_baisser_le_compteur(client, jeu_de_segments, dossiers):
    html = client.get(URL + PERIODE, **DIR).content.decode()
    assert "Groupes à classer" in html
    seg = Segment.objects.filter(statut_classement="a_classer").order_by("id").first()
    r = client.post(
        URL + "rattacher",
        {"segment": seg.pk, "dossier": dossiers[0].pk, "type": "chemin", "retour": URL + PERIODE},
        follow=True,
        **DIR,
    )
    assert r.status_code == 200 and r.redirect_chain[-1][0] == URL + PERIODE
    html = r.content.decode()
    assert "2 segment(s) rattaché(s) à GIC-HYD-ETU-052" in html and "chemin exact" in html
    assert "Rien à classer sur la période" in html  # le compteur est tombé à zéro
    assert Segment.objects.filter(statut_classement="a_classer").count() == 0
    regle = RegleException.objects.get()
    assert (
        regle.type == "chemin"
        and regle.dossier == dossiers[0]
        and regle.cree_par.login_windows == "giconseils\\directrice"
    )
    assert JournalAcces.objects.filter(action="rattacher").exists()


@override_settings(**IIS)
def test_rattacher_par_dossier_parent(client, jeu_de_segments, dossiers):
    seg = Segment.objects.filter(statut_classement="a_classer").first()
    r = client.post(
        URL + "rattacher",
        {"segment": seg.pk, "dossier": dossiers[1].pk, "type": "prefixe"},
        follow=True,
        **DIR,
    )
    assert r"C:\Users\awa\Desktop" in r.content.decode()
    assert RegleException.objects.get().motif == r"C:\Users\awa\Desktop"


@override_settings(**IIS)
def test_rattacher_erreurs_et_droits(client, jeu_de_segments, dossiers):
    seg = Segment.objects.filter(statut_classement="a_classer").first()
    assert (
        client.post(
            URL + "rattacher", {"segment": seg.pk, "dossier": dossiers[0].pk}, **VUE
        ).status_code
        == 403
    )
    assert (
        client.post(
            URL + "rattacher", {"segment": 9999, "dossier": dossiers[0].pk}, **DIR
        ).status_code
        == 404
    )
    assert (
        client.post(URL + "rattacher", {"segment": seg.pk, "dossier": 9999}, **DIR).status_code
        == 404
    )
    r = client.post(
        URL + "rattacher",
        {"segment": seg.pk, "dossier": dossiers[0].pk, "type": "regex"},
        follow=True,
        **DIR,
    )
    assert "type : chemin, prefixe ou mot_cle" in r.content.decode()
    deja = Segment.objects.filter(statut_classement="dossier").first()
    r = client.post(
        URL + "rattacher", {"segment": deja.pk, "dossier": dossiers[0].pk}, follow=True, **DIR
    )
    assert "plus à classer (déjà rattaché" in r.content.decode()  # l'apostrophe est échappée
    # retour hors de l'écran refusé : on revient sur la file
    r = client.post(
        URL + "rattacher",
        {"segment": seg.pk, "dossier": dossiers[0].pk, "retour": "/admin/"},
        **DIR,
    )
    assert r["Location"] == URL


@override_settings(**IIS)
def test_consultation_seule_sans_bouton(client, jeu_de_segments):
    html = client.get(URL + PERIODE, **VUE).content.decode()
    assert "notes.pdf" in html and ">Rattacher<" not in html and "Consultation seule" in html


@override_settings(**IIS)
def test_nom_seul_non_rattachable(client, employes, postes):
    from datetime import timedelta
    from uuid import uuid4

    from django.utils import timezone

    t = timezone.now() - timedelta(hours=1)
    Segment.objects.create(
        employe=employes[0],
        poste=postes[0],
        debut=t,
        fin=t + timedelta(minutes=5),
        duree_s=300,
        etat="ACTIF",
        application="chrome.exe",
        fichier="TDR.pdf",
        chemin="",
        statut_classement="a_classer",
        lot_id=uuid4(),
    )
    html = client.get(URL, **DIR).content.decode()
    assert "TDR.pdf" in html and "nom seul" in html and ">Rattacher<" not in html


@override_settings(**IIS)
def test_vue_ensemble_pointe_vers_la_file(client, jeu_de_segments):
    html = client.get("/suivi/" + PERIODE, **DIR).content.decode()
    assert (
        'href="/suivi/a-classer/?debut=2026-10-05&amp;fin=2026-10-07"' in html
        or 'href="/suivi/a-classer/?debut=2026-10-05&fin=2026-10-07"' in html
    )


def test_portees_proposees():
    from suivi.vues.a_classer import portees

    bureau = r"C:\Users\odicko\Desktop\Offre 2026\Offre Unicef\Offre Vf\Metho.docx"
    valeurs = [v for v, _ in portees(bureau, "Metho.docx")]
    assert valeurs == [
        "chemin|",
        r"prefixe|C:\Users\odicko\Desktop\Offre 2026\Offre Unicef\Offre Vf",
        r"prefixe|C:\Users\odicko\Desktop\Offre 2026\Offre Unicef",
        r"prefixe|C:\Users\odicko\Desktop\Offre 2026",
        "mot_cle|",
    ]  # jamais le Bureau entier
    assert portees(bureau)[2][1] == "tout le dossier « Offre Unicef »"
    assert portees(bureau)[-1][1] == "tout chemin contenant « Metho »"
    assert [v for v, _ in portees(r"C:\Users\odicko\Desktop\notes.pdf")] == ["chemin|", "mot_cle|"]
    temp = r"C:\Users\odicko\AppData\Local\Temp\x_Dossier.zip\a.docx"
    assert [v for v, _ in portees(temp)] == ["chemin|", "mot_cle|"]
    unc = [v for v, _ in portees(r"\\AD-SERVEUR\AMI\AMI-2026\Cameroun\Lettre.docx")]
    assert unc[1:-1] == [  # jamais le partage entier
        r"prefixe|\\AD-SERVEUR\AMI\AMI-2026\Cameroun",
        r"prefixe|\\AD-SERVEUR\AMI\AMI-2026",
    ]
    lettre = [v for v, _ in portees(r"Q:\AMI-2026\AMI-Cameroun\2. LETTRES\Lettre.docx")]
    assert lettre[-2] == r"prefixe|Q:\AMI-2026"  # jamais le lecteur entier
    profond = "Q:\\" + "\\".join(f"n{i}" for i in range(10)) + "\f.docx"
    assert len(portees(profond)) == 8  # fichier + 6 dossiers au plus + mot-clé


def _a_classer(employe, poste, chemin):
    from datetime import timedelta
    from uuid import uuid4

    from django.utils import timezone

    t = timezone.now() - timedelta(hours=1)
    return Segment.objects.create(
        employe=employe,
        poste=poste,
        debut=t,
        fin=t + timedelta(minutes=5),
        duree_s=300,
        etat="ACTIF",
        application="WINWORD.EXE",
        fichier=chemin.rsplit("\\", 1)[-1],
        chemin=chemin,
        statut_classement="a_classer",
        lot_id=uuid4(),
    )


@override_settings(**IIS)
def test_rattacher_un_dossier_plus_large(client, employes, postes, dossiers):
    base = r"C:\Users\odicko\Desktop\Offre 2026\Offre Unicef"
    seg = _a_classer(employes[0], postes[0], base + r"\Offre Vf\Metho.docx")
    _a_classer(employes[0], postes[0], base + r"\DP Unicef\Annexes.pdf")
    autre = _a_classer(employes[0], postes[0], r"C:\Users\odicko\Desktop\Autre\x.docx")
    html = client.get(URL, **DIR).content.decode()
    assert 'name="portee"' in html and "tout le dossier « Offre Unicef »" in html
    r = client.post(
        URL + "rattacher",
        {"segment": seg.pk, "dossier": dossiers[1].pk, "portee": "prefixe|" + base},
        follow=True,
        **DIR,
    )
    assert "2 segment(s) rattaché(s)" in r.content.decode()
    assert RegleException.objects.get().motif == base
    assert Segment.objects.filter(statut_classement="a_classer").get() == autre


@override_settings(**IIS)
def test_rattacher_refuse_un_dossier_qui_ne_contient_pas_le_fichier(
    client, employes, postes, dossiers
):
    seg = _a_classer(employes[0], postes[0], r"C:\Users\odicko\Desktop\Offre\a.docx")
    r = client.post(
        URL + "rattacher",
        {
            "segment": seg.pk,
            "dossier": dossiers[0].pk,
            "portee": r"prefixe|C:\Users\odicko\Desktop\Of",
        },
        follow=True,
        **DIR,
    )
    assert "ne contient pas ce fichier" in r.content.decode()
    assert not RegleException.objects.exists()
    r = client.post(
        URL + "rattacher",
        {"segment": seg.pk, "dossier": dossiers[0].pk, "portee": "chemin|"},
        follow=True,
        **DIR,
    )
    assert RegleException.objects.get().motif == r"C:\Users\odicko\Desktop\Offre\a.docx"
