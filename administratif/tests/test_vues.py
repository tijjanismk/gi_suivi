"""AD03 à AD06 — écrans, droits, actions, pastille, accueil et commandes."""

from __future__ import annotations

from html import unescape
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from freezegun import freeze_time

from administratif import demo
from administratif.models import DemandeRenouvellement, PieceAdministrative, TypePiece
from administratif.tests.conftest import AWA, DIR, IIS, VUE
from suivi.models import JournalAcces

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def le_22_octobre():
    with freeze_time("2026-10-22 10:00"):
        yield


URL = "/administratif/"


def html(reponse) -> str:
    assert reponse.status_code == 200, reponse.status_code
    return unescape(reponse.content.decode())


@override_settings(**IIS)
def test_registre_compteurs_filtres_et_droits(client, jeu):
    page = html(client.get(URL, **DIR))
    assert 'data-compteur="expirees">1<' in page and 'data-compteur="a_renouveler">1<' in page
    assert "expire dans 15 j" in page and "expirée depuis 35 j" in page
    assert "Déposer une nouvelle version" in page and "Demandée le 19/10/2026" in page
    assert "À demander" in page  # la liste des moyens, expirée, sans demande
    assert page.index('data-code="MOYENS"') < page.index('data-code="NIF"')  # alertes d'abord
    assert page.index('data-code="NIF"') < page.index('data-code="TVA"')  # non requises à la fin
    a_traiter = html(client.get(URL + "?vue=a_traiter", **DIR))
    assert 'data-code="MOYENS"' in a_traiter and 'data-code="NIF"' not in a_traiter
    valides = html(client.get(URL + "?vue=valides", **DIR))
    assert 'data-code="NIF"' in valides and 'data-code="MOYENS"' not in valides
    assert 'data-code="TVA"' in html(client.get(URL + "?vue=inconnue", **DIR))
    lecture = html(client.get(URL, **VUE))
    assert "Déposer une nouvelle version" not in lecture
    assert client.get(URL, **AWA).status_code == 403
    assert JournalAcces.objects.filter(action="consulter:pieces").exists()


@override_settings(**IIS)
def test_registre_partage_non_configure(client, db, settings):
    settings.PARTAGE_GIC = ""
    assert "pas configuré" in html(client.get(URL, **DIR))


@override_settings(**IIS)
def test_fiche_historique_et_fichier(client, jeu):
    page = html(client.get(URL + "QUITUS-FISCAL/", **DIR))
    assert "Quitus DGI aout.pdf" in page and "QF-0815" in page and "en cours" in page
    assert "remplacée" in page and "Noter une demande" in page and "Retirer" in page
    assert "Centre des impôts (DGI)" in page
    r = client.get(URL + f"version/{jeu['en_cours']}/fichier", **VUE)
    assert r.status_code == 200 and r["Content-Type"] == "application/pdf"
    assert b"".join(r.streaming_content).startswith(b"%PDF")
    assert client.get(URL + "version/999999/fichier", **DIR).status_code == 404
    assert client.get(URL + "INCONNU/", **DIR).status_code == 404
    assert "Retirer" not in html(client.get(URL + "QUITUS-FISCAL/", **VUE))


@override_settings(**IIS)
def test_fichier_absent_ou_partage_non_configure(client, jeu, partage, settings):
    v = PieceAdministrative.objects.get(pk=jeu["en_cours"])
    (partage / v.chemin.replace("\\", "/")).unlink()
    (partage / "ADMINISTRATIF/PIECES/QUITUS-FISCAL/Copie de Quitus DGI aout.pdf").unlink()
    assert client.get(URL + f"version/{v.pk}/fichier", **DIR).status_code == 404
    settings.PARTAGE_GIC = ""
    assert client.get(URL + f"version/{v.pk}/fichier", **DIR).status_code == 404
    assert "pas configuré" in html(client.get(URL + "QUITUS-FISCAL/", **DIR))


