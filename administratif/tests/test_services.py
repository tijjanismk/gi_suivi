"""AD02 et AD04 — types de départ, lecture du dossier d'une pièce, registre, dépôt, rescan."""

from __future__ import annotations

import shutil
from datetime import date

import pytest
from freezegun import freeze_time

from administratif import demo, services
from administratif.models import DemandeRenouvellement, PieceAdministrative, TypePiece
from administratif.tests.conftest import AUJOURDHUI

pytestmark = pytest.mark.django_db


def type_(code: str) -> TypePiece:
    return TypePiece.objects.get(code=code)


def fichier(code: str, nom: str) -> services.FichierDuDossier:
    return next(f for f in services.fichiers_du_dossier(type_(code)) if f.nom == nom)


def test_types_de_depart():
    types = list(TypePiece.objects.all())
    assert len(types) == 18  # 16 au départ, présentation et carte OICM le 26/10
    assert all(t.rappel_jours == 15 for t in types)
    assert all(
        t.dossier == f"ADMINISTRATIF\\PIECES\\{t.code}" for t in types if t.code != "PRESENTATION"
    )
    assert type_("PRESENTATION").dossier == "ADMINISTRATIF\\PRESENTATION"
    assert type_("PRESENTATION").regle_texte == "revue tous les 12 mois"
    assert type_("CARTE-PRO-OICM").regle_texte == "permanente"
    exigees = {t.code for t in types if t.exigee_par_defaut}
    assert exigees == {
        "QUITUS-FISCAL",
        "INPS",
        "RCCM",
        "OICM",
        "AGREMENT",
        "MOYENS",
        "NIF",
        "STATUTS",
    }
    q = type_("QUITUS-FISCAL")
    assert q.regle_texte == "date écrite sur le document (3 mois en pratique)"
    assert type_("NON-FAILLITE").regle_texte == "3 mois après l'émission"
    assert type_("MOYENS").regle_texte == "revue tous les 12 mois"
    assert type_("PATENTE").regle_texte == "jusqu'au 31/12 de l'année d'émission"
    assert type_("NIF").regle_texte == "permanente"
    assert type_("PATENTE").date_de_fin(date(2026, 3, 1)) == date(2026, 12, 31)
    assert str(q) == q.libelle


def test_partage_non_configure_et_chemins_refuses(settings, partage):
    assert services.chemin_absolu(r"ADMINISTRATIF\PIECES\NIF\a.pdf") == (
        partage / "ADMINISTRATIF" / "PIECES" / "NIF" / "a.pdf"
    )
    for mauvais in (r"..\secret.pdf", r"ADMINISTRATIF\..\..\x", r"C:\Windows\x"):
        with pytest.raises(ValueError):
            services.chemin_absolu(mauvais)
    settings.PARTAGE_GIC = ""
    with pytest.raises(services.PartageIndisponibleError):
        services.racine_partage()
    assert not services._existe(r"ADMINISTRATIF\x.pdf")


def test_dossier_absent(partage):
    with pytest.raises(services.PartageIndisponibleError, match="introuvable"):
        services.fichiers_du_dossier(type_("NIF"))


def test_fichiers_du_dossier_nouveau_doublon_deja_enregistre(jeu, partage):
    (partage / "ADMINISTRATIF" / "PIECES" / "QUITUS-FISCAL" / "~$brouillon.pdf").write_bytes(b"x")
    fichiers = {f.nom: f for f in services.fichiers_du_dossier(type_("QUITUS-FISCAL"))}
    # les sous-dossiers (_perimees) et les fichiers de travail (~$) ne sont pas proposés
    assert set(fichiers) == {
        "Quitus DGI aout.pdf",
        "Quitus DGI octobre.pdf",
        "scan0042.pdf",
        "Copie de Quitus DGI aout.pdf",
    }
    assert fichiers["Copie de Quitus DGI aout.pdf"].statut == "deja_enregistre"
    assert fichiers["Quitus DGI aout.pdf"].statut == "enregistre"  # le fichier de la version
    nouveaux = [f for f in fichiers.values() if f.statut == "nouveau"]
    doublons = [f for f in fichiers.values() if f.statut == "doublon"]
    assert len(nouveaux) == 1 and len(doublons) == 1
    assert doublons[0].meme_que == nouveaux[0].nom and not doublons[0].enregistrable
    assert nouveaux[0].nb_pages == 1 and nouveaux[0].taille > 0


