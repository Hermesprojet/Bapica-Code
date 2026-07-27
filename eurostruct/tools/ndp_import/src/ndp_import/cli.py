#!/usr/bin/env python3
"""Command line for the National Annex import pipeline.

    ndp-import catalogue
        What official documents are still needed, and how to obtain them.

    ndp-import extract --pdf ANNEXE.pdf --country BE --standard "EN 1992" \
                       --part 1-1 --reference "NBN EN 1992-1-1 ANB" \
                       --publisher NBN --edition "2010" --effective-from 2010-04-01 \
                       --language fr --deposited-by "ing. A. Dupont" \
                       --out run.json
        Read a deposited document and write the extraction run. Produces
        candidates only.

    ndp-import review --run run.json
        Print the review queue for an engineer, hardest cases first.

    ndp-import apply --run run.json --decisions decisions.json \
                     --dataset ../../engine/src/eurostruct_engine/ndp/data/be.json
        Apply signed decisions. Refuses anything lacking source, reference,
        named verifier or timestamp.

The metadata of a document is *declared*, never inferred from the file: an
edition read out of a PDF header is a guess, an edition typed by the person
holding the document is a statement they answer for.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from .catalogue import render_catalogue
from .model import DocumentRole
from .extract import extract_document, read_pages
from .model import ExtractionCandidate, ExtractionRun, SourceDocument
from .review import (
    ReviewQueue,
    apply_decisions,
    load_decisions,
    merge_into_dataset,
    to_engine_records,
)


def _expected_for(doc: SourceDocument) -> list[str] | None:
    """The parameters the catalogue expects from *this* document.

    Without this the extractor searched every pattern it knows, so an EC2
    annex came back reporting that ``theta_crit_classe_4`` was "not found" —
    a steel-fire parameter that has no business being looked for there. The
    noise matters: a reviewer scanning a long "not found" list to spot the
    entries that actually concern their document will eventually stop reading
    it. ``ExtractionRun.not_found`` has always documented itself as
    catalogue-driven; this makes the behaviour match.

    Returns ``None`` — meaning "search everything" — when the catalogue has no
    entry for the document, so an unknown one is still fully explored.
    """
    from .catalogue import load_catalogue

    standard = f"{doc.standard_family}-{doc.part}"
    for entry in load_catalogue():
        if entry.country_code == doc.country_code and entry.standard == standard:
            return list(entry.parameters_expected) or None
    return None


def _load_run(path: Path) -> ExtractionRun:
    raw = json.loads(path.read_text(encoding="utf-8"))
    d = raw["document"]
    doc = SourceDocument(
        doc_id=d["doc_id"], filename=d["filename"],
        role=DocumentRole(d.get("role", "base_eurocode")),
        country_code=d["country_code"],
        standard_family=d["standard_family"], part=d["part"],
        reference=d["reference"], publisher=d["publisher"], edition=d["edition"],
        effective_from=date.fromisoformat(d["effective_from"]),
        effective_to=date.fromisoformat(d["effective_to"]) if d.get("effective_to") else None,
        language=d["language"], page_count=d["page_count"],
        deposited_by=d["deposited_by"], deposited_at=d["deposited_at"],
        notes=d.get("notes"),
    )
    cands = tuple(
        ExtractionCandidate(
            candidate_id=c["candidate_id"], doc_id=c["doc_id"],
            parameter_name=c["parameter_name"], page=c["page"], snippet=c["snippet"],
            raw_value=c.get("raw_value"), parsed_value=c.get("parsed_value"),
            unit=c.get("unit", "dimensionless"), clause=c.get("clause"),
            bbox=tuple(c["bbox"]) if c.get("bbox") else None,
            pattern_id=c.get("pattern_id"), confidence=c.get("confidence", 0.0),
            extractor_version=c.get("extractor_version", "?"),
        )
        for c in raw["candidates"]
    )
    return ExtractionRun(
        doc=doc, candidates=cands, run_at=raw["run_at"],
        extractor_version=raw["extractor_version"],
        not_found=tuple(raw.get("not_found", [])),
        pages_skipped_overlay=tuple(raw.get("pages_skipped_overlay", [])),
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="ndp-import", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("catalogue", help="documents officiels a obtenir")

    tr = sub.add_parser("triage", help="classer des documents deposes")
    tr.add_argument("paths", nargs="+", type=Path)
    tr.add_argument(
        "--needed", nargs="*", default=["EN 1992-1-1"],
        help="normes dont le moteur a besoin (defaut: EN 1992-1-1)",
    )
    tr.add_argument("--json", type=Path, default=None)

    ex = sub.add_parser("extract", help="depouiller un document depose")
    ex.add_argument("--pdf", type=Path, required=True)
    ex.add_argument(
        "--role", required=True,
        choices=[r.value for r in DocumentRole],
        help="nature normative DECLAREE du document; un nom de fichier ne suffit pas",
    )
    ex.add_argument("--country", required=True)
    ex.add_argument("--standard", required=True, help='ex. "EN 1992"')
    ex.add_argument("--part", required=True, help='ex. "1-1"')
    ex.add_argument("--reference", required=True)
    ex.add_argument("--publisher", required=True)
    ex.add_argument("--edition", required=True)
    ex.add_argument("--effective-from", required=True)
    ex.add_argument("--language", required=True)
    ex.add_argument("--deposited-by", required=True)
    ex.add_argument("--parameters", nargs="*", default=None)
    ex.add_argument("--out", type=Path, required=True)

    rv = sub.add_parser("review", help="file de relecture")
    rv.add_argument("--run", type=Path, required=True)

    ap_ = sub.add_parser("apply", help="appliquer des decisions signees")
    ap_.add_argument("--run", type=Path, required=True)
    ap_.add_argument("--decisions", type=Path, required=True)
    ap_.add_argument("--dataset", type=Path, required=True)
    ap_.add_argument("--dry-run", action="store_true")

    args = ap.parse_args(argv)

    if args.cmd == "catalogue":
        print(render_catalogue())
        return 0

    if args.cmd == "triage":
        from .triage import render_triage, triage_batch

        results = triage_batch(args.paths, needed_standards=args.needed)
        print(render_triage(results))
        if args.json:
            args.json.write_text(
                json.dumps([r.to_dict() for r in results], indent=2,
                           ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        return 0

    if args.cmd == "extract":
        doc = SourceDocument(
            doc_id=SourceDocument.digest(args.pdf),
            filename=args.pdf.name,
            role=DocumentRole(args.role),
            country_code=args.country.upper(),
            standard_family=args.standard,
            part=args.part,
            reference=args.reference,
            publisher=args.publisher,
            edition=args.edition,
            effective_from=date.fromisoformat(args.effective_from),
            language=args.language,
            # Compte reel, pas zero: l'en-tete de la file de relecture affiche
            # ce nombre, et « 0 pages » sur un document de 31 pages est une
            # fausse indication dans le dossier que l'ingenieur signe.
            page_count=len(read_pages(args.pdf)),
            deposited_by=args.deposited_by,
            deposited_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        run = extract_document(
            doc, args.pdf, parameters=args.parameters or _expected_for(doc)
        )
        args.out.write_text(
            json.dumps(run.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(ReviewQueue(run).render())
        print(f"\nExtraction ecrite dans {args.out}")
        print(
            "Aucune de ces valeurs n'est utilisable en l'etat: ce sont des "
            "propositions. Les faire relever par un ingenieur habilite."
        )
        return 0

    if args.cmd == "review":
        print(ReviewQueue(_load_run(args.run)).render())
        return 0

    if args.cmd == "apply":
        run = _load_run(args.run)
        reviewed = apply_decisions(run, load_decisions(args.decisions))
        records = to_engine_records(reviewed)
        result = merge_into_dataset(args.dataset, run.doc, records, dry_run=args.dry_run)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if result["still_pending"]:
            print(
                f"\n{len(result['still_pending'])} parametre(s) restent "
                "pending_verification: le mode strict continue de bloquer.",
                file=sys.stderr,
            )
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