@override_settings(**IIS)
def test_fiche_signale_un_fichier_retrouve(client, jeu, partage):
    dossier = partage / "ADMINISTRATIF/PIECES/MOYENS"
    (dossier / "_perimees").mkdir()
    (dossier / "Moyens 2025.pdf").rename(dossier / "_perimees" / "Moyens 2025.pdf")
    assert "a été retrouvé" in html(client.get(URL + "MOYENS/", **DIR))


@override_settings(**IIS)
def test_noter_une_demande_et_retirer(client, jeu):
    r = client.post(
        URL + "MOYENS/demande",
        {"demandee_le": "2026-10-22", "relance_prevue_le": "2026-10-29", "note": "à signer"},
        follow=True,
        **DIR,
    )
    assert "Demande du 22/10/2026 notée" in html(r)
    assert DemandeRenouvellement.objects.filter(type__code="MOYENS").exists()
    r = client.post(
        URL + "MOYENS/demande",
        {"demandee_le": "2026-10-22", "relance_prevue_le": "2026-10-01"},
        follow=True,
        **DIR,
    )
    assert "la relance précède la demande" in html(r)
    assert client.post(URL + "MOYENS/demande", {}, **VUE).status_code == 403

    v = PieceAdministrative.objects.get(pk=jeu["en_cours"])
    r = client.post(URL + f"version/{v.pk}/retirer", {"motif": ""}, follow=True, **DIR)
    assert "indiquez pourquoi" in html(r)
    r = client.post(URL + f"version/{v.pk}/retirer", {"motif": "mauvais type"}, follow=True, **DIR)
    assert "retirée" in html(r) and "mauvais type" in html(r)
    assert client.post(URL + f"version/{v.pk}/retirer", {"motif": "x"}, **VUE).status_code == 403


@override_settings(**IIS)
def test_depot_proposer_puis_enregistrer(client, jeu):
    page = html(client.get(URL + "deposer", **DIR))
    assert "Type de pièce" in page and "Le fichier" not in page
    page = html(client.get(URL + "deposer?type=QUITUS-FISCAL", **DIR))
    assert page.count('data-statut="deja_enregistre"') == 1 and 'data-statut="doublon"' in page
    assert page.count('data-statut="enregistre"') == 1 and "Cette copie peut être retirée" in page
    assert "passera dans l'historique" in page and "Nouveau scan de la version en cours" in page
    nouveau = page.split('data-statut="nouveau"')[1].split('value="')[1].split('"')[0]
    base = {"type": "QUITUS-FISCAL", "empreinte": nouveau, "numero": "QF-1"}
    # sans date d'émission
    assert "date d'émission" in html(client.post(URL + "deposer", base, **DIR))
    # proposition : date du document, 3 mois en pratique
    page = html(
        client.post(
            URL + "deposer", {**base, "date_emission": "2026-10-20", "action": "proposer"}, **DIR
        )
    )
    assert 'value="2027-01-20"' in page and "Échéance proposée" in page
    r = client.post(
        URL + "deposer",
        {
            **base,
            "date_emission": "2026-10-20",
            "valide_jusqu_au": "2027-01-20",
            "action": "enregistrer",
        },
        follow=True,
        **DIR,
    )
    page = html(r)
    assert "Version du 20/10/2026 enregistrée, valide jusqu'au 20/01/2027" in page
    assert r.redirect_chain[-1][0] == URL + "QUITUS-FISCAL/"
    assert PieceAdministrative.objects.filter(numero="QF-1").exists()
    assert JournalAcces.objects.filter(action="piece:deposer").exists()


