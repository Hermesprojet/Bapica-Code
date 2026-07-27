#!/usr/bin/env python3
"""Record every Belgian National Annex actually in hand.

Why this exists
---------------
The catalogue said three documents were acquired. Ten had been deposited and
read. So ``ndp-import catalogue`` kept listing, as "still to obtain", annexes
that were sitting in the deposit — and the same files were sent three times
over because the report gave no way to tell.

An inventory that under-reports what it holds is not a safe error: it wastes
the acquisition effort that is the whole point of the report.

What this does NOT do
---------------------
Marking a document acquired says "we hold this file", never "we trust its
values". Every parameter stays ``pending_verification``; strict mode stays
blocked. ``parameters_expected`` is left empty where no extraction patterns
have been written yet: claiming parameters we cannot search for would be the
same lie in the other direction.

Editions below are LUES sur la page de garde and remain A DECLARER by the
depositor — the pipeline never infers an edition from a file.

Run from tools/ndp_import/:
    python scripts/record_be_acquisitions.py [--dry-run]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
CATALOGUE = HERE / "src/ndp_import/data/catalogue.json"

_COMMON = (
    "Metadonnees LUES sur la page de garde, a DECLARER par le deposant. "
    "Detenir ce fichier ne confirme aucune valeur: tous les parametres restent "
    "pending_verification tant qu'un ingenieur habilite n'a pas signe."
)

#: doc_key -> (sha256, edition read from cover, pages, language, note)
ACQUIRED: dict[str, tuple[str, str, int, str, str]] = {
    "BE-EN1990-NA": (
        "40a8eeac9471d7203e81ff8a03921e064775734a1ad2e7c468f8dff63f943b16",
        "1e ed., septembre 2007", 15, "fr",
        "Base de calcul des structures: coefficients partiels et combinaisons "
        "d'actions. Aucun motif d'extraction ecrit a ce jour.",
    ),
    "BE-EN199111-NA": (
        "16acbb56fcc160a3867ac000f91505a79724bed28f3ca58500cfcf06b7c9a58e",
        "1e ed., septembre 2007", 11, "fr",
        "Poids volumiques, charges d'exploitation. Aucun motif d'extraction "
        "ecrit a ce jour.",
    ),
    "BE-EN199112-NA": (
        "bb39ccad867e4cb183534719143f07dffd7ab71a17512137482dc841514c7808",
        "1e ed., mai 2008", 27, "fr",
        "Actions sur les structures exposees au feu. Aucun motif d'extraction "
        "ecrit a ce jour.",
    ),
    "BE-EN199113-NA": (
        "9a2880b2f489a9803e1fc73b2268a0306ce2c298b568f0c52eeb10872980c29d",
        "1e uitg., oktober 2007 (version neerlandaise)", 9, "nl",
        "Charges de neige. Version NEERLANDAISE: la version francaise n'a pas "
        "ete deposee. Aucun motif d'extraction ecrit a ce jour.",
    ),
    "BE-EN199114-NA": (
        "a406441e0b5b53b79e4d0940fef1df72a6617ac260dc5dcf7749070c4999ffaf",
        "1e uitg., december 2010 (version neerlandaise)", 63, "nl",
        "Actions du vent. Version NEERLANDAISE: la version francaise n'a pas "
        "ete deposee. Aucun motif d'extraction ecrit a ce jour.",
    ),
    "BE-EN19912-NA": (
        "25735718283606f39fec41fae861b95cbfefd9e795b3d2c86b0763221191c11e",
        "1e ed., octobre 2011", 43, "fr",
        "Actions sur les ponts dues au trafic. Hors perimetre P1 (batiment). "
        "Aucun motif d'extraction ecrit a ce jour.",
    ),
}


def _verify_against_deposit(deposit: Path) -> int:
    """Recompute every digest from the files and refuse on any mismatch.

    A digest that is *typed* is a digest that can be invented — and one was,
    in the first draft of this script: only the leading 16 characters were
    known from the triage output and the remainder was filled in. The values
    were well-formed, 64 hex characters, and completely false.

    Nothing in the repository could have caught that, because the deposited
    PDFs are not in it. So the digests are cross-checked here against the
    actual files whenever they are available, and this mode is what should be
    run before committing a change to the table above.
    """
    from ndp_import.model import SourceDocument

    have = {SourceDocument.digest(p): p.name for p in sorted(deposit.glob("*.pdf"))}
    bad = 0
    for key, (sha, *_rest) in sorted(ACQUIRED.items()):
        if sha in have:
            print(f"  OK   {key:18s} {sha[:16]}...  {have[sha]}")
        else:
            bad += 1
            print(f"  FAUX {key:18s} {sha[:16]}...  AUCUN fichier depose "
                  f"n'a cette empreinte")
    print()
    if bad:
        print(f"{bad} empreinte(s) ne correspondent a aucun fichier. NE PAS "
              f"COMMITTER: une empreinte se calcule, elle ne se saisit pas.")
    else:
        print(f"{len(ACQUIRED)} empreinte(s) verifiees contre les fichiers reels.")
    return 1 if bad else 0


def main(argv: list[str]) -> int:
    if "--verify" in argv:
        deposit = Path(argv[argv.index("--verify") + 1])
        return _verify_against_deposit(deposit)

    data = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    by_key = {e["doc_key"]: e for e in data["documents"]}

    missing = [k for k in ACQUIRED if k not in by_key]
    if missing:
        print("ERREUR: cles absentes du catalogue: " + ", ".join(missing))
        return 1

    for key, (sha, edition, pages, lang, note) in ACQUIRED.items():
        entry = by_key[key]
        entry["status"] = "acquired"
        entry["doc_id_sha256"] = sha
        entry["edition_read_from_cover"] = edition
        entry["acquisition"]["notes"] = (
            f"ACQUIS en version texte ({pages} pages, langue {lang}). "
            f"{_COMMON} {note}"
        )
        entry.setdefault("parameters_expected", [])

    if "--dry-run" not in argv:
        CATALOGUE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    total = sum(1 for e in data["documents"] if e["status"] != "not_acquired")
    print(f"{len(ACQUIRED)} annexe(s) belge(s) marquee(s) acquises.")
    print(f"{total} document(s) en main au total dans le catalogue.")
    print()
    print("AUCUN parametre ne change de statut. Le mode strict reste bloque.")
    print("NBN EN 1997-1 ANB (geotechnique) reste le seul manque pour P1 en")
    print("Belgique: les fichiers deposes sous ce nom sont l'Eurocode de base,")
    print("un projet slovene, et une page d'appat au telechargement.")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(HERE / "src"))
    raise SystemExit(main(sys.argv))
