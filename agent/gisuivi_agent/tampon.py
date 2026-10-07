"""Tampon local des segments (SQLite). Survit aux coupures réseau et aux redémarrages."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

from moteur.suivi.types import Etat, Segment

_SCHEMA = """
CREATE TABLE IF NOT EXISTS segments (
    id INTEGER PRIMARY KEY,
    debut TEXT NOT NULL, fin TEXT NOT NULL, duree_s REAL NOT NULL,
    etat TEXT NOT NULL, application TEXT NOT NULL, fichier TEXT, chemin TEXT,
    lot_id TEXT, envoye INTEGER NOT NULL DEFAULT 0, cree_le TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_segments_envoye ON segments(envoye, lot_id);
CREATE INDEX IF NOT EXISTS ix_segments_debut ON segments(debut);
CREATE TABLE IF NOT EXISTS etat (cle TEXT PRIMARY KEY, valeur TEXT);
"""


class Tampon:
    def __init__(self, chemin: Path) -> None:
        chemin.parent.mkdir(parents=True, exist_ok=True)
        self.cx = sqlite3.connect(str(chemin), check_same_thread=False, isolation_level=None)
        self.cx.execute("PRAGMA journal_mode=WAL")
        self.cx.executescript(_SCHEMA)

    # -- écriture ---------------------------------------------------------------
    def ajouter(self, segments: list[Segment]) -> None:
        if not segments:
            return
        self.cx.executemany(
            "INSERT INTO segments(debut, fin, duree_s, etat, application, fichier, chemin, cree_le)"
            " VALUES (?,?,?,?,?,?,?,?)",
            [
                (
                    s.debut.isoformat(),
                    s.fin.isoformat(),
                    round(s.duree_s, 1),
                    s.etat.value,
                    s.application,
                    s.fichier,
                    s.chemin,
                    datetime.now().isoformat(),
                )
                for s in segments
            ],
        )

    # -- lots ---------------------------------------------------------------------
    def preparer_lot(self, max_segments: int = 500) -> tuple[str, list[dict]] | None:
        """Reprend un lot déjà formé mais non acquitté, sinon en forme un nouveau."""
        ligne = self.cx.execute(
            "SELECT lot_id FROM segments WHERE envoye = 0 AND lot_id IS NOT NULL LIMIT 1"
        ).fetchone()
        if ligne:
            lot_id = ligne[0]
        else:
            ids = [
                r[0]
                for r in self.cx.execute(
                    "SELECT id FROM segments WHERE envoye = 0 AND lot_id IS NULL"
                    " ORDER BY id LIMIT ?",
                    (max_segments,),
                )
            ]
            if not ids:
                return None
            lot_id = str(uuid.uuid4())
            self.cx.executemany(
                "UPDATE segments SET lot_id = ? WHERE id = ?", [(lot_id, i) for i in ids]
            )
        lignes = self.cx.execute(
            "SELECT debut, fin, duree_s, etat, application, fichier, chemin FROM segments"
            " WHERE lot_id = ? ORDER BY debut",
            (lot_id,),
        ).fetchall()
        cles = ("debut", "fin", "duree_s", "etat", "application", "fichier", "chemin")
        return lot_id, [dict(zip(cles, ligne, strict=True)) for ligne in lignes]

    def acquitter(self, lot_id: str) -> None:
        self.cx.execute("UPDATE segments SET envoye = 1 WHERE lot_id = ?", (lot_id,))

    def en_attente(self) -> int:
        return self.cx.execute("SELECT COUNT(*) FROM segments WHERE envoye = 0").fetchone()[0]

    def purger(self, jours: int = 7) -> int:
        limite = (datetime.now() - timedelta(days=jours)).isoformat()
        return self.cx.execute(
            "DELETE FROM segments WHERE envoye = 1 AND fin < ?", (limite,)
        ).rowcount

    # -- résumé local (icône « mon activité du jour ») -----------------------------
    def resume_du_jour(self, jour: date | None = None, racines=None, lecteurs=None) -> dict:
        jour = jour or date.today()
        lignes = self.cx.execute(
            "SELECT application, fichier, chemin, duree_s FROM segments"
            " WHERE etat = ? AND debut >= ? AND debut < ?",
            (Etat.ACTIF.value, jour.isoformat(), (jour + timedelta(days=1)).isoformat()),
        ).fetchall()
        total = sum(ligne[3] for ligne in lignes)
        par_dossier: dict[str, float] = {}
        if racines:
            from moteur.suivi.classement import classer_chemin

            for app, fichier, chemin, duree in lignes:
                c = classer_chemin(chemin, racines, lecteurs) if chemin else None
                # Fichier connu mais non rattaché : chemin hors racine, ou nom seul
                # (PDF dans un navigateur)
                cle = (
                    (c.code or c.dossier_nom)
                    if c and c.statut == "dossier"
                    else ("à classer" if chemin or fichier else app)
                )
                par_dossier[cle] = par_dossier.get(cle, 0.0) + duree
        par_app: dict[str, float] = {}
        for app, _f, _c, duree in lignes:
            par_app[app] = par_app.get(app, 0.0) + duree
        return {
            "total_s": total,
            "par_dossier": dict(sorted(par_dossier.items(), key=lambda x: -x[1])),
            "par_application": dict(sorted(par_app.items(), key=lambda x: -x[1])),
        }

    # -- état divers -------------------------------------------------------------------
    def lire_etat(self, cle: str) -> str | None:
        ligne = self.cx.execute("SELECT valeur FROM etat WHERE cle = ?", (cle,)).fetchone()
        return ligne[0] if ligne else None

    def ecrire_etat(self, cle: str, valeur: str) -> None:
        self.cx.execute(
            "INSERT INTO etat(cle, valeur) VALUES (?, ?)"
            " ON CONFLICT(cle) DO UPDATE SET valeur = excluded.valeur",
            (cle, valeur),
        )
