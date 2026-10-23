"""Données fictives pour une base d'essai et les parcours dans le navigateur.

Écrit de petits PDF dans un dossier LOCAL qui joue le rôle du partage (jamais dans le vrai
partage : `remplir` refuse un chemin réseau) et enregistre des versions dont les dates sont
calculées à partir d'aujourd'hui, pour que chaque état existe quel que soit le jour :

- quitus fiscal à renouveler (expire dans 15 jours), demande en cours, une ancienne version
  rangée dans `_perimees`, et trois fichiers posés pour le dépôt : un nouveau, son doublon, et
  une copie de la version déjà enregistrée ;
- liste des moyens expirée ; INPS, non-faillite, OICM valides ; NIF, statuts, RCCM, agrément
  permanents ; les pièces non exigées par défaut restent sans version.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from administratif.models import DemandeRenouvellement, PieceAdministrative, TypePiece
from administratif.services import empreinte


def pdf(texte: str, pages: int = 1) -> bytes:
    """Un PDF valide, minimal, de `pages` pages portant `texte`."""
    objets: list[bytes] = []
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(pages))
    objets.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objets.append(f"<< /Type /Pages /Kids [{kids}] /Count {pages} >>".encode())
    for i in range(pages):
        contenu = f"BT /F1 18 Tf 72 720 Td ({texte} - page {i + 1}) Tj ET".encode(
            "latin-1", "replace"
        )
        objets.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                f"/Contents {4 + 2 * i} 0 R /Resources << /Font << /F1 << /Type /Font "
                f"/Subtype /Type1 /BaseFont /Helvetica >> >> >> >>"
            ).encode()
        )
        objets.append(b"<< /Length %d >>\nstream\n" % len(contenu) + contenu + b"\nendstream")
    sortie = bytearray(b"%PDF-1.4\n")
    positions = []
    for n, corps in enumerate(objets, start=1):
        positions.append(len(sortie))
        sortie += f"{n} 0 obj\n".encode() + corps + b"\nendobj\n"
    xref = len(sortie)
    sortie += f"xref\n0 {len(objets) + 1}\n0000000000 65535 f \n".encode()
    for p in positions:
        sortie += f"{p:010d} 00000 n \n".encode()
    sortie += (
        f"trailer\n<< /Size {len(objets) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(sortie)


def _poser(racine: Path, type_piece: TypePiece, nom: str, contenu: bytes) -> Path:
    dossier = racine.joinpath(*[m for m in type_piece.dossier.replace("/", "\\").split("\\") if m])
    chemin = dossier.joinpath(*[m for m in nom.replace("/", "\\").split("\\") if m])
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_bytes(contenu)
    return chemin


def _version(racine, t, nom, contenu, emise, fin, utilisateur=None, numero=""):
    chemin = _poser(racine, t, nom, contenu)
    return PieceAdministrative.objects.create(
        type=t,
        chemin="\\".join(chemin.relative_to(racine).parts),
        empreinte=empreinte(chemin),
        taille=chemin.stat().st_size,
        nb_pages=1,
        numero=numero,
        date_emission=emise,
        valide_jusqu_au=fin,
        deposee_par=utilisateur,
    )


def remplir(racine: Path, aujourd_hui: date | None = None, utilisateur=None) -> dict[str, int]:
    """Crée les dossiers de tous les types sous `racine`, y écrit les PDF fictifs et enregistre
    les versions. Rend le nombre de fichiers écrits et de versions créées."""
    if str(racine).startswith(("\\\\", "//")):
        raise ValueError("données fictives : un dossier local, jamais le partage du serveur")
    j = aujourd_hui or date.today()
    types = {t.code: t for t in TypePiece.objects.all()}
    for t in types.values():
        _poser(racine, t, ".garder", b"")  # le dossier existe, même vide
        (racine.joinpath(*t.dossier.split("\\")) / ".garder").unlink()

    q = types["QUITUS-FISCAL"]
    ancien = _version(
        racine,
        q,
        r"_perimees\Quitus mai.pdf",
        pdf("Quitus fiscal mai"),
        j - timedelta(days=170),
        j - timedelta(days=78),
        utilisateur,
    )
    courant = _version(
        racine,
        q,
        "Quitus DGI aout.pdf",
        pdf("Quitus fiscal aout"),
        j - timedelta(days=77),
        j + timedelta(days=15),
        utilisateur,
        "QF-0815",
    )
    nouveau = pdf("Quitus fiscal octobre")
    _poser(racine, q, "Quitus DGI octobre.pdf", nouveau)
    _poser(racine, q, "scan0042.pdf", nouveau)  # doublon du nouveau
    _poser(racine, q, "Copie de Quitus DGI aout.pdf", pdf("Quitus fiscal aout"))  # déjà là
    DemandeRenouvellement.objects.create(
        type=q,
        demandee_le=j - timedelta(days=3),
        aupres_de="Centre des impôts (DGI)",
        relance_prevue_le=j + timedelta(days=7),
        par=utilisateur,
    )

    _version(
        racine,
        types["MOYENS"],
        "Moyens 2025.pdf",
        pdf("Liste des moyens"),
        j - timedelta(days=400),
        j - timedelta(days=35),
        utilisateur,
    )
    _version(
        racine,
        types["INPS"],
        "INPS septembre.pdf",
        pdf("Attestation INPS"),
        j - timedelta(days=40),
        j + timedelta(days=52),
        utilisateur,
    )
    _version(
        racine,
        types["NON-FAILLITE"],
        "Non faillite.pdf",
        pdf("Non-faillite"),
        j - timedelta(days=5),
        j + timedelta(days=87),
        utilisateur,
    )
    _version(
        racine,
        types["OICM"],
        "OICM.pdf",
        pdf("Attestation OICM"),
        j - timedelta(days=200),
        j + timedelta(days=165),
        utilisateur,
    )
    for code, nom in (
        ("NIF", "Carte NIF.pdf"),
        ("STATUTS", "Statuts.pdf"),
        ("RCCM", "RCCM constitution.pdf"),
        ("AGREMENT", "API-Mali.pdf"),
    ):
        _version(racine, types[code], nom, pdf(nom), date(2016, 3, 15), None, utilisateur)
    return {
        "versions": PieceAdministrative.objects.count(),
        "remplacee": ancien.pk,
        "en_cours": courant.pk,
    }
