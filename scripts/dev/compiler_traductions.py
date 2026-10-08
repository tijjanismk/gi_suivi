"""Compile les catalogues .po en .mo, sans dépendre de GNU gettext (absent sous Windows).

    .venv\\Scripts\\python.exe scripts\\dev\\compiler_traductions.py

Format .mo : https://www.gnu.org/software/gettext/manual/html_node/MO-Files.html
Analyse .po minimale mais suffisante pour nos catalogues (msgid/msgstr simples et multi-lignes).
"""

from __future__ import annotations

import pathlib
import re
import struct

RACINE = pathlib.Path(__file__).resolve().parents[2]


def analyser_po(texte: str) -> dict[str, str]:
    entrees: dict[str, str] = {}
    msgid: list[str] | None = None
    msgstr: list[str] | None = None
    cible: list[str] | None = None

    def vider() -> None:
        if msgid is not None and msgstr is not None:
            entrees["".join(msgid)] = "".join(msgstr)

    for brute in texte.splitlines():
        ligne = brute.strip()
        if not ligne or ligne.startswith("#"):
            continue
        if ligne.startswith("msgid "):
            vider()
            msgid, msgstr = [_chaine(ligne[6:])], None
            cible = msgid
        elif ligne.startswith("msgstr "):
            msgstr = [_chaine(ligne[7:])]
            cible = msgstr
        elif ligne.startswith('"') and cible is not None:
            cible.append(_chaine(ligne))
    vider()
    return entrees  # on garde l'en-tête (msgid "") : il porte le charset UTF-8


_ECHAPPES = {r"\n": "\n", r"\t": "\t", r"\r": "\r", r"\"": '"', r"\\": "\\"}


def _chaine(fragment: str) -> str:
    """Contenu d'une chaîne .po entre guillemets. Le texte est déjà de l'UTF-8 décodé ;
    on ne traite que les échappements antislash, sans toucher aux accents."""
    m = re.match(r'\s*"(.*)"\s*$', fragment, re.DOTALL)
    brut = m.group(1) if m else fragment
    return re.sub(r"\\[ntr\"\\]", lambda x: _ECHAPPES[x.group()], brut)


def ecrire_mo(entrees: dict[str, str], sortie: pathlib.Path) -> None:
    cles = sorted(entrees)
    ids = b"\x00".join(k.encode("utf-8") for k in cles)
    strs = b"\x00".join(entrees[k].encode("utf-8") for k in cles)
    n = len(cles)
    debut_table_id = 7 * 4
    debut_table_str = debut_table_id + n * 8
    debut_ids = debut_table_str + n * 8
    debut_strs = debut_ids + len(ids) + (1 if ids else 0)

    offsets_id, offsets_str = [], []
    pos = debut_ids
    for k in cles:
        longueur = len(k.encode("utf-8"))
        offsets_id.append((longueur, pos))
        pos += longueur + 1
    pos = debut_strs
    for k in cles:
        longueur = len(entrees[k].encode("utf-8"))
        offsets_str.append((longueur, pos))
        pos += longueur + 1

    sortie.parent.mkdir(parents=True, exist_ok=True)
    with sortie.open("wb") as f:
        f.write(struct.pack("Iiiiiii", 0x950412DE, 0, n, debut_table_id, debut_table_str, 0, 0))
        for longueur, decalage in offsets_id:
            f.write(struct.pack("ii", longueur, decalage))
        for longueur, decalage in offsets_str:
            f.write(struct.pack("ii", longueur, decalage))
        f.write(ids + (b"\x00" if ids else b""))
        f.write(strs + (b"\x00" if strs else b""))


def main() -> None:
    # Seulement nos catalogues ; ceux des bibliothèques (dans .venv) sont déjà compilés.
    for po in (RACINE / "locale").rglob("*.po"):
        entrees = analyser_po(po.read_text(encoding="utf-8"))
        mo = po.with_suffix(".mo")
        ecrire_mo(entrees, mo)
        print(f"{po.relative_to(RACINE)} -> {mo.name} ({len(entrees)} entrées)")


if __name__ == "__main__":
    main()
