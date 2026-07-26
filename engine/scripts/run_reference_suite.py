#!/usr/bin/env python3
"""Run the normative reference suite — CI entry point for TICKET 2.2.

Exits non-zero if any case that could run drifted outside its tolerance.
Coverage gaps (awaiting a published source, or awaiting the engine module) are
reported and do not fail the build: see tests/test_reference.py for why.

    python scripts/run_reference_suite.py [--json report.json]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from eurostruct_engine.reference import run_library  # noqa: E402


def main(argv: list[str]) -> int:
    report = run_library()
    print(report.render())

    if "--json" in argv:
        out = Path(argv[argv.index("--json") + 1])
        out.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        print(f"\nrapport ecrit: {out}")

    if not report.ok:
        print(
            f"\n::error::{len(report.failures)} cas de reference hors tolerance. "
            "Un ecart sur une reference validee est une regression: corriger le "
            "moteur, ou documenter le changement dans une note de release et "
            "incrementer la version majeure.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
