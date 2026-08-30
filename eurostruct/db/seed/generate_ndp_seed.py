#!/usr/bin/env python3
"""Emit the SQL seed of the National Annexes and their parameters.

Single source of truth: the JSON files under
``engine/src/eurostruct_engine/ndp/data/``. The engine reads them directly and
the database is seeded from the same files, so a parameter cannot say one thing
to the calculation and another in the note de calcul.

Run from the repository root::

    python db/seed/generate_ndp_seed.py > db/seed/0001_ndp.sql

Every row keeps its ``validation_status`` verbatim. Nothing is promoted to
``confirmed`` here: that transition requires a named engineer and a date, and
the schema enforces it (``confirmed_ndp_is_signed``).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "engine" / "src" / "eurostruct_engine" / "ndp" / "data"


def q(s: Any) -> str:
    """Quote a SQL string literal, or NULL."""
    if s is None:
        return "null"
    return "'" + str(s).replace("'", "''") + "'"


def num(x: Any) -> str:
    return "null" if x is None else repr(float(x))


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
        "-- 'confirmed' only when an engineer has read the published National",
        "-- Annex and signed for it; the schema refuses that status without a",
        "-- named verifier, a date, and source_type = 'national_annex'.",
        "",
        "begin;",
        "",
    ]

    for path in sorted(DATA.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        country = raw["country_code"]
        out.append(f"-- ===== {country} — {raw['country_name']} " + "=" * 30)
        out.append("")

        for annex in raw["annexes"]:
            std = f"{annex['standard_family']}-{annex['part']}"
            out.append(f"-- {annex['reference']} ({std})")
            out.append(
                "insert into national_annexes (country_code, standard_family, part, "
                "reference, edition, effective_from, effective_to, source_official, "
                "source_url_or_doc_id)\nvalues ("
                f"{q(country)}::country_code, {q(annex['standard_family'])}, "
                f"{q(annex['part'])}, {q(annex['reference'])}, {q(annex['edition'])}, "
                f"{q(annex['effective_from'])}::date, "
                f"{q(annex.get('effective_to'))}"
                + ("::date" if annex.get("effective_to") else "")
                + f", {q(annex['source_official'])}, "
                f"{q(annex.get('source_url_or_doc_id'))})\n"
                "on conflict (country_code, standard_family, part, edition) "
                "do nothing;"
            )
            out.append("")

            for name, item in sorted(annex["parameters"].items()):
                # LA SECONDE PORTE DE LA MEME PIECE.
                #
                # Le moteur refuse depuis 07df06c qu'un fichier du depot porte
                # `confirmed` — mesure du 30/08: deux champs bascules dans
                # `be.json` suffisaient a faire aboutir un calcul belge STRICT
                # et a le declarer signable, sans relecteur nomme ni ligne en
                # base.
                #
                # Ce generateur lit les MEMES fichiers et ecrit dans la base de
                # reference. Sans ce controle, une graine confirmee y entrerait
                # pendant que le moteur, lui, refuserait de la lire: la base
                # dirait une chose et le calcul une autre — pire que les deux
                # erreurs separement.
                if item.get("validation_status") == "confirmed":
                    raise SystemExit(
                        f"REFUS: {country}/{std}:{name} porte 'confirmed' dans "
                        f"{path.name}. Un fichier transcrit; il ne confirme "
                        "pas. La confirmation est l'acte date d'un ingenieur "
                        "nomme, contre-signe par un second, enregistre par le "
                        "chemin d'autorite — pas un champ que l'on edite. Voir "
                        "engine/src/eurostruct_engine/ndp/registry.py, "
                        "_statut_transcrit."
                    )
                out.append(
                    "insert into national_annex_parameters (annex_id, country_code, "
                    "standard_family, part, national_annex_reference, edition, "
                    "effective_from, effective_to, parameter_name, parameter_value, "
                    "unit, source_official, source_url_or_doc_id, source_type, "
                    "validation_status, verified_at, verified_by, notes, clause, "
                    "description, en_recommended, has_variants)\n"
                    f"select a.id, {q(country)}::country_code, "
                    f"{q(annex['standard_family'])}, {q(annex['part'])}, "
                    f"{q(annex['reference'])}, {q(annex['edition'])}, "
                    f"{q(annex['effective_from'])}::date, "
                    f"{q(annex.get('effective_to'))}"
                    + ("::date" if annex.get("effective_to") else "")
                    + f", {q(name)}, {num(item['parameter_value'])}, "
                    f"{q(item.get('unit', 'dimensionless'))}, "
                    f"{q(item.get('source_official', annex['source_official']))}, "
                    f"{q(item.get('source_url_or_doc_id', annex.get('source_url_or_doc_id')))}, "
                    f"{q(item.get('source_type', 'national_annex'))}::ndp_source_type, "
                    f"{q(item['validation_status'])}::ndp_validation_status, "
                    f"{q(item.get('verified_at'))}"
                    + ("::timestamptz" if item.get("verified_at") else "")
                    + ", null, "
                    f"{q(item.get('notes'))}, {q(item['clause'])}, "
                    f"{q(item['description'])}, {num(item.get('en_recommended'))}, "
                    f"{'true' if item.get('variants') else 'false'}\n"
                    "from national_annexes a\n"
                    f"where a.country_code = {q(country)}::country_code\n"
                    f"  and a.standard_family = {q(annex['standard_family'])}\n"
                    f"  and a.part = {q(annex['part'])}\n"
                    f"  and a.edition = {q(annex['edition'])}\n"
                    "on conflict (country_code, standard_family, part, "
                    "parameter_name, effective_from) do nothing;"
                )
                for v in item.get("variants", []):
                    out.append(
                        "insert into national_annex_parameter_variants "
                        "(parameter_id, condition, value, description)\n"
                        f"select p.id, {q(v['condition'])}, {num(v['value'])}, "
                        f"{q(v['description'])}\n"
                        "from national_annex_parameters p\n"
                        f"where p.country_code = {q(country)}::country_code\n"
                        f"  and p.standard_family = {q(annex['standard_family'])}\n"
                        f"  and p.part = {q(annex['part'])}\n"
                        f"  and p.parameter_name = {q(name)}\n"
                        "on conflict (parameter_id, condition) do nothing;"
                    )
            out.append("")

    out.append("commit;")
    sys.stdout.write("\n".join(out) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
