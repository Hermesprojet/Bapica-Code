#!/usr/bin/env python3
"""What is still missing, per country, with the indice where one is known.

Written to be run again rather than pasted once: the answer changes every time
a document is deposited.

Why the indice column is mostly empty
--------------------------------------
The indice de classement of a document nobody holds is exactly the thing this
report must not invent. Two observations from the French deposit make that
concrete:

* ``NF EN 1991-1-1``'s annex is not called ``NF EN 1991-1-1/NA`` at all. It is
  ``NF P 06-111-2``, a standalone French standard under the older AFNOR
  practice. Anyone sent to buy the first designation would find nothing.
* The EC3 indices run P22-311-1, -312-1, ... -318-1, -319-1 — and then jump to
  **P22-380-1, P22-381, P22-382** for parts 1-10, 1-11 and 1-12. The series
  that looks obvious for nine consecutive parts breaks on the tenth.

So an indice is printed only when it was READ on the cover of a held document.
Everything else says ``a rechercher``, which is the honest instruction: the
buyer looks it up on the publisher's site rather than trusting a pattern.

The observed pattern is printed at the end all the same — as a search aid, not
as a rule, with the break stated.

Run from tools/ndp_import/:
    python scripts/report_missing_annexes.py [--country FR]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
CATALOGUE = HERE / "src/ndp_import/data/catalogue.json"

#: Les notes ecrites a la main portent « P 06-100-1/NA », avec une espace
#: apres la lettre; celles du parseur portent « P18-711-1/NA », sans. Un
#: premier jet s'arretait a la lettre et affichait « P » pour douze documents
#: — troisieme fois dans cette session qu'une classe de caracteres trop
#: etroite tronque un indice en silence. Elle est desormais ancree sur la
#: forme reelle (lettre, deux chiffres, tiret, puis segments) et verifiee
#: sur les cinq ecritures rencontrees, dont « P 06-100-1/A1/NA ».
_INDICE_IN_NOTE = re.compile(r"Indice de classement:\s*([A-Z]\s?\d{2}-[\dA-Z/-]+)")

PUBLISHER_SITE = {
    "FR": "https://www.boutique.afnor.org",
    "BE": "https://www.nbn.be",
    "ES": "https://www.une.org",
    "DE": "https://www.beuth.de",
}


def indice_of(entry: dict) -> str | None:
    """The indice READ on a held document's cover, or None."""
    note = (entry.get("acquisition", {}) or {}).get("notes") or ""
    m = _INDICE_IN_NOTE.search(note)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else None


