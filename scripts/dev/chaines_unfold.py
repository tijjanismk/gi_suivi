"""Liste les textes traduisibles d'Unfold (qui n'a pas de traduction française).

    .venv\\Scripts\\python.exe scripts\\dev\\chaines_unfold.py > chaines.txt

Sert à tenir à jour locale/fr/LC_MESSAGES/django.po quand on change de version d'Unfold.
"""

import pathlib
import re

import unfold

MOTIFS = [
    re.compile(r"{%\s*(?:trans|translate)\s+\"([^\"]+)\""),
    re.compile(r"{%\s*(?:trans|translate)\s+'([^']+)'"),
    re.compile(r"\b(?:_|gettext|gettext_lazy)\(\s*\"([^\"]+)\""),
    re.compile(r"\b(?:_|gettext|gettext_lazy)\(\s*'([^']+)'"),
]


def chaines() -> dict[str, str]:
    racine = pathlib.Path(unfold.__file__).parent
    trouvees: dict[str, str] = {}
    for f in sorted(racine.rglob("*")):
        if f.suffix not in (".html", ".py"):
            continue
        texte = f.read_text(encoding="utf-8", errors="ignore")
        for motif in MOTIFS:
            for s in motif.findall(texte):
                trouvees.setdefault(s, f.relative_to(racine).as_posix())
    return trouvees


if __name__ == "__main__":
    for s, origine in sorted(chaines().items()):
        print(f"{origine}\t{s}")