@override_settings(**IIS)
def test_depot_refus_et_cas_particuliers(client, jeu, partage, settings):
    # fichier inconnu ou doublon : refusé
    r = client.post(
        URL + "deposer",
        {"type": "QUITUS-FISCAL", "empreinte": "0" * 64, "date_emission": "2026-10-20"},
        **DIR,
    )
    assert "Choisissez un fichier nouveau" in html(r)
    # date du document sans durée (INPS) : la fin doit être saisie
    dossier = partage / "ADMINISTRATIF/PIECES/INPS"
    (dossier / "INPS octobre.pdf").write_bytes(demo.pdf("INPS octobre"))
    page = html(client.get(URL + "deposer?type=INPS", **DIR))
    emp = page.split('data-statut="nouveau"')[1].split('value="')[1].split('"')[0]
    page = html(
        client.post(
            URL + "deposer",
            {"type": "INPS", "empreinte": emp, "date_emission": "2026-10-20"},
            **DIR,
        )
    )
    assert "Saisissez la date de fin" in page
    r = client.post(
        URL + "deposer",
        {
            "type": "INPS",
            "empreinte": emp,
            "date_emission": "2026-10-20",
            "valide_jusqu_au": "2026-10-01",
            "action": "enregistrer",
        },
        **DIR,
    )
    assert "précède" in html(r)
    # pièce permanente : pas d'échéance
    nif = partage / "ADMINISTRATIF/PIECES/NIF"
    (nif / "NIF recto verso.pdf").write_bytes(demo.pdf("NIF propre", pages=2))
    page = html(client.get(URL + "deposer?type=NIF", **DIR))
    emp = page.split('data-statut="nouveau"')[1].split('value="')[1].split('"')[0]
    page = html(
        client.post(
            URL + "deposer",
            {"type": "NIF", "empreinte": emp, "date_emission": "2016-03-15", "action": "proposer"},
            **DIR,
        )
    )
    assert "Pièce permanente" in page
    r = client.post(
        URL + "deposer",
        {"type": "NIF", "empreinte": emp, "date_emission": "2016-03-15", "action": "enregistrer"},
        follow=True,
        **DIR,
    )
    assert "Version du 15/03/2016 enregistrée." in html(r)
    # dossier absent, partage non configuré, droits
    (partage / "ADMINISTRATIF/PIECES/PATENTE").rmdir()
    assert "introuvable" in html(client.get(URL + "deposer?type=PATENTE", **DIR))
    settings.PARTAGE_GIC = ""
    assert "pas configuré" in html(client.get(URL + "deposer?type=NIF", **DIR))
    assert client.get(URL + "deposer", **VUE).status_code == 403


@override_settings(**IIS)
def test_depot_nouveau_scan(client, jeu):
    page = html(client.get(URL + "deposer?type=QUITUS-FISCAL", **DIR))
    nouveau = page.split('data-statut="nouveau"')[1].split('value="')[1].split('"')[0]
    r = client.post(
        URL + "deposer",
        {
            "type": "QUITUS-FISCAL",
            "empreinte": nouveau,
            "nouveau_scan": "1",
            "action": "enregistrer",
        },
        follow=True,
        **DIR,
    )
    page = html(r)
    assert "Nouveau scan enregistré pour la version du" in page
    assert "remplacée par un nouveau scan" in page
    assert JournalAcces.objects.filter(action="piece:nouveau_scan").exists()


@override_settings(**IIS)
def test_depot_nouveau_scan_sans_version(client, jeu, partage):
    (partage / "ADMINISTRATIF/PIECES/TVA/TVA.pdf").write_bytes(demo.pdf("TVA"))
    page = html(client.get(URL + "deposer?type=TVA", **DIR))
    assert "Nouveau scan de la version en cours" not in page
    emp = page.split('data-statut="nouveau"')[1].split('value="')[1].split('"')[0]
    r = client.post(
        URL + "deposer",
        {"type": "TVA", "empreinte": emp, "nouveau_scan": "1", "action": "enregistrer"},
        **DIR,
    )
    assert "aucune version en cours" in html(r)


