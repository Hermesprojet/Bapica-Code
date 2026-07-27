#!/usr/bin/env python3
"""Derive the expected values of the §7.4.2 span/depth reference cases.

Same discipline as the sibling generators: nothing here calls the engine.

The independent route on the branch that matters — (7.16a) versus (7.16b) — is
that the two expressions are evaluated **both ways at the boundary**. The engine
branches on ``rho > rho_0``; this script evaluates the two formulas separately
and checks they agree where rho meets rho_0, which is the one place a wrong
comparison operator would not show up as a jump. A branch chosen with ``>=``
instead of ``>`` is invisible everywhere else.

Three cases:

``EC2-LD-101``   isostatique, 4 HA20 — (7.16b), dispense acquise
``EC2-LD-102``   console, meme section — K = 0,4, dispense REFUSEE. Le meme
                 element, le meme ferraillage, un verdict oppose: c'est le
                 parametre national qui decide.
``EC2-LD-103``   travee de rive, 4 HA16 + cloisons fragiles sur 10 m —
                 (7.16a), facteur 7/l_eff et acier surabondant plafonne

Run from engine/:
    python scripts/generate_span_depth_references.py [--dry-run]
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
LIBRARY = HERE / "src/eurostruct_engine/reference/library"

COUNTRY = "FR"
AS_OF = "2026-07-26"
FCK, FYK = 30.0, 500.0
K_TABLE = {
    "simply_supported": 1.0, "end_span_continuous": 1.3,
    "interior_span_continuous": 1.5, "flat_slab": 1.2, "cantilever": 0.4,
}


def eq_7_16a(K: float, rho: float, rho_0: float) -> float:
    sq = math.sqrt(FCK)
    return K * (11.0 + 1.5 * sq * rho_0 / rho
                + 3.2 * sq * (rho_0 / rho - 1.0) ** 1.5)


def eq_7_16b(K: float, rho: float, rho_c: float, rho_0: float) -> float:
    sq = math.sqrt(FCK)
    return K * (11.0 + 1.5 * sq * rho_0 / (rho - rho_c)
                + sq * math.sqrt(rho_c / rho_0) / 12.0)


def check_branch_continuity() -> None:
    """At rho == rho_0 with rho' = 0 the two expressions must coincide.

    (7.16a) loses its third term there — (rho_0/rho - 1) is zero — and (7.16b)
    loses its own third term for rho' = 0. Both collapse to K(11 + 1,5 sqrt(fck)).
    If they did not agree, the engine's choice of strict versus non-strict
    comparison would silently change the answer at the boundary.
    """
    rho_0 = 1e-3 * math.sqrt(FCK)
    a = eq_7_16a(1.0, rho_0, rho_0)
    b = eq_7_16b(1.0, rho_0, 0.0, rho_0)
    assert abs(a - b) < 1e-12, f"discontinuite a la frontiere: {a} vs {b}"
    assert abs(a - (11.0 + 1.5 * math.sqrt(FCK))) < 1e-12


def solve(*, b: float, d: float, l_eff_mm: float, system: str, A_req: float,
          A_prov: float, A_comp: float = 0.0, flange: float | None = None,
          brittle: bool = False) -> dict[str, float]:
    K = K_TABLE[system]
    rho_0 = 1e-3 * math.sqrt(FCK)
    rho = A_prov / (b * d)
    rho_c = A_comp / (b * d)

    basic = (eq_7_16b(K, rho, rho_c, rho_0) if rho > rho_0
             else eq_7_16a(K, rho, rho_0))

    stress = min(500.0 / (FYK * A_req / A_prov), 1.5)
    flange_f = 0.8 if (flange is not None and flange > 3.0) else 1.0
    threshold = 8.5 if system == "flat_slab" else 7.0
    l_m = l_eff_mm / 1000.0
    long_f = threshold / l_m if (brittle and l_m > threshold) else 1.0

    limit = basic * stress * flange_f * long_f
    actual = l_eff_mm / d
    return {
        "K": K, "rho_0": rho_0, "rho": rho, "rho_comp": rho_c,
        "basic_ratio": basic, "stress_factor": stress,
        "flange_factor": flange_f, "long_span_factor": long_f,
        "limit_ratio": limit, "actual_ratio": actual,
        "exempt": 1.0 if actual <= limit else 0.0,
        "utilisation": actual / limit,
    }


def _source(method: str) -> dict[str, str]:
    return {
        "title": "Resolution independante — " + method,
        "publisher": "EUROSTRUCT — scripts/generate_span_depth_references.py",
        "edition": "1", "locator": "",
        "notes": (
            "Valeurs attendues obtenues sans appeler le moteur, et continuite "
            "des formules (7.16a)/(7.16b) verifiee a la frontiere rho = rho_0. "
            "L'accord atteste l'algebre; il ne remplace pas un exemple resolu "
            "publie, et les cas 'official_worked_example' de "
            "planned_coverage.json restent des lacunes ouvertes."
        ),
    }


def build() -> list[dict]:
    b, h, d = 300.0, 600.0, 550.0
    A20 = 4 * math.pi * 20.0**2 / 4.0
    A16 = 4 * math.pi * 16.0**2 / 4.0

    common = {
        "country": COUNTRY, "as_of": AS_OF, "strict_ndp": False,
        "b": {"value": b, "unit": "mm"},
        "h": {"value": h, "unit": "mm"},
        "d": {"value": d, "unit": "mm"},
        "concrete_grade": "C30/37", "steel_grade": "B500B",
    }

    return [
        {
            "reference_id": "EC2-LD-101",
            "title": ("Dispense du calcul de fleche — poutre isostatique "
                      "300x550, 4 HA20, portee 6 m"),
            "normative_scope": ["EN 1992-1-1 §7.4.2"],
            "country_scope": [COUNTRY],
            "source_type": "manual_reference",
            "source_document": _source("(7.16b) evaluee terme a terme"),
            "harness": "ec2.span_depth",
            "input_dataset": {
                **common,
                "l_eff": {"value": 6000.0, "unit": "mm"},
                "system": "simply_supported",
                "A_s_required": {"value": A20, "unit": "mm**2"},
                "A_s_provided": {"value": A20, "unit": "mm**2"},
            },
            "expected_outputs": solve(
                b=b, d=d, l_eff_mm=6000.0, system="simply_supported",
                A_req=A20, A_prov=A20),
            "tolerance_rules": [{"output": "*", "rel": 1e-9}],
            "notes": ("rho > rho_0: c'est (7.16b) qui s'applique, sans acier "
                      "comprime. Dispense acquise."),
        },
        {
            "reference_id": "EC2-LD-102",
            "title": ("Dispense refusee — meme section en console, K = 0,4 "
                      "au lieu de 1,0"),
            "normative_scope": ["EN 1992-1-1 §7.4.2(2)", "Tab. 7.4N"],
            "country_scope": [COUNTRY],
            "source_type": "manual_reference",
            "source_document": _source("meme (7.16b), K de la ligne console"),
            "harness": "ec2.span_depth",
            "input_dataset": {
                **common,
                "l_eff": {"value": 6000.0, "unit": "mm"},
                "system": "cantilever",
                "A_s_required": {"value": A20, "unit": "mm**2"},
                "A_s_provided": {"value": A20, "unit": "mm**2"},
            },
            "expected_outputs": solve(
                b=b, d=d, l_eff_mm=6000.0, system="cantilever",
                A_req=A20, A_prov=A20),
            "tolerance_rules": [{"output": "*", "rel": 1e-9}],
            "notes": (
                "Meme poutre, meme ferraillage, meme portee que EC2-LD-101; "
                "seul le systeme structural change et 'exempt' bascule de 1 a "
                "0. Le cas verrouille le fait que le parametre national decide "
                "du verdict — s'il etait lu comme un scalaire, les deux cas "
                "donneraient la meme reponse et l'un des deux serait faux."
            ),
        },
        {
            "reference_id": "EC2-LD-103",
            "title": ("Travee de rive 4 HA16, portee 10 m avec cloisons "
                      "fragiles — (7.16a), facteur 7/l et acier surabondant"),
            "normative_scope": ["EN 1992-1-1 §7.4.2(2)"],
            "country_scope": [COUNTRY],
            "source_type": "manual_reference",
            "source_document": _source(
                "(7.16a) sur la branche faiblement armee, facteurs du "
                "§7.4.2(2) appliques separement"),
            "harness": "ec2.span_depth",
            "input_dataset": {
                **common,
                "l_eff": {"value": 10000.0, "unit": "mm"},
                "system": "end_span_continuous",
                "A_s_required": {"value": A16 * 0.75, "unit": "mm**2"},
                "A_s_provided": {"value": A16, "unit": "mm**2"},
                "supports_brittle_partitions": True,
            },
            "expected_outputs": solve(
                b=b, d=d, l_eff_mm=10000.0, system="end_span_continuous",
                A_req=A16 * 0.75, A_prov=A16, brittle=True),
            "tolerance_rules": [{"output": "*", "rel": 1e-9}],
            "notes": (
                "Trois branches en meme temps: rho < rho_0 donc (7.16a); "
                "A_prov/A_req = 4/3 donne un facteur de contrainte de 1,333 "
                "sous le plafond de 1,5; et 10 m > 7 m avec cloisons fragiles "
                "applique 0,7."
            ),
        },
    ]


def main(argv: list[str]) -> int:
    check_branch_continuity()
    cases = build()
    payload = {
        "_comment": (
            "Cas de reference a valeurs attendues DERIVEES INDEPENDAMMENT. "
            "Regenerer avec scripts/generate_span_depth_references.py. Ne "
            "jamais recopier une valeur depuis une sortie du moteur."
        ),
        "cases": cases,
    }
    out = LIBRARY / "ec2_span_depth.json"
    if "--dry-run" not in argv:
        out.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")
    print("Continuite (7.16a)/(7.16b) a rho = rho_0: verifiee")
    for c in cases:
        print(f"\n{c['reference_id']}  {c['title'][:60]}")
        for k, v in c["expected_outputs"].items():
            print(f"     {k:18s} {v:16.9f}")
    print(f"\n{len(cases)} cas ecrits dans {out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
