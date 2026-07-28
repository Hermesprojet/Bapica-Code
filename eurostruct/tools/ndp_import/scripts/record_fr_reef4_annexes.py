#!/usr/bin/env python3
"""Record the French National Annexes delivered through Reef4 (CSTB).

Seven files, the first of this deposit to pass triage as usable for a national
parameter. Each identity below was READ on page 1 of the file it names —
reference, edition, indice de classement — and each digest is computed from the
bytes actually held, never typed.

What they are
-------------
Genuine AFNOR National Annexes, homologated, each with its own indice de
classement and its date of taking effect. They arrive through Reef4, the CSTB's
document platform, whose banner sits above AFNOR's cover. That banner is what
made the triage classify them as CSTB guidance and refuse them — see
``test_a_national_annex_delivered_through_a_platform_stays_an_annex``.

Two findings worth carrying into the catalogue
----------------------------------------------
1. **The annex to EN 1991-1-1 is not called what the catalogue asked for.**
   It is ``NF P 06-111-2`` (juin 2004), published as a standalone French
   standard under the older AFNOR practice, before the ``/NA`` suffix
   convention. Anyone sent to buy "NF EN 1991-1-1/NA" would be looking for a
   designation that does not exist. The catalogue entry is corrected to the
   reference the document itself carries.

2. **EN 1990 needs two documents, not one.** ``NF EN 1990/NA`` (décembre 2011)
   and ``NF EN 1990/A1/NA`` (décembre 2007) are complementary, not competing:
   the second is the annex to amendment A1. The triage's competing-editions
   warning fires on them because both map to "EN 1990"; that warning asks a
   human to check, which remains the right instruction.

Why ``acquired_for_reading`` and not ``acquired``
--------------------------------------------------
``acquired`` means a value read from the file may be CONFIRMED. Nothing in this
script is entitled to make that declaration: the pipeline's rule throughout is
that the depositing engineer declares the role, and a script is not an engineer.
No licence stamp was found on any of the seven — no "Uncontrolled Copy", no
third-party licensee — so nothing here contradicts their being authoritative.
An engineer who holds the licence flips the status in one line.

Run from tools/ndp_import/:
    python scripts/record_fr_reef4_annexes.py --dir DIR [--dry-run]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
CATALOGUE = HERE / "src/ndp_import/data/catalogue.json"

#: filename -> (doc_key, reference as printed, edition, indice, note)
READINGS: dict[str, tuple[str, str, str, str, str]] = {
    "f8a438d7-NF_EN_1990__NA.pdf": (
        "FR-EN1990-NA", "NF EN 1990/NA", "decembre 2011", "P 06-100-1/NA",
        "Annexe nationale a la NF EN 1990:2003. « pour prendre effet le 30 "
        "decembre 2011 ». A completer par NF EN 1990/A1/NA pour l'amendement A1.",
    ),
    "aaeee55f-NF_EN_1990__A1__NA.pdf": (
        "FR-EN1990-A1-NA", "NF EN 1990/A1/NA", "decembre 2007",
        "P 06-100-1/A1/NA",
        "Annexe nationale a la NF EN 1990/A1:2006. COMPLEMENTAIRE de "
        "NF EN 1990/NA, pas une edition concurrente: elle porte sur "
        "l'amendement A1 (annexe A2, ponts).",
    ),
    "38187f3d-NF_EN_199111__NA.pdf": (
        "FR-EN199111-NA", "NF P 06-111-2", "juin 2004", "P 06-111-2",
        "Annexe nationale a la NF EN 1991-1-1, publiee comme NORME FRANCAISE "
        "DISTINCTE et non sous un suffixe /NA — pratique AFNOR anterieure a "
        "cette convention. Le catalogue reclamait « NF EN 1991-1-1/NA », "
        "designation qui n'existe pas. Inclut l'amendement A1 (mars 2009) "
        "d'apres la page de garde.",
    ),
    "78368e72-NF_EN_199112__NA.pdf": (
        "FR-EN199112-NA", "NF EN 1991-1-2/NA", "fevrier 2007",
        "P 06-112-2/NA",
        "Annexe nationale a la NF EN 1991-1-2 (actions sur les structures "
        "exposees au feu).",
    ),
    "32fec0c6-NF_EN_199113__NA.pdf": (
        "FR-EN199113-NA", "NF EN 1991-1-3/NA", "mai 2007", "P 06-113-1/NA",
        "Annexe nationale a la NF EN 1991-1-3 (charges de neige). « pour "
        "prendre effet le 20 mai 2007 ».",
    ),
    "a7cad75a-NF_EN_199114__NA.pdf": (
        "FR-EN199114-NA", "NF EN 1991-1-4/NA", "mars 2008", "P 06-114-1/NA",
        "Annexe nationale a la NF EN 1991-1-4 (actions du vent). « pour "
        "prendre effet le 27 mars 2008 ».",
    ),
    "bff8c1f7-NF_EN_199115__NA.pdf": (
        "FR-EN199115-NA", "NF EN 1991-1-5/NA", "fevrier 2008",
        "P 06-115-1/NA",
        "Annexe nationale a la NF EN 1991-1-5 (actions thermiques).",
    ),
    "2ea0d20f-NF_EN_199116__NA.pdf": (
        "FR-EN199116-NA", "NF EN 1991-1-6/NA", "mars 2009",
        "P 06-116-1/NA",
        "Annexe nationale de la NF EN 1991-1-6 (actions en cours "
        "d'execution).",
    ),
    "196fabd4-NF_EN_199117__NA.pdf": (
        "FR-EN199117-NA", "NF EN 1991-1-7/NA", "septembre 2008",
        "P 06-117/NA",
        "Annexe nationale a la NF EN 1991-1-7 (actions accidentelles). "
        "ATTENTION a l'indice: « P 06-117/NA », SANS le segment numerique "
        "supplementaire que portent ses voisines (P 06-116-1/NA, "
        "P 06-115-1/NA). Ce n'est pas une coquille de lecture.",
    ),
    "f8e2e1ed-NF_EN_19912__NA.pdf": (
        "FR-EN19912-NA", "NF EN 1991-2/NA", "mars 2008", "P 06-120-1/NA",
        "Annexe nationale a la NF EN 1991-2 (actions sur les ponts dues au "
        "trafic).",
    ),
    "8b5cd71f-NF_EN_19913__NA.pdf": (
        "FR-EN19913-NA", "NF EN 1991-3/NA", "janvier 2010", "P 06-130/NA",
        "Annexe nationale a la NF EN 1991-3 (actions induites par les "
        "appareils de levage et les machines).",
    ),
    "1054d11a-NF_EN_19914__NA.pdf": (
        "FR-EN19914-NA", "NF EN 1991-4/NA", "novembre 2007", "P 06-140/NA",
        "Annexe nationale a la NF EN 1991-4 (silos et reservoirs).",
    ),
}


def _split(key: str) -> tuple[str, str, str]:
    """``FR-EN199115-NA`` -> ("EN 1991", "", "1-5"). Only for entries the
    catalogue did not already carry."""
    body = key.split("-", 1)[1].rsplit("-", 1)[0]      # EN199115 / EN1990-A1
    if body.startswith("EN1990"):
        return "EN 1990", "", ("A1" if "A1" in body else "")
    digits = body[2:]
    return f"EN {digits[:4]}", "", "-".join(digits[4:]) or ""


#: Mirroring a newly discovered standard onto the other three countries.
#: Recording a French annex creates a catalogue entry France alone carries,
#: which breaks the invariant that the four countries track the same set of
#: standards — and a country silently missing an entry is a country whose
#: acquisition list is quietly incomplete. Done here rather than patched after
#: each batch, because each batch broke it again.
_MIRROR = {
    "BE": ("NBN", "NBN {std} ANB", "Achat sur https://www.nbn.be."),
    "ES": ("AENOR", "UNE-{std} Anexo Nacional", "Achat sur https://www.une.org."),
    "DE": ("DIN", "DIN {std}/NA", "Achat sur https://www.beuth.de."),
}


def _mirror_to_other_countries(data: dict) -> list[str]:
    """Give BE, ES and DE an entry for every standard only France carries."""
    by_country: dict[str, dict[str, dict]] = {}
    for e in data["documents"]:
        if e.get("document_role") != "national_annex":
            continue
        key = f"{e['standard_family']}|{e['part']}"
        by_country.setdefault(e["country_code"], {})[key] = e

    created = []
    for key, fr_entry in by_country.get("FR", {}).items():
        family, part = key.split("|")
        std = f"{family}-{part}" if part else family
        for cc, (publisher, pattern, how) in _MIRROR.items():
            if key in by_country.get(cc, {}):
                continue
            doc_key = f"{cc}-{fr_entry['doc_key'].split('-', 1)[1]}"
            data["documents"].append({
                "doc_key": doc_key, "country_code": cc,
                "standard_family": family, "part": part,
                "reference": pattern.format(std=std),
                "title": f"Annexe Nationale a l'{std}",
                "publisher": publisher,
                "acquisition": {
                    "how": how,
                    "licence": "Document payant, non redistribuable.",
                    "languages": [],
                    "notes": (
                        "REFERENCE A CONFIRMER. La designation nationale d'une "
                        "annexe n'est PAS previsible: la France publie celle de "
                        "l'EN 1991-1-1 sous « NF P 06-111-2 », sans suffixe /NA. "
                        "Le libelle porte ici est une hypothese de FORME, a "
                        "remplacer par ce que porte le document reel."
                    ),
                },
                "parameters_expected": [], "phase": "P1",
                "document_role": "national_annex", "status": "not_acquired",
            })
            created.append(doc_key)
    return created


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv[1:])

    data = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    by_key = {e["doc_key"]: e for e in data["documents"]}

    applied, missing_file, created = [], [], []
    for filename, (key, ref, edition, indice, note) in READINGS.items():
        path = args.dir / filename
        if not path.exists():
            missing_file.append(filename)
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()

        entry = by_key.get(key)
        if entry is None:
            # NF EN 1990/A1/NA n'etait pas au catalogue: l'amendement A1 a sa
            # propre annexe, et la liste ne le prevoyait pas.
            family, _, part = _split(key)
            entry = {
                "doc_key": key, "country_code": "FR",
                "standard_family": family, "part": part,
                "reference": ref,
                "title": f"Annexe Nationale — {ref}",
                "publisher": "AFNOR — Association francaise de normalisation",
                "acquisition": {
                    "how": "Achat sur https://www.boutique.afnor.org, ou "
                           "abonnement COBAZ.",
                    "licence": "Document payant, non redistribuable.",
                    "languages": ["fr"],
                    "notes": "",
                },
                "parameters_expected": [], "phase": "P1",
                "document_role": "national_annex",
                "status": "not_acquired",
            }
            data["documents"].append(entry)
            created.append(key)

        # Ne JAMAIS declasser. NF EN 1991-1-3/NA etait deja 'acquired', et une
        # premiere version de ce script l'a fait retomber a
        # 'acquired_for_reading' en ecrasant au passage l'empreinte du fichier
        # qui faisait foi. Un exemplaire de plus n'a jamais retire son autorite
        # a celui qu'on detenait deja.
        previous_status = entry.get("status", "not_acquired")
        previous_digest = entry.get("doc_id_sha256")
        status = (
            "acquired" if previous_status == "acquired"
            else "acquired_for_reading"
        )

        # L'empreinte precedente est CONSERVEE, pas remplacee: c'est un autre
        # rendu du meme document, exactement ce que prevoit
        # alternate_copy_hashes.
        alternates = list(entry.get("alternate_copy_hashes", ()))
        if previous_digest and previous_digest != digest:
            if previous_digest not in alternates:
                alternates.append(previous_digest)
            kept = previous_digest
        else:
            kept = None

        # La note existante est PRESERVEE. Celle de NF EN 1991-1-3/NA porte
        # « INCOMPLET: edition de base de mai 2007, SANS les amendements A1
        # (juillet 2011) ni A2 (juillet 2022) » — une reserve que personne ne
        # doit perdre parce qu'un exemplaire de plus est arrive.
        acq = entry.setdefault("acquisition", {})
        previous_note = (acq.get("notes") or "").strip()

        entry.update({
            "reference": ref,
            "edition_read_from_cover": f"{edition} (LUE en page 1)",
            # PAS de promotion vers 'acquired': voir le docstring. Un script
            # ne declare pas qu'un document fait foi. Une DEGRADATION serait
            # pire encore, et la ligne ci-dessus l'empeche.
            "status": status,
            "doc_id_sha256": digest,
            "alternate_copy_hashes": alternates,
        })
        acq["notes"] = (
            (previous_note + "\n\n--- exemplaire Reef4 depose en complement ---\n"
             if previous_note else "")
            + (
                (f"Exemplaire precedemment enregistre conserve en copie "
                 f"alternative ({kept[:16]}...). " if kept else "")
                +
                f"{note} Indice de classement: {indice}. Exemplaire livre par "
                "Reef4 (plateforme documentaire CSTB), version 4.4.3.1, "
                "edition 167, mars 2012. Aucun tampon de licence nominative ni "
                "mention « Uncontrolled Copy » relevee. STATUT A DECLARER par "
                "l'ingenieur qui depose: 'acquired' si l'exemplaire fait foi "
                "pour le bureau d'etudes."
            )
        )
        applied.append(
            f"{key:20s} {ref:22s} {edition:16s} {status:22s} {digest[:16]}"
        )

    mirrored = _mirror_to_other_countries(data)

    if not args.dry_run:
        CATALOGUE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    print(f"{len(applied)} annexe(s) nationale(s) francaise(s) enregistree(s):")
    for line in applied:
        print("   " + line)
    if created:
        print(f"\nEntree(s) creee(s) au catalogue: {', '.join(created)}")
    if mirrored:
        print(f"\n{len(mirrored)} entree(s) miroir creee(s) pour BE/ES/DE, "
              "statut not_acquired,")
        print("reference marquee « A CONFIRMER »: les quatre pays doivent "
              "suivre le meme")
        print("jeu de normes, sinon la liste d'acquisition d'un pays est "
              "silencieusement")
        print("incomplete.")
    if missing_file:
        print(f"\nFICHIER(S) ABSENT(S) de {args.dir}: {', '.join(missing_file)}")
    print()
    print("Aucune n'est PROMUE « fait foi » — cette declaration revient a")
    print("l'ingenieur, pas a un script. Aucune n'est DECLASSEE non plus:")
    print("un exemplaire de plus ne retire pas son autorite a celui qu'on")
    print("detenait deja, et son empreinte est conservee en copie alternative.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