@override_settings(**IIS)
def test_types_lister_modifier_ajouter(client, jeu):
    page = html(client.get(URL + "types/", **DIR))
    assert "QUITUS-FISCAL" in page and "3 mois après l'émission" in page and "Modifier" in page
    assert "Modifier" not in html(client.get(URL + "types/", **VUE))
    page = html(client.get(URL + "types/NON-FAILLITE/modifier", **DIR))
    assert "La direction" in page and "disabled" in page  # code figé
    donnees = {
        "libelle": "Certificat de non-faillite",
        "organisme": "Greffe",
        "regle_validite": "apres_emission",
        "duree_mois": "6",
        "rappel_jours": "20",
        "dossier": r"ADMINISTRATIF\PIECES\NON-FAILLITE",
        "ordre": "50",
        "actif": "on",
    }
    r = client.post(URL + "types/NON-FAILLITE/modifier", donnees, follow=True, **DIR)
    assert "enregistré" in html(r)
    t = TypePiece.objects.get(code="NON-FAILLITE")
    assert t.duree_mois == 6 and t.rappel_jours == 20 and not t.exigee_par_defaut
    # ajout : code contrôlé, durée exigée par la règle, dossier par défaut
    nouveau = {**donnees, "code": "attestation bancaire", "libelle": "Attestation bancaire"}
    assert "Majuscules" in html(client.post(URL + "types/ajouter", nouveau, **DIR))
    nouveau.update(code="BANQUE", duree_mois="", dossier="")
    assert "demande une durée" in html(client.post(URL + "types/ajouter", nouveau, **DIR))
    nouveau["duree_mois"] = "3"
    client.post(URL + "types/ajouter", nouveau, **DIR)
    assert TypePiece.objects.get(code="BANQUE").dossier == r"ADMINISTRATIF\PIECES\BANQUE"
    assert client.get(URL + "types/ajouter", **VUE).status_code == 403
    assert "Ajouter un type de pièce" in html(client.get(URL + "types/ajouter", **DIR))


@override_settings(**IIS)
def test_pastille_et_accueil(client, jeu):
    page = html(client.get(URL, **DIR))
    assert "Pièces administratives" in page and "Types de pièces" in page
    accueil = html(client.get("/admin/", **DIR))
    assert "Pièces administratives à traiter" in accueil
    from django.test import RequestFactory

    from administratif.vues.registre import pastille
    from identite.models import Utilisateur

    req = RequestFactory().get("/")
    req.user = Utilisateur.objects.get(login_windows="giconseils\\directrice")
    assert pastille(req) == 2
    req.user = None
    assert pastille(req) is None


def test_commande_echeances(jeu):
    sortie = StringIO()
    with pytest.raises(SystemExit) as fin:
        call_command("administratif_echeances", stdout=sortie)
    assert fin.value.code == 1
    texte = sortie.getvalue()
    assert "EXPIRÉE" in texte and "MOYENS" in texte and "À RENOUVELER" in texte
    assert "1 expirée(s), 1 à renouveler, 0 manquante(s)" in texte
    sortie = StringIO()
    call_command("administratif_echeances", "--date", "2026-09-01", stdout=sortie)  # rien d'expiré
    assert "0 expirée(s)" in sortie.getvalue()
    with pytest.raises(CommandError):
        call_command("administratif_echeances", "--date", "hier")


def test_commande_sans_alerte(db, partage):
    sortie = StringIO()
    call_command("administratif_echeances", stdout=sortie)  # aucune version : manquantes, code 0
    assert "MANQUANTE" in sortie.getvalue()


def test_commande_jeu_demo(db, tmp_path):
    sortie = StringIO()
    call_command("administratif_jeu_demo", "--partage", str(tmp_path), stdout=sortie)
    assert "10 versions fictives" in sortie.getvalue()
    with pytest.raises(CommandError, match="déjà des versions"):
        call_command("administratif_jeu_demo", "--partage", str(tmp_path))
    PieceAdministrative.objects.all().delete()
    DemandeRenouvellement.objects.all().delete()
    with pytest.raises(CommandError, match="local"):
        call_command("administratif_jeu_demo", "--partage", r"\\AD-SERVEUR\GIC")
