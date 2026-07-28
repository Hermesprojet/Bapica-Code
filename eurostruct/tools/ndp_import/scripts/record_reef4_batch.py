#!/usr/bin/env python3
"""Register a batch of Reef4-delivered National Annexes, identity read from page 1.

Why this replaces the hand-typed table
--------------------------------------
``record_fr_reef4_annexes.py`` carried a dict mapping each filename to a
reference, an edition and an indice de classement that I had typed after
reading page 1. That worked for seven documents. At twenty-four it stops being
sensible: my transcription becomes the least reliable step in a pipeline whose
whole point is that nothing is typed from memory.

Reef4's header is regular, and it repeats the identity twice — once in the
platform's own ``Document :`` line, once in AFNOR's title block below it:

    Reef4 - CSTB Page 1 sur 25 ... Document : NF EN 1992-1-1/NA (mars 2007) :
    Eurocode 2 - ... (Indice de classement : P18-711-1/NA)
    NF EN 1992-1-1/NA Mars 2007 P 18-711-1/NA ...

So the reference, the edition and the indice are PARSED, and the two renderings
are cross-checked against each other. A file whose two statements disagree is
refused rather than guessed at — that mismatch is exactly the kind of thing a
human skims past.

What is still not automated, and must not be
--------------------------------------------
The STATUS. Nothing here promotes a document to ``acquired``; nothing here
demotes one either. Whether a copy governs is a declaration an engineer makes,
and this script has no standing to make it.

Run from tools/ndp_import/:
    python scripts/record_reef4_batch.py --dir DIR [--dry-run]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import pdfplumber

sys.path.insert(0, str(Path(__file__).resolve().parent))
from record_fr_reef4_annexes import _mirror_to_other_countries  # noqa: E402

HERE = Path(__file__).resolve().parents[1]
CATALOGUE = HERE / "src/ndp_import/data/catalogue.json"

#: Reef4's own header line, which names the document and its date.
_PLATFORM = re.compile(
    r"Document\s*:\s*(?P<ref>NF\s+(?:EN\s+)?[\dA-Z\s./-]+?)\s*"
    r"\((?P<edition>[^)]{4,40})\)\s*:",
    re.IGNORECASE,
)

#: AFNOR's own indice de classement, printed inside the same header. The
#: character class must admit the letters of the /NA and /A1 suffixes: a first
#: pass stopped at "P22-314/" and dropped the very segment that says the
#: document is an annex.
#: Les espaces internes sont tolerees et retirees ensuite: un exemplaire
#: ecrit « P22- 382/NA », avec une espace APRES le tiret, et la classe de
#: caracteres s'y arretait en rendant « P22- ».
#:
#: L'indice apparait DEUX fois et les deux ne concordent pas toujours. Sur
#: NF EN 1994-1-2/NA, le bandeau Reef4 annonce « P22-412-2 » quand le bloc de
#: titre AFNOR porte « P 22-412-1/NA ». Le controle de double mention ne
#: portait que sur la reference et laissait passer: il porte maintenant aussi
#: sur l'indice, et un desaccord est SIGNALE plutot que tranche.
_INDICE = re.compile(
    r"Indice\s+de\s+classement\s*:\s*(?P<indice>[A-Z]\s?[\dA-Z/\s-]*?[\dA-Z])"
    r"(?=\s*[)\n]|\s+[A-Z]{2})"
)

#: L'indice tel que le bloc AFNOR l'imprime, hors parentheses.
_INDICE_TITLE = re.compile(r"\b([A-Z]\s?\d{2}-\s?[\dA-Z/-]*\d(?:/[A-Z]{2})?)\b")

#: What the document says it is an annex TO. The ``/A1`` suffix is part of the
#: identity, not decoration: without it NF EN 1990/NA and NF EN 1990/A1/NA
#: collapse onto one catalogue key and the second silently overwrites the
#: first. They are two different documents, both in force.
#: Insensible a la casse: un exemplaire ecrit « Annexe Nationale », avec une
#: majuscule a nationale, et la regex le rejetait comme illisible.
_ANNEX_TO = re.compile(
    r"annexe\s+nationale\s+(?:a|à|de)\s+la\s+"
    r"(?P<parent>NF\s+EN\s+[\d-]+(?:/A\d)?)",
    re.IGNORECASE,
)

MONTHS = {
    "janvier": "01", "fevrier": "02", "février": "02", "mars": "03",
    "avril": "04", "mai": "05", "juin": "06", "juillet": "07",
    "aout": "08", "août": "08", "septembre": "09", "octobre": "10",
    "novembre": "11", "decembre": "12", "décembre": "12",
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def identify(path: Path) -> dict[str, str] | None:
    """Parse the identity from page 1, or return None with the reason printed."""
    with pdfplumber.open(str(path)) as pdf:
        front = _norm(pdf.pages[0].extract_text() or "")

    plat = _PLATFORM.search(front)
    ind = _INDICE.search(front)
    parent = _ANNEX_TO.search(front)
    if not (plat and ind and parent):
        missing = [n for n, m in (("reference", plat), ("indice", ind),
                                  ("parent", parent)) if not m]
        print(f"  IGNORE {path.name}: {', '.join(missing)} illisible(s)")
        return None

    ref = _norm(plat.group("ref"))
    edition = _norm(plat.group("edition"))

    # Contre-verification: le bloc AFNOR repete la reference sous la ligne
    # Reef4. Si les deux ne concordent pas, on ne devine pas.
    if front.count(ref) < 2:
        print(f"  IGNORE {path.name}: « {ref} » n'apparait qu'une fois, "
              "les deux mentions de la page 1 ne se confirment pas")
        return None

    indice_platform = re.sub(r"\s+", "", ind.group("indice"))
    # Le bloc AFNOR suit la ligne Reef4: on cherche l'indice APRES elle.
    tail = front[ind.end():]
    alt = [re.sub(r"\s+", "", m.group(1)) for m in _INDICE_TITLE.finditer(tail[:200])]
    # Seul un ecart sur le NUMERO est signale. NF EN 1991-1-2/NA porte
    # « P06-112-2/NA » au bandeau et « P06-112-2 » au titre: c'est la meme
    # reference, ecrite avec et sans son suffixe. Signaler ca reviendrait a
    # crier au loup, et une alerte qui crie au loup finit ignoree — y compris
    # le jour ou elle porte sur un vrai desaccord comme celui de
    # NF EN 1994-1-2/NA, « P22-412-2 » contre « P22-412-1/NA ».
    def _number(x: str) -> str:
        return x.split("/")[0]

    disagreement = next(
        (a for a in alt
         if _number(a) != _number(indice_platform)
         and a[:6] == indice_platform[:6]),
        None,
    )

    m = re.match(r"(\w+)\s+(\d{4})", edition)
    effective = (
        f"{m.group(2)}-{MONTHS.get(m.group(1).lower(), '01')}-01" if m else None
    )
    parent_std = _norm(parent.group("parent")).replace("NF ", "")
    # « EN 1990/A1 » -> famille « EN 1990 », partie « A1 ».
    if "/" in parent_std:
        base, _, amendment = parent_std.partition("/")
        family, part = base.strip(), amendment.strip()
    else:
        family, _, part = parent_std.partition("-")
    return {
        "reference": ref, "edition": edition,
        "indice": indice_platform, "indice_disagreement": disagreement,
        "standard_family": family.strip(), "part": part.strip(),
        "effective_from": effective,
        "doc_id_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "filename": path.name,
    }


def doc_key(family: str, part: str, existing: set[str]) -> str:
    """The catalogue key, reusing whatever spelling the catalogue already has.

    ``EN 1990`` + ``A1`` flattens to ``FR-EN1990A1-NA`` here, while an earlier
    script wrote ``FR-EN1990-A1-NA``. Two spellings of one document is two
    entries for one document, and the mirror rows for BE/ES/DE already follow
    the older one. So the existing key wins whenever one is present.
    """
    flat = f"FR-{(family + part).replace(' ', '').replace('-', '')}-NA"
    if flat in existing:
        return flat
    dashed = f"FR-{family.replace(' ', '')}-{part}-NA"
    return dashed if dashed in existing else flat


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv[1:])

    data = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    by_key = {e["doc_key"]: e for e in data["documents"]}

    recorded, created, skipped = [], [], []
    seen_this_run: dict[str, str] = {}
    for path in sorted(args.dir.glob("*NA*.pdf")):
        ident = identify(path)
        if ident is None:
            skipped.append(path.name)
            continue

        key = doc_key(ident["standard_family"], ident["part"], set(by_key))
        if key in seen_this_run:
            print(f"  COLLISION sur {key}: {ident['filename']} et "
                  f"{seen_this_run[key]} revendiquent la meme entree. "
                  "Aucun des deux n'est ecrit.")
            skipped.append(ident["filename"])
            continue
        seen_this_run[key] = ident["filename"]

        entry = by_key.get(key)
        if entry is None:
            entry = {
                "doc_key": key, "country_code": "FR",
                "standard_family": ident["standard_family"],
                "part": ident["part"], "reference": ident["reference"],
                "title": f"Annexe Nationale — {ident['reference']}",
                "publisher": "AFNOR — Association francaise de normalisation",
                "acquisition": {
                    "how": "Achat sur https://www.boutique.afnor.org, ou "
                           "abonnement COBAZ.",
                    "licence": "Document payant, non redistribuable.",
                    "languages": ["fr"], "notes": "",
                },
                "parameters_expected": [], "phase": "P2",
                "document_role": "national_annex", "status": "not_acquired",
            }
            data["documents"].append(entry)
            by_key[key] = entry
            created.append(key)

        # Le statut ne descend jamais, et l'empreinte precedente est gardee.
        previous_status = entry.get("status", "not_acquired")
        previous_digest = entry.get("doc_id_sha256")
        alternates = list(entry.get("alternate_copy_hashes", ()))
        if previous_digest and previous_digest != ident["doc_id_sha256"]:
            if previous_digest not in alternates:
                alternates.append(previous_digest)

        acq = entry.setdefault("acquisition", {})
        previous_note = (acq.get("notes") or "").strip()

        entry.update({
            "reference": ident["reference"],
            "edition_read_from_cover": f"{ident['edition']} (PARSEE en page 1)",
            "effective_from": ident["effective_from"],
            "status": ("acquired" if previous_status == "acquired"
                       else "acquired_for_reading"),
            "doc_id_sha256": ident["doc_id_sha256"],
            "alternate_copy_hashes": alternates,
        })
        acq["notes"] = (
            (previous_note + "\n\n--- exemplaire Reef4 ---\n" if previous_note else "")
            + f"Identite PARSEE en page 1 de {ident['filename']}, et confirmee "
            f"par la double mention de la page (bandeau Reef4 + bloc AFNOR). "
            f"Indice de classement: {ident['indice']}. "
            + (
                f"DESACCORD INTERNE AU DOCUMENT: le bandeau de la plateforme "
                f"annonce « {ident['indice']} » et le bloc de titre de "
                f"l'editeur porte « {ident['indice_disagreement']} ». Les deux "
                "sont reproduits tels quels; aucun n'est retenu contre "
                "l'autre. A TRANCHER sur l'exemplaire papier ou aupres de "
                "l'AFNOR avant tout achat ou toute citation. "
                if ident.get("indice_disagreement") else ""
            )
            + f"Edition "
            f"{ident['edition']}. STATUT A DECLARER par l'ingenieur qui "
            "depose: 'acquired' si l'exemplaire fait foi pour le bureau "
            "d'etudes. Detenir ce fichier ne confirme aucune valeur."
        )
        recorded.append(
            f"{key:20s} {ident['reference']:22s} {ident['edition']:16s} "
            f"{ident['indice']:16s} {ident['doc_id_sha256'][:12]}"
        )

    # Toute norme que seule la France porte recoit une entree BE/ES/DE:
    # un pays a qui il manque une ligne est un pays dont la liste d'achat
    # est silencieusement incomplete.
    mirrored = _mirror_to_other_countries(data)

    if not args.dry_run:
        CATALOGUE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    print(f"\n{len(recorded)} annexe(s) enregistree(s):")
    for line in recorded:
        print("   " + line)
    if created:
        print(f"\n{len(created)} entree(s) creee(s): {', '.join(sorted(created))}")
    if skipped:
        print(f"\n{len(skipped)} fichier(s) IGNORE(S) faute d'identite lisible.")
    if mirrored:
        print(f"\n{len(mirrored)} entree(s) miroir BE/ES/DE, not_acquired, "
              "reference marquee A CONFIRMER.")
    print("\nAucun statut n'est promu ni retrograde: cette declaration revient")
    print("a l'ingenieur. Le mode strict reste bloque.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