def sort_key(entry: dict) -> tuple:
    fam = entry.get("standard_family", "")
    part = entry.get("part", "") or ""
    nums = [int(n) for n in re.findall(r"\d+", fam + " " + part)]
    return (tuple(nums), part)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--country", default="FR")
    args = ap.parse_args(argv[1:])
    cc = args.country.upper()

    data = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    rows = [
        e for e in data["documents"]
        if e["country_code"] == cc and e.get("document_role") == "national_annex"
    ]
    held = [e for e in rows if e.get("status", "not_acquired") != "not_acquired"]
    missing = [e for e in rows if e.get("status", "not_acquired") == "not_acquired"]

    print(f"=== {cc} — annexes nationales ===")
    print(f"{len(held)} detenue(s), {len(missing)} manquante(s), "
          f"{len(rows)} au catalogue.\n")

    print(f"--- MANQUANTES ({len(missing)}) ---")
    print(f"{'norme':16s} {'reference au catalogue':34s} {'indice':16s} phase")
    for e in sorted(missing, key=sort_key):
        std = f"{e['standard_family']}-{e['part']}".rstrip("-")
        note = (e.get("acquisition", {}) or {}).get("notes") or ""
        # Une reference issue du miroir entre pays est une hypothese de FORME,
        # pas un nom a recopier chez un vendeur. Le dire sur chaque ligne.
        hypothetical = "A CONFIRMER" in note or "hypothese" in note.lower()
        ref = e["reference"] + (" (forme supposee)" if hypothetical else "")
        print(f"{std:16s} {ref:34s} {'a rechercher':16s} {e.get('phase','?')}")

    print(f"\n--- DETENUES ({len(held)}), indice lu en couverture ---")
    print(f"{'norme':16s} {'reference':24s} {'indice':20s} edition")
    for e in sorted(held, key=sort_key):
        std = f"{e['standard_family']}-{e['part']}".rstrip("-")
        ind = indice_of(e) or "(non releve)"
        ed = str(e.get("edition_read_from_cover") or e.get("edition") or "")
        print(f"{std:16s} {e['reference']:24s} {ind:20s} {ed[:34]}")

    if cc == "BE":
        print("\n--- comment chercher chez le NBN ---")
        print("Le NBN ne numerote pas ses annexes par un indice de classement:")
        print("la reference EST le nom du document. Il n'y a donc rien a")
        print("deviner de ce cote, contrairement a la France.")
        print()
        print("La forme « NBN EN <norme> ANB » se lit a l'identique sur les")
        print("NEUF annexes detenues, sans exception. C'est une regularite")
        print("bien mieux etablie que celle des indices francais — mais elle")
        print("porte sur neuf documents d'une seule famille de parties, et le")
        print("depot francais a montre qu'une serie reguliere peut rompre.")
        print()
        print("A verifier au passage sur chaque fiche produit:")
        print("  * L'EDITION. NBN EN 1990 ANB est detenu en 2e ed. 2013 et un")
        print("    registre externe annonce une edition 2021 — non verifiee.")
        print("    Une annexe remplacee ne doit pas servir a un projet courant.")
        print("  * LA LANGUE. Deux des neuf annexes detenues sont en")
        print("    neerlandais (1991-1-3 et 1991-1-4). Le NBN publie en FR et")
        print("    en NL; verifier laquelle est commandee.")
        print()
        print("  Boutique: https://www.nbn.be — recherche par le numero de la")
        print("  norme, puis filtrer sur les documents « ANB ».")

    if cc == "FR":
        print("\n--- structure OBSERVEE des indices, aide a la recherche ---")
        print("Ce n'est PAS une regle: c'est ce qu'on lit sur les documents en")
        print("main. Deux contre-exemples suffisent a interdire d'extrapoler.")
        print()
        print("  EN 1990        P 06-100-1        (+ /A1 pour l'amendement)")
        print("  EN 1991-1-x    P 06-11x")
        print("  EN 1991-2/3/4  P 06-120-1 / 130 / 140")
        print("  EN 1992-1-1    P 18-711-1        EN 1992-2  P 18-720-1")
        print("  EN 1992-1-2    P 18-712-1        EN 1992-3  P 18-730")
        print("  EN 1993-1-1..9 P 22-311-1 a P 22-319-1")
        print("  EN 1993-2/3/4/5  P 22-320 / 331-332 / 341 / 350")
        print("  EN 1994-1-1/2  P 22-411-1 / 420-1     (mixte, meme P 22)")
        print("  EN 1995-x      P 21-711-1 / 712-1 / 720-1   (bois)")
        print("  EN 1996-x      P 10-611-1 / 612-1 / 620 / 630 (maconnerie)")
        print("  EN 1997-1      P 94-251-1                    (geotechnique)")
        print("  EN 1998-1..6   P 06-030-1 / 032 / 033-1 / 034 / 035-1 /")
        print("                 036-1                          (sismique)")
        print()
        print("  RUPTURES CONSTATEES:")
        print("   * EN 1991-1-1: l'annexe s'appelle NF P 06-111-2, PAS")
        print("     « NF EN 1991-1-1/NA ». Aucune convention /NA.")
        print("   * EN 1993-1-10/1-11/1-12: P 22-380-1 / 381 / 382, et non la")
        print("     suite P 22-3110 qu'on attendrait apres P 22-319-1.")
        print("   * la FAMILLE change avec le materiau et ne se devine pas:")
        print("     P 06 actions, P 18 beton, P 21 bois, P 22 acier ET mixte,")
        print("     P 10 maconnerie, P 94 geotechnique. L'acier et le mixte")
        print("     partagent P 22; le bois et la maconnerie ont chacun la leur.")
        print("   * le SISMIQUE retombe sur P 06 — P 06-030-1 pour l'EN 1998-1 —")
        print("     alors que P 06 sert par ailleurs aux actions, de P 06-100 a")
        print("     P 06-140. Meme prefixe, plage sans rapport. C'est le")
        print("     contre-exemple le plus net: connaitre la famille ne suffit")
        print("     meme pas a cadrer la recherche.")
        print()
        print("  UNE extrapolation a ete tentee et VERIFIEE ensuite, elle")
        print("  merite d'etre racontee. Sur la foi de P 06-030-1, 032, 033-1")
        print("  et 034, « P 06-035 » avait ete propose pour l'EN 1998-5, en")
        print("  precisant qu'il fallait le verifier. Le document porte")
        print("  « P 06-035-1/NA »: bon numero, plus un segment -1 imprevu —")
        print("  que 032 et 034 n'ont pas, et que 030, 033 et 036 ont.")
        print()
        print("  Une recherche sur la chaine exacte « P 06-035 » aurait donc pu")
        print("  ne rien rendre. C'est la cinquieme fois que la regularite")
        print("  apparente deraille sur un detail, et la meilleure raison de")
        print("  chercher par le NUMERO DE NORME.")
        print()
        print(f"  Rechercher sur {PUBLISHER_SITE[cc]} par le numero de la norme")
        print("  (« EN 1998-5 »), pas par l'indice suppose.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
