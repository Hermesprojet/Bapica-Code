#!/usr/bin/env python3
"""Which national parameters are still missing, and where each one is found.

Four situations, and they call for four different actions. Lumping them into a
single "missing" count is what makes a blocker list useless: three of the four
are answered by a document, and the fourth never will be.

``A CONFIRMER``
    Read in the annex, page cited, value stored. What is missing is a named
    engineer opening that page and signing. No purchase, no search.

``A LIRE``
    The annex is IN HAND but nobody has opened it at this clause. The value
    carried is the EN recommendation, which the country may or may not have
    adopted. Found in a document already held — the page is simply not known.

``PAGE ILLISIBLE``
    The annex says it replaces a table, and that table's cells do not extract
    from the copy held. The value carried is the EN's, explicitly not the
    country's. What is missing is a legible copy of one page.

``CODE, PAS DOCUMENT``
    The annex fixes the parameter by an EXPRESSION. No scalar can hold it, so
    no document and no signature unblocks it. The calculation module has to
    learn to evaluate the formula.

Run from tools/ndp_import/ or engine/:
    python scripts/report_missing_parameters.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = next(p for p in HERE.parents if (p / "engine").is_dir())
DATA = ROOT / "engine/src/eurostruct_engine/ndp/data"

#: The document each country's EC2 parameters come from, and whether it is held.
HELD = {
    "be": ("NBN EN 1992-1-1 ANB (1e ed., aout 2010)", True),
    "fr": ("NF EN 1992-1-1/NA (mars 2007, P 18-711-1/NA)", True),
}


def classify(name: str, p: dict) -> tuple[str, str]:
    notes = p.get("notes") or ""
    if p.get("validation_status") == "not_representable":
        return "CODE, PAS DOCUMENT", "aucun document ne debloque: le modele doit apprendre l'expression"
    if "PAS CELLES" in notes:
        return "PAGE ILLISIBLE", "cellules du tableau national non extractibles de l'exemplaire detenu"
    if p.get("source_page"):
        return "A CONFIRMER", f"p. {p['source_page']} de l'annexe detenue"
    return "A LIRE", "clause jamais ouverte; l'annexe est pourtant en main"


def main() -> int:
    for cc in ("fr", "be"):
        data = json.loads((DATA / f"{cc}.json").read_text(encoding="utf-8"))
        annex = next(
            a for a in data["annexes"]
            if a["standard_family"] == "EN 1992" and a["part"] == "1-1"
        )
        doc, in_hand = HELD[cc]
        buckets: dict[str, list[tuple[str, str, str]]] = {}
        for name, p in sorted(annex["parameters"].items()):
            kind, where = classify(name, p)
            buckets.setdefault(kind, []).append(
                (name, p.get("clause", ""), where)
            )

        print("=" * 74)
        print(f"{cc.upper()} — {doc}")
        print(f"Document {'EN MAIN' if in_hand else 'ABSENT'} ; "
              f"{len(annex['parameters'])} parametres")
        print("=" * 74)
        for kind in ("A LIRE", "A CONFIRMER", "PAGE ILLISIBLE", "CODE, PAS DOCUMENT"):
            rows = buckets.get(kind, [])
            if not rows:
                continue
            print(f"\n[{kind}] {len(rows)}")
            for name, clause, where in rows:
                print(f"    {name:26s} {clause:34s} {where}")
        print()
    print("=" * 74)
    print("OU LES TROUVER")
    print("=" * 74)
    print("A LIRE et A CONFIRMER: dans l'annexe deja detenue. Rien a acheter.")
    print("  Ce qui manque est une lecture humaine, pas un document.")
    print()
    print("PAGE ILLISIBLE: un exemplaire lisible d'UNE page.")
    print("  BE  Tableau 7.1N-ANB, p. 17 de NBN EN 1992-1-1 ANB   -> NBN")
    print("  FR  Tableau 7.1NF,    p. 16 de NF EN 1992-1-1/NA     -> AFNOR")
    print("  Un tirage papier ou un autre rendu PDF suffit.")
    print()
    print("CODE, PAS DOCUMENT: rien a chercher. Ces deux parametres sont")
    print("  fixes par une formule, et le moteur ne sait porter qu'un")
    print("  scalaire. C'est un developpement, pas une acquisition.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
