#!/usr/bin/env python3
"""Emit the SQL seed of the National Annex parameter sets.

Single source of truth: the JSON files under
``engine/src/eurostruct_engine/ndp/data/``. The engine reads them directly and
the database is seeded from the same files, so a parameter cannot say one thing
to the calculation and another in the note de calcul.

Run from the repository root::

    python db/seed/generate_ndp_seed.py > db/seed/0001_ndp.sql

Every emitted row keeps its ``status``. Nothing is promoted to ``na_confirmed``
here: that transition requires a named engineer and a date, and the schema
enforces it (``confirmed_ndp_needs_a_verifier``).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "engine" / "src" / "eurostruct_engine" / "ndp" / "data"


def q(s: str | None) -> str:
    """Quote a SQL string literal, or NULL."""
    if s is None:
        return "null"
    return "'" + s.replace("'", "''") + "'"


def main() -> int:
    out: list[str] = [
        "-- GENERATED FILE — DO NOT EDIT.",
        "--",
        "-- Produced by db/seed/generate_ndp_seed.py from the engine's NDP data.",
        "-- Re-run after changing engine/src/eurostruct_engine/ndp/data/*.json:",
        "--",
        "--     python db/seed/generate_ndp_seed.py > db/seed/0001_ndp.sql",
        "--",
        "-- Statuses are carried across verbatim. A parameter reaches",
        "-- 'na_confirmed' only when an engineer has read the published National",
        "-- Annex and signed for it; the schema refuses that status without a",
        "-- named verifier and a date.",
        "",
        "begin;",
        "",
    ]

    for path in sorted(DATA.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        country = raw["country"]
        version = raw["version"]

        out.append(f"-- ----- {country} — {version} " + "-" * 30)
        out.append(
            "insert into national_annex_sets "
            "(country, region, version, published_at, description)\n"
            f"values ({q(country)}::country_code, null, {q(version)}, "
            f"{q(raw['published_at'])}::date, {q(raw['description'])})\n"
            "on conflict (country, region, version) do nothing;"
        )
        out.append("")

        for key, item in sorted(raw["parameters"].items()):
            out.append(
                "insert into national_annex_parameters "
                "(set_id, key, value, unit, status, standard, clause, "
                "description, source, en_recommended)\n"
                "select s.id, "
                f"{q(key)}, {float(item['value'])!r}, "
                f"{q(item.get('unit', 'dimensionless'))}, "
                f"{q(item['status'])}::ndp_status, {q(item['standard'])}, "
                f"{q(item['clause'])}, {q(item['description'])}, "
                f"{q(item['source'])}, "
                f"{item['en_recommended'] if item.get('en_recommended') is not None else 'null'}\n"
                "from national_annex_sets s\n"
                f"where s.country = {q(country)}::country_code and s.region is null "
                f"and s.version = {q(version)}\n"
                "on conflict (set_id, key) do nothing;"
            )
        out.append("")

    out.append("commit;")
    sys.stdout.write("\n".join(out) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