def test_nb_pages(tmp_path):
    p = tmp_path / "trois.pdf"
    p.write_bytes(demo.pdf("essai", pages=3))
    assert services.nb_pages(p) == 3
    (tmp_path / "x.txt").write_text("x")
    assert services.nb_pages(tmp_path / "x.txt") is None
    assert services.nb_pages(tmp_path / "absent.pdf") is None
    (tmp_path / "vide.pdf").write_bytes(b"%PDF-1.4")
    assert services.nb_pages(tmp_path / "vide.pdf") is None


def test_registre_a_la_date(jeu):
    lignes = {x.type.code: x for x in services.registre(AUJOURDHUI)}
    assert lignes["QUITUS-FISCAL"].cle_etat == "a_renouveler"
    assert lignes["QUITUS-FISCAL"].libelle_etat == "expire dans 15 j"
    assert lignes["QUITUS-FISCAL"].demande is not None
    assert len(lignes["QUITUS-FISCAL"].versions) == 2
    assert lignes["MOYENS"].cle_etat == "expiree" and lignes["MOYENS"].alerte
    assert lignes["MOYENS"].libelle_etat == "expirée depuis 35 j"
    assert lignes["INPS"].libelle_etat == "valide · 52 j"
    assert lignes["NIF"].cle_etat == "permanente" and not lignes["NIF"].alerte
    assert lignes["TVA"].cle_etat == "non_requise" and not lignes["TVA"].alerte
    assert lignes["TVA"].libelle_etat == "non requise"
    n = services.compteurs(list(lignes.values()))
    assert n == {"valides": 7, "a_renouveler": 1, "expirees": 1, "manquantes": 0, "a_traiter": 2}


def test_libelles_d_etat():
    assert services.libelle_etat("a_renouveler", 0) == "expire aujourd'hui"
    assert services.libelle_etat("expiree", None) == "expirée"
    assert services.libelle_etat("valide", None) == "valide"
    assert services.libelle_etat("manquante", None) == "manquante"


@freeze_time("2026-10-22 10:00")
def test_enregistrer_une_nouvelle_version_clot_la_demande(jeu):
    q = type_("QUITUS-FISCAL")
    nouveau = next(f for f in services.fichiers_du_dossier(q) if f.enregistrable)
    v = services.enregistrer_version(
        q, nouveau, date(2026, 10, 20), date(2027, 1, 20), " QF-1", None
    )
    assert v.numero == "QF-1" and v.deposee_par is None and v.nb_pages == 1
    ligne = services.registre(AUJOURDHUI, types=[q])[0]
    assert ligne.version == v and ligne.cle_etat == "valide" and ligne.demande is None
    assert DemandeRenouvellement.objects.get().close_le == AUJOURDHUI
    # le doublon de ce fichier est maintenant « déjà enregistré »
    assert {f.statut for f in services.fichiers_du_dossier(q)} == {"enregistre", "deja_enregistre"}
    assert services.a_traiter() == 1  # il reste la liste des moyens


def test_enregistrer_refus(jeu, partage):
    q = type_("QUITUS-FISCAL")
    fichiers = services.fichiers_du_dossier(q)
    nouveau = next(f for f in fichiers if f.enregistrable)
    doublon = next(f for f in fichiers if f.statut == "doublon")
    with pytest.raises(ValueError, match="doublon"):
        services.enregistrer_version(q, doublon, date(2026, 10, 20), date(2027, 1, 20), "", None)
    with pytest.raises(ValueError, match="précède"):
        services.enregistrer_version(q, nouveau, date(2026, 10, 20), date(2026, 10, 1), "", None)
    with pytest.raises(ValueError, match="jusqu'à quand"):
        services.enregistrer_version(q, nouveau, date(2026, 10, 20), None, "", None)
    services.chemin_absolu(nouveau.chemin).write_bytes(demo.pdf("modifié entre-temps"))
    with pytest.raises(ValueError, match="changé ou disparu"):
        services.enregistrer_version(q, nouveau, date(2026, 10, 20), date(2027, 1, 20), "", None)
    # déjà en base (enregistré par un autre écran entre la lecture et l'envoi)
    autre = next(f for f in services.fichiers_du_dossier(q) if f.enregistrable)
    PieceAdministrative.objects.create(
        type=q, chemin="x", empreinte=autre.empreinte, date_emission=date(2026, 1, 1)
    )
    with pytest.raises(ValueError, match="déjà enregistré"):
        services.enregistrer_version(q, autre, date(2026, 10, 20), date(2027, 1, 20), "", None)


