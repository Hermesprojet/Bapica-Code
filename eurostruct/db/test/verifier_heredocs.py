#!/usr/bin/env python3
"""Cherche, dans les harnais, les heredocs NON QUOTES contenant une
substitution shell.

POURQUOI CE FICHIER EXISTE
---------------------------
Un heredoc ouvert par ``<<SQL`` — et non ``<<'SQL'`` — subit l'expansion du
shell. Ce qui ressemble a de la prose SQL est alors du shell. Mesure du 28/08 :

    montrer <<SQL
    -- voir `whoami` pour le detail
    SQL

fait parvenir a ``psql`` la ligne ``-- voir root pour le detail``. La
substitution s'execute, et sa sortie entre dans le flux SQL.

Quatre harnais d'autorite contenaient cette forme. L'effet y etait benin — un
commentaire mutile, parce que le mot entre accents graves n'etait pas une
commande — mais le mecanisme etait vivant.

CE QU'IL NE FAIT PAS
---------------------
Il n'interdit pas les heredocs non quotes : la plupart doivent interpoler
``$MIG``, ``$BASE``, ``$CTL``. Il interdit qu'un heredoc non quote contienne
une SUBSTITUTION — accents graves ou ``$(``.

Rend 0 si rien n'est trouve, 1 sinon, et imprime un emplacement par ligne.
"""
from __future__ import annotations

import pathlib
import re
import sys

OUVERTURE = re.compile(r"<<(-?)([A-Za-z_]\w*)\s*$")


def heredocs_a_risque(chemin: pathlib.Path) -> list[tuple[int, str]]:
    """Rend (ligne, delimiteur) pour chaque heredoc non quote a substitution."""
    lignes = chemin.read_text(encoding="utf-8", errors="replace").split("\n")
    trouves: list[tuple[int, str]] = []
    i = 0
    while i < len(lignes):
        m = OUVERTURE.search(lignes[i])
        if not m:
            i += 1
            continue
        delim = m.group(2)
        j = i + 1
        corps: list[str] = []
        while j < len(lignes) and lignes[j].strip() != delim:
            corps.append(lignes[j])
            j += 1
        texte = "\n".join(corps)
        # UNE SUBSTITUTION ECHAPPEE N'EST PAS UN DANGER, C'EST LA FORME
        # CORRECTE. `deploy_recovery.sh` ecrit un FAUX psql par heredoc non
        # quote: son corps doit contenir des `\$(...)` qui s'evaluent quand le
        # faux psql tourne, pas quand on l'ecrit. Les compter comme un risque
        # aurait fait rougir la bonne pratique et pousse a la contourner.
        if re.search(r"(?<!\\)`", texte) or re.search(r"(?<!\\)\$\(", texte):
            trouves.append((i + 1, delim))
        i = j + 1
    return trouves


def main(argv: list[str]) -> int:
    racine = pathlib.Path(argv[1] if len(argv) > 1 else ".")
    fichiers = sorted(racine.glob("*.sh"))
    if not fichiers:
        print(f"REFUS: aucun fichier .sh sous {racine}", file=sys.stderr)
        return 2
    total = 0
    for f in fichiers:
        for ligne, delim in heredocs_a_risque(f):
            print(f"{f.name}:{ligne} (<<{delim})")
            total += 1
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
