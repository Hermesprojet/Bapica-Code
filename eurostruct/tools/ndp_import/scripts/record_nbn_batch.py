#!/usr/bin/env python3
"""Register Belgian National Annexes, and detect the ones they supersede.

The NBN cover is regular and says more than AFNOR's:

    Norme belge NBN EN 1990 ANB:2021 ... Valable a partir de 23-03-2021
    Remplace NBN EN 1990 ANB:2013

That third line is the reason this script exists rather than a variant of the
French one. AFNOR's covers do not name the edition they replace, so a
superseded copy in the catalogue can only be found by someone noticing. NBN
prints it, so it can be checked mechanically — and it has to be, because the
failure it prevents is the worst one this catalogue can suffer.

The failure in question, found on the first run
------------------------------------------------
``NBN EN 1990 ANB`` was held in its 2013 edition at status ``acquired`` — the
status that means a value read from it may be CONFIRMED. The 2021 edition says,
on its own cover, that it replaces 2013. A study signed on the 2013 values would
have cited an annex withdrawn five years earlier, and nothing in the pipeline
would have said so.

An external register had claimed the 2021 edition existed. That claim was
recorded as a flag and explicitly NOT acted upon, because the register named no
document and no URL. It turned out to be right, to the day: 2021-03-23. Being
right is not the same as being verifiable, and the flag was the correct response
to an unverifiable claim — the document is what settles it.

What happens to a superseded edition
--------------------------------------
It is closed, not deleted. ``effective_to`` is set to the day before the new
edition takes effect, its digest moves to ``superseded_copies``, and the note
says which edition replaced it and on what date. Ten-year liability means a
study signed in 2019 was signed against the 2013 annex, and that has to stay
readable.

Run from tools/ndp_import/:
    python scripts/record_nbn_batch.py --dir DIR [--dry-run]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

import pdfplumber

sys.path.insert(0, str(Path(__file__).resolve().parent))
from record_fr_reef4_annexes import _mirror_to_other_countries  # noqa: E402

HERE = Path(__file__).resolve().parents[1]
CATALOGUE = HERE / "src/ndp_import/data/catalogue.json"

_SELF = re.compile(
    r"Norme\s+belge\s+(?P<ref>NBN\s+EN\s+[\d-]+(?:/A\d)?[\s-]ANB)\s*:\s*(?P<year>\d{4})",
    re.IGNORECASE,
)
#: « Valable a partir de 23-03-2021 ». Un premier jet acceptait « d » et
#: « du » mais pas « de », et rendait une date vide sur TOUS les documents
#: recents sans rien signaler.
_VALID_FROM = re.compile(
    r"Valable\s+(?:a|à)\s+partir\s+d[eu]?\s+(\d{2})-(\d{2})-(\d{4})",
    re.IGNORECASE,
)

#: Le separateur avant « ANB » est une espace sur dix-sept documents et un
#: TIRET sur un seul: « NBN EN 1991-1-2-ANB ». Variation typographique de
#: l'editeur, pas du sens.
#:
#: Couverture ANCIENNE (2007-2013), tout autre: la reference precede la
#: mention « Norme belge », l'edition s'ecrit en toutes lettres, et il y a un
#: INDICE DE CLASSEMENT — « B 51 », « B 03 ». Contrairement a ce que j'avais
#: affirme, le NBN en attribue donc un; il est bien plus large que l'indice
#: AFNOR (une famille, pas un document) mais il existe.
_SELF_OLD = re.compile(
    r"(?P<ref>NBN\s+EN\s+[\d-]+(?:/A\d)?[\s-]ANB)\s+Norme\s+belge\s+"
    r"(?P<edition>\d+e?\s+(?:ed|éd)\.?,?\s+[a-zéû]+\s+(?P<year>\d{4}))",
    re.IGNORECASE,
)
_INDICE_BE = re.compile(r"Indice\s+de\s+classement\s*:\s*([A-Z]\s?\d+)",
                        re.IGNORECASE)
_REPLACES = re.compile(
    r"Remplace\s+(?P<ref>NBN\s+EN\s+[\d-]+(?:/A\d)?[\s-]ANB)\s*:\s*(?P<year>\d{4})",
    re.IGNORECASE,
)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def identify(path: Path) -> dict | None:
    with pdfplumber.open(str(path)) as pdf:
        front = _norm(pdf.pages[0].extract_text() or "")

    me = _SELF.search(front)
    old = None if me else _SELF_OLD.search(front)
    if not (me or old):
        print(f"  IGNORE {path.name}: ni « Norme belge NBN ... ANB:AAAA » "
              "ni « NBN ... ANB Norme belge Ne ed., ... »")
        return None

    vf = _VALID_FROM.search(front)
    rep = _REPLACES.search(front)
    ind = _INDICE_BE.search(front)
    ref = _norm((me or old).group("ref"))
    std = ref.replace("NBN ", "").replace(" ANB", "").replace("-ANB", "").strip()
    family, _, part = std.partition("-")
    if family.startswith("EN 1990") or " " not in std:
        family, part = std, ""
    else:
        family = "EN " + std.split()[1].split("-")[0]
        part = std.split("-", 1)[1] if "-" in std.split()[1] else ""

    edition = (
        me.group("year") if me else _norm(old.group("edition"))
    )
    return {
        "reference": ref, "edition": edition,
        "indice": _norm(ind.group(1)) if ind else None,
        "effective_from": (f"{vf.group(3)}-{vf.group(2)}-{vf.group(1)}" if vf else None),
        "replaces": (
            f"{_norm(rep.group('ref'))}:{rep.group('year')}" if rep else None
        ),
        "replaces_year": rep.group("year") if rep else None,
        "standard_family": family, "part": part,
        "doc_id_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "filename": path.name,
    }


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv[1:])

    data = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    by_key = {e["doc_key"]: e for e in data["documents"]}

    recorded, superseded, skipped, created = [], [], [], []
    for path in sorted(args.dir.glob("*ANB*.pdf")):
        ident = identify(path)
        if ident is None:
            skipped.append(path.name)
            continue

        flat = (ident["standard_family"] + ident["part"]).replace(" ", "").replace("-", "")
        key = f"BE-{flat}-NA"
        entry = by_key.get(key)
        if entry is None:
            # Le depot cree l'entree, comme cote francais. Refuser aurait
            # oblige a une intervention manuelle a chaque nouvelle partie —
            # EN 1993-4-2 et 4-3 sont arrivees ainsi, et aucune phase ne les
            # prevoyait.
            entry = {
                "doc_key": key, "country_code": "BE",
                "standard_family": ident["standard_family"],
                "part": ident["part"], "reference": ident["reference"],
                "title": f"Annexe Nationale — {ident['reference']}",
                "publisher": "NBN — Bureau de Normalisation",
                "acquisition": {
                    "how": "Achat sur https://www.nbn.be.",
                    "licence": "Document payant, non redistribuable.",
                    "languages": ["fr", "nl"], "notes": "",
                },
                "parameters_expected": [], "phase": "P2",
                "document_role": "national_annex", "status": "not_acquired",
            }
            data["documents"].append(entry)
            by_key[key] = entry
            created.append(key)

        acq = entry.setdefault("acquisition", {})
        previous_note = (acq.get("notes") or "").strip()
        previous_edition = str(
            entry.get("edition_read_from_cover") or entry.get("edition") or ""
        )
        previous_digest = entry.get("doc_id_sha256")

        # Le document dit lui-meme ce qu'il remplace. Si l'exemplaire detenu
        # porte cette edition, il est PERIME: on le clot, on ne l'ecrase pas.
        closed = None
        if ident["replaces_year"] and ident["replaces_year"] in previous_edition:
            eff = ident["effective_from"]
            closed = {
                "reference": entry["reference"],
                "edition": previous_edition,
                "doc_id_sha256": previous_digest,
                "effective_to": (
                    (date.fromisoformat(eff) - timedelta(days=1)).isoformat()
                    if eff else None
                ),
                "superseded_by": f"{ident['reference']}:{ident['edition']}",
            }
            entry.setdefault("superseded_copies", []).append(closed)
            superseded.append(
                f"{entry['reference']} ed. {previous_edition} -> remplacee par "
                f"{ident['edition']}"
            )

        entry.update({
            "reference": ident["reference"],
            "edition_read_from_cover": f"{ident['edition']} (PARSEE en page 1)",
            "effective_from": ident["effective_from"],
            "status": ("acquired" if entry.get("status") == "acquired"
                       else "acquired_for_reading"),
            "doc_id_sha256": ident["doc_id_sha256"],
        })
        acq["notes"] = (
            (previous_note + "\n\n--- exemplaire NBN depose ---\n"
             if previous_note else "")
            + f"Identite PARSEE en page 1 de {ident['filename']}. "
            + (f"Indice de classement NBN: {ident['indice']}. "
               if ident.get("indice") else "")
            + f"Edition {ident['edition']}, en vigueur depuis "
            + f"{ident['effective_from'] or 'date non lue'}. "
            + (
                f"CETTE EDITION REMPLACE {ident['replaces']} — l'exemplaire "
                f"precedemment detenu ({previous_edition}) est PERIME et a ete "
                "clos par effective_to; son empreinte est conservee dans "
                "superseded_copies, une etude signee sous l'ancienne edition "
                "devant rester lisible dix ans. "
                if closed else
                (f"Le document declare remplacer {ident['replaces']}, edition "
                 "qui n'etait pas detenue. " if ident["replaces"] else "")
            )
            + "STATUT A DECLARER par l'ingenieur qui depose."
        )
        recorded.append(
            f"{key:18s} {ident['reference']:24s} ed.{ident['edition']} "
            f"{ident['effective_from'] or '?':12s} {ident['doc_id_sha256'][:12]}"
        )

    mirrored = _mirror_to_other_countries(data)

    if not args.dry_run:
        CATALOGUE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    print(f"\n{len(recorded)} annexe(s) belge(s) enregistree(s):")
    for line in recorded:
        print("   " + line)
    if superseded:
        print(f"\n*** {len(superseded)} EDITION(S) DETENUE(S) DEVENUE(S) PERIMEE(S) ***")
        for line in superseded:
            print("   " + line)
        print("   Closes par effective_to, empreintes conservees. Une etude")
        print("   signee sous l'ancienne edition reste lisible.")
    if created:
        print(f"\n{len(created)} entree(s) creee(s): "
              f"{', '.join(sorted(created))}")
    if mirrored:
        print(f"{len(mirrored)} entree(s) miroir FR/ES/DE.")
    if skipped:
        print(f"\n{len(skipped)} fichier(s) ignore(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