def test_piece_permanente_sans_echeance(partage, db):
    nif = type_("NIF")
    dossier = partage / "ADMINISTRATIF" / "PIECES" / "NIF"
    dossier.mkdir(parents=True)
    (dossier / "NIF.pdf").write_bytes(demo.pdf("NIF"))
    f = services.fichiers_du_dossier(nif)[0]
    v = services.enregistrer_version(nif, f, date(2016, 3, 15), None, "", None)
    assert v.valide_jusqu_au is None and str(v) == f"{nif.libelle} du 15/03/2016"


def test_nouveau_scan_reprend_les_dates_et_retire_l_ancien(jeu):
    q = type_("QUITUS-FISCAL")
    ancien = services.registre(AUJOURDHUI, types=[q])[0].version
    nouveau = next(f for f in services.fichiers_du_dossier(q) if f.enregistrable)
    v = services.enregistrer_nouveau_scan(q, nouveau, None)
    assert (v.date_emission, v.valide_jusqu_au, v.numero) == (
        ancien.date_emission,
        ancien.valide_jusqu_au,
        "QF-0815",
    )
    ancien.refresh_from_db()
    assert ancien.retiree and ancien.motif_retrait.startswith(services.MOTIF_NOUVEAU_SCAN)
    ligne = services.registre(AUJOURDHUI, types=[q])[0]
    assert ligne.version == v and ligne.demande is not None  # la demande reste ouverte
    # son doublon a maintenant le contenu d'une version enregistrée : plus rien à déposer
    restants = services.fichiers_du_dossier(q)
    assert {f.statut for f in restants} == {"enregistre", "deja_enregistre"}
    with pytest.raises(ValueError, match="deja_enregistre"):
        services.enregistrer_nouveau_scan(
            q, next(f for f in restants if f.statut == "deja_enregistre"), None
        )


def test_nouveau_scan_refus(jeu, partage):
    with pytest.raises(ValueError, match="aucune version en cours"):
        dossier = partage / "ADMINISTRATIF" / "PIECES" / "TVA"
        (dossier / "TVA.pdf").write_bytes(demo.pdf("TVA"))
        services.enregistrer_nouveau_scan(
            type_("TVA"), services.fichiers_du_dossier(type_("TVA"))[0], None
        )
    q = type_("QUITUS-FISCAL")
    nouveau = next(f for f in services.fichiers_du_dossier(q) if f.enregistrable)
    services.chemin_absolu(nouveau.chemin).unlink()
    with pytest.raises(ValueError, match="changé ou disparu"):
        services.enregistrer_nouveau_scan(q, nouveau, None)


def test_retirer_une_version(jeu):
    q = type_("QUITUS-FISCAL")
    courante = services.registre(AUJOURDHUI, types=[q])[0].version
    with pytest.raises(ValueError, match="pourquoi"):
        services.retirer_version(courante, "  ")
    services.retirer_version(courante, "mauvais type")
    ligne = services.registre(AUJOURDHUI, types=[q])[0]
    assert ligne.version.pk == jeu["remplacee"] and ligne.cle_etat == "expiree"


def test_fichier_deplace_retrouve_par_son_empreinte(jeu, partage):
    q = type_("QUITUS-FISCAL")
    dossier = partage / "ADMINISTRATIF" / "PIECES" / "QUITUS-FISCAL"
    (dossier / "Copie de Quitus DGI aout.pdf").unlink()  # sinon la copie identique suffit
    shutil.move(dossier / "Quitus DGI aout.pdf", dossier / "_perimees" / "Quitus aout.pdf")
    (dossier / "_perimees" / "autre.pdf").write_bytes(demo.pdf("sans rapport"))
    assert services.retrouver_deplaces(q) == 1
    v = PieceAdministrative.objects.get(pk=jeu["en_cours"])
    assert v.chemin.endswith(r"_perimees\Quitus aout.pdf") and v.nom_fichier == "Quitus aout.pdf"
    assert services.retrouver_deplaces(q) == 0


def test_noter_une_demande(jeu):
    t = type_("MOYENS")
    with pytest.raises(ValueError, match="relance"):
        services.noter_demande(t, date(2026, 10, 22), "", date(2026, 10, 1), "", None)
    d = services.noter_demande(t, date(2026, 10, 22), "", None, "  à signer ", None)
    assert d.aupres_de == "Interne" and d.note == "à signer" and str(d).startswith(t.libelle)


def test_jeu_fictif_refuse_le_partage_reseau(db):
    with pytest.raises(ValueError, match="local"):
        demo.remplir(__import__("pathlib").Path(r"\\AD-SERVEUR\GIC"))
