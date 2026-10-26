"""Chantier 8 — premier remplissage du registre : `administratif_importer`."""

from __future__ import annotations

from datetime import date
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from administratif import services
from administratif.demo import pdf
from administratif.models import PieceAdministrative

pytestmark = pytest.mark.django_db

REGISTRE = "\n".join(
    [
        "type;fichier;emise_le;valide_jusqu_au;numero;rescan",
        "NIF;NIF 2010.pdf;13/12/2010;;025004950G;",
        "INPS;INPS scan.pdf;02/10/2026;14/11/2026;2026-02398;",
        "INPS;INPS certifiee.pdf;;;;oui",
        "NON-FAILLITE;Non-faillite.pdf;2026-07-21;;;",
        "PRESENTATION;Presentation.pdf;01/08/2026;;;",
        "TVA;absente.pdf;04/09/2026;15/10/2026;;",
        "INCONNU;x.pdf;01/01/2026;;;",
    ]
)


@pytest.fixture
def poses(partage):
    """Les fichiers posés dans les dossiers des types, comme sur le partage."""
    for dossier, nom in (
        ("PIECES/NIF", "NIF 2010.pdf"),
        ("PIECES/INPS", "INPS scan.pdf"),
        ("PIECES/INPS", "INPS certifiee.pdf"),
        ("PIECES/NON-FAILLITE", "Non-faillite.pdf"),
        ("PRESENTATION", "Presentation.pdf"),
        ("PIECES/TVA", None),
    ):
        d = partage / "ADMINISTRATIF" / dossier
        d.mkdir(parents=True, exist_ok=True)
        if nom:
            (d / nom).write_bytes(pdf(nom))
    return partage


def test_importer_le_registre(poses):
    lignes = services.lire_csv(REGISTRE)
    r = services.importer(lignes, simuler=True)
    assert len(r.enregistrees) == 5 and not PieceAdministrative.objects.exists()
    assert r.erreurs == [
        "ligne 7 (TVA : absente.pdf) : fichier absent de ADMINISTRATIF\\PIECES\\TVA",
        "ligne 8 (INCONNU : x.pdf) : type de pièce inconnu",
    ]
    r = services.importer(lignes)
    assert len(r.enregistrees) == 5 and PieceAdministrative.objects.count() == 5
    nif = PieceAdministrative.objects.get(type__code="NIF")
    assert (nif.date_emission, nif.valide_jusqu_au, nif.numero) == (
        date(2010, 12, 13),
        None,
        "025004950G",
    )
    # le scan certifié remplace le premier scan, dates et numéro repris
    inps = list(PieceAdministrative.objects.filter(type__code="INPS"))
    courante = services.version_en_cours(inps)
    assert courante.nom_fichier == "INPS certifiee.pdf" and courante.numero == "2026-02398"
    assert courante.valide_jusqu_au == date(2026, 11, 14)
    assert [v.nom_fichier for v in inps if v.retiree] == ["INPS scan.pdf"]
    # fin de validité vide : la règle du type
    faillite = PieceAdministrative.objects.get(type__code="NON-FAILLITE")
    assert faillite.valide_jusqu_au == date(2026, 10, 21)
    presentation = PieceAdministrative.objects.get(type__code="PRESENTATION")
    assert presentation.valide_jusqu_au == date(2027, 8, 1)
    # relancé : rien de neuf
    r = services.importer(lignes)
    assert not r.enregistrees and len(r.deja) == 5


def test_lire_le_registre_refus():
    assert services.lire_date_texte(" 23/09/2026 ") == date(2026, 9, 23)
    assert services.lire_date_texte("") is None
    with pytest.raises(ValueError, match="illisible"):
        services.lire_date_texte("septembre")
    with pytest.raises(ValueError, match="colonnes manquantes : emise_le, fichier"):
        services.lire_csv("type;numero\nNIF;1\n")
    with pytest.raises(ValueError, match="vide"):
        services.lire_csv("")


def test_commande_importer(poses, tmp_path):
    f = tmp_path / "registre.csv"
    f.write_text(REGISTRE, encoding="utf-8-sig")
    sortie = StringIO()
    with pytest.raises(SystemExit):
        call_command("administratif_importer", str(f), "--simuler", stdout=sortie)
    texte = sortie.getvalue()
    assert "Simulation, rien n'est gardé : 7 ligne(s) lue(s) ; 5 pièce(s) enregistrée(s)" in texte
    assert "ERREUR ligne 8 (INCONNU : x.pdf) : type de pièce inconnu" in texte
    assert not PieceAdministrative.objects.exists()
    with pytest.raises(CommandError, match="introuvable"):
        call_command("administratif_importer", str(tmp_path / "absent.csv"))
    (tmp_path / "vide.csv").write_text("type;numero\n", encoding="utf-8")
    with pytest.raises(CommandError, match="colonnes manquantes"):
        call_command("administratif_importer", str(tmp_path / "vide.csv"))
