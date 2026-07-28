#!/usr/bin/env python3
"""Bring EN 1999 — aluminium — into the catalogue's scope.

Why this is a script and not an import
---------------------------------------
The other families entered the catalogue by themselves: depositing an annex
created its entry. EN 1996 (masonry) arrived that way, without ever having
figured in the roadmap.

Aluminium could not. The four EN 1999 files deposited are the BASE standards —
``NF EN 1999-1-2`` to ``1-5`` — and none of them says "annexe nationale". A base
Eurocode, homologated NF or not, carries the recommended values, so nothing in
the deposit created anything. Putting aluminium in scope is a product decision,
taken by the user, and this script records that decision rather than inferring
it from files.

What the entries claim, and what they do not
---------------------------------------------
The reference of each entry is a FORM, marked "A CONFIRMER". This deposit gave
five reasons not to trust a constructed designation:

* the annex to EN 1991-1-1 is ``NF P 06-111-2``, with no ``/NA`` at all;
* EC3 parts 1-10 to 1-12 jump from P 22-319-1 to P 22-380-1 / 381 / 382;
* the family follows the material, not the standard number;
* seismic reuses P 06 on a range unrelated to the actions it otherwise numbers;
* ``P 06-035-1/NA`` carried a ``-1`` segment that a four-point series had not
  predicted.

The base standards in hand do say something worth recording: they are numbered
P 22-152 to P 22-155, so aluminium shares P 22 with steel and composite. That is
a search aid on the family, not a prediction of the annex's number.

Run from tools/ndp_import/:
    python scripts/add_en1999_aluminium.py [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from record_fr_reef4_annexes import _mirror_to_other_countries  # noqa: E402

HERE = Path(__file__).resolve().parents[1]
CATALOGUE = HERE / "src/ndp_import/data/catalogue.json"

#: part -> (title, phase). Fire design follows the FEU phase like its siblings
#: in the other families; the rest sit in P7, a phase the roadmap did not have
#: because aluminium was not in it.
PARTS = {
    "1-1": ("Regles generales", "P7"),
    "1-2": ("Calcul du comportement au feu", "FEU"),
    "1-3": ("Structures sensibles a la fatigue", "P7"),
    "1-4": ("Tôles de structure formees a froid", "P7"),
    "1-5": ("Structures en coque", "P7"),
}

#: The base standards deposited, whose indices were read on their covers. Kept
#: as evidence about the FAMILY, not as a prediction of the annex numbers.
BASE_INDICES = {
    "1-2": "P 22-152", "1-3": "P 22-153",
    "1-4": "P 22-154", "1-5": "P 22-155",
}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv[1:])

    data = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    existing = {e["doc_key"] for e in data["documents"]}

    created = []
    for part, (title, phase) in PARTS.items():
        key = f"FR-EN1999{part.replace('-', '')}-NA"
        if key in existing:
            continue
        base = BASE_INDICES.get(part)
        data["documents"].append({
            "doc_key": key, "country_code": "FR",
            "standard_family": "EN 1999", "part": part,
            "reference": f"NF EN 1999-{part}/NA",
            "title": f"Annexe Nationale a l'EN 1999-{part} — {title}",
            "publisher": "AFNOR — Association francaise de normalisation",
            "acquisition": {
                "how": "Achat sur https://www.boutique.afnor.org, ou "
                       "abonnement COBAZ. Chercher par le NUMERO DE NORME "
                       f"(« EN 1999-{part} »), pas par un indice construit.",
                "licence": "Document payant, non redistribuable.",
                "languages": ["fr"],
                "notes": (
                    "REFERENCE A CONFIRMER — le libelle porte ici est une "
                    "hypothese de FORME. Cinq contre-exemples releves dans ce "
                    "depot interdisent de construire une designation: "
                    "NF P 06-111-2 sans /NA, le saut P 22-380 des EC3 1-10 a "
                    "1-12, la famille qui suit le materiau, le sismique en "
                    "P 06-03x etranger aux actions en P 06-1xx, et le segment "
                    "-1 imprevu de P 06-035-1/NA."
                    + (
                        f" La norme de BASE NF EN 1999-{part} est en main et "
                        f"porte l'indice {base}: l'aluminium partage donc la "
                        "famille P 22 avec l'acier et le mixte. C'est une "
                        "indication sur la FAMILLE, pas sur le numero de "
                        "l'annexe."
                        if base else
                        " La norme de base de cette partie n'est pas en main."
                    )
                ),
            },
            "parameters_expected": [], "phase": phase,
            "document_role": "national_annex", "status": "not_acquired",
        })
        created.append(key)

    mirrored = _mirror_to_other_countries(data)

    if not args.dry_run:
        CATALOGUE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    print(f"{len(created)} entree(s) francaise(s) creee(s): {', '.join(created)}")
    print(f"{len(mirrored)} entree(s) miroir BE/ES/DE.")
    print()
    print("Toutes en not_acquired, reference marquee A CONFIRMER. Les quatre")
    print("normes de BASE deposees (NF EN 1999-1-2 a 1-5) ne sont pas")
    print("enregistrees comme annexes: elles portent les valeurs recommandees,")
    print("pas les valeurs nationales.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
