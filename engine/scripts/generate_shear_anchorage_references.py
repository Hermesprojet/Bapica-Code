#!/usr/bin/env python3
"""Derive the expected values of the shear and anchorage reference cases.

The point of a reference case is that its expected values come from somewhere
else. Reading them back out of the engine would produce a test that says
"the engine agrees with itself", which is true of any engine including a wrong
one.

So every figure below is computed here, in this file, by a route that does not
call the engine:

* ``V_Rd,c`` — from §6.2.2 eq. (6.2a) written out longhand, including the
  ``v_min`` floor evaluated separately and compared;
* ``V_Rd,max`` — through the strut's **trigonometry**, ``sin θ cos θ``, rather
  than the ``1/(cot θ + tan θ)`` identity the module uses;
* ``V_Rd,s`` — by counting the links a diagonal crack crosses;
* ``l_b,rqd`` — from equilibrium of the bar: the force it carries against the
  bond stress on its lateral surface, so the ``φ/4`` of eq. (8.3) is never
  assumed.

Where the two routes agree, the algebra is attested. That is not the same as an
agreement with a published worked example, and the cases say so: their
``source_type`` stays ``manual_reference``, and the ``official_worked_example``
entries of ``planned_coverage.json`` remain open gaps.

Run from engine/:
    python scripts/generate_shear_anchorage_references.py [--dry-run]
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
LIBRARY = HERE / "src/eurostruct_engine/reference/library"

#: The French parameter set is used because Belgium has no scalar bound on the
#: strut angle: NBN EN 1992-1-1 ANB §6.2.3(2) replaces 2,5 by an expression,
#: so a Belgian shear case cannot be replayed at all. Stated here rather than
#: left as an unexplained choice of country.
COUNTRY = "FR"
AS_OF = "2026-07-26"

GAMMA_C, GAMMA_S = 1.5, 1.15
ALPHA_CC_OTHER = 1.0       # §3.1.6(1)P, "autres cas" — l'effort tranchant
ALPHA_CT = 1.0             # §3.1.6(2)P — l'adherence
FCK, FYK = 30.0, 500.0
C_RD_C, V_MIN_C, K1_SHEAR = 0.18, 0.035, 0.15
NU1_C, NU1_DIV, ALPHA_CW = 0.6, 250.0, 1.0
RHO_W_MIN_C, S_L_MAX_C = 0.08, 0.75


def fctm(fck: float) -> float:
    """Tab. 3.1, fck <= 50 MPa."""
    return 0.30 * fck ** (2.0 / 3.0)


def v_rd_c_kN(b_w: float, d: float, A_sl: float) -> tuple[float, bool]:
    """§6.2.2(1), written longhand. Returns (kN, whether v_min governed)."""
    k = min(1.0 + math.sqrt(200.0 / d), 2.0)
    rho_l = min(A_sl / (b_w * d), 0.02)
    principal = C_RD_C / GAMMA_C * k * (100.0 * rho_l * FCK) ** (1.0 / 3.0)
    floor = V_MIN_C * k**1.5 * math.sqrt(FCK)
    stress = max(principal, floor)          # sigma_cp = 0: aucun effort normal
    return stress * b_w * d / 1000.0, floor > principal


def truss_kN(b_w: float, d: float, cot_theta: float, A_sw: float, s: float
             ) -> tuple[float, float]:
    """(V_Rd,s ; V_Rd,max) by two independent routes."""
    z = 0.9 * d
    fywd = FYK / GAMMA_S
    fcd = ALPHA_CC_OTHER * FCK / GAMMA_C
    nu1 = NU1_C * (1.0 - FCK / NU1_DIV)

    # V_Rd,s: count the links a diagonal crack of horizontal extent z cot(theta)
    # crosses, each yielding A_sw f_ywd. Not eq. (6.8).
    crossed = z * cot_theta / s
    v_rd_s = crossed * A_sw * fywd / 1000.0

    # V_Rd,max: cap the web compression V / (b_w z sin cos) at nu1 f_cd.
    # Not 1/(cot + tan).
    theta = math.atan(1.0 / cot_theta)
    v_rd_max = ALPHA_CW * nu1 * fcd * b_w * z * math.sin(theta) * math.cos(theta) / 1000.0
    return v_rd_s, v_rd_max


def anchorage_mm(phi: float, sigma_sd: float, eta_1: float) -> dict[str, float]:
    """§8.4, with l_b,rqd from equilibrium on the bar rather than eq. (8.3)."""
    f_ctd = ALPHA_CT * 0.7 * fctm(FCK) / GAMMA_C
    f_bd = 2.25 * eta_1 * 1.0 * f_ctd

    force = sigma_sd * math.pi * phi**2 / 4.0        # N carried by the bar
    bond_per_mm = f_bd * math.pi * phi               # N delivered per mm
    l_b_rqd = force / bond_per_mm

    l_b_min = max(0.3 * l_b_rqd, 10.0 * phi, 100.0)
    l_0_min = max(0.3 * 1.0 * l_b_rqd, 15.0 * phi, 200.0)
    return {
        "f_bd_MPa": f_bd,
        "l_b_rqd_mm": l_b_rqd,
        "l_bd_mm": max(l_b_rqd, l_b_min),            # tous les alpha valent 1,0
        "l_b_min_mm": l_b_min,
        "l_0_mm": max(l_b_rqd, l_0_min),
        "l_0_min_mm": l_0_min,
        "sigma_sd_MPa": sigma_sd,
    }


def _source(method: str) -> dict[str, str]:
    return {
        "title": "Resolution independante — " + method,
        "publisher": "EUROSTRUCT — scripts/generate_shear_anchorage_references.py",
        "edition": "1",
        "locator": "",
        "notes": (
            "Valeurs attendues obtenues par une voie DISTINCTE de celle du "
            "moteur. L'accord des deux atteste l'algebre; il ne remplace pas "
            "un exemple resolu publie, et les cas "
            "'official_worked_example' de planned_coverage.json restent des "
            "lacunes ouvertes."
        ),
    }


def build() -> list[dict]:
    b_w, d, A_sl = 300.0, 550.0, 4 * math.pi * 20.0**2 / 4.0
    A_sw, s, cot = 157.0, 150.0, 2.5

    v_c, floor_governs = v_rd_c_kN(b_w, d, A_sl)
    v_s, v_max = truss_kN(b_w, d, cot, A_sw, s)
    asw_min = RHO_W_MIN_C * math.sqrt(FCK) / FYK * b_w * 1000.0

    common_in = {
        "country": COUNTRY, "as_of": AS_OF, "strict_ndp": False,
        "b_w": {"value": b_w, "unit": "mm"},
        "d": {"value": d, "unit": "mm"},
        "A_sl": {"value": A_sl, "unit": "mm**2"},
        "concrete_grade": "C30/37", "steel_grade": "B500B",
    }

    cases = [
        {
            "reference_id": "EC2-SH-101",
            "title": (
                "Effort tranchant ELU avec treillis — 300x550 mm, C30/37, "
                "cot(theta)=2,5, cadres HA10/150, V_Ed=300 kN"
            ),
            "normative_scope": [
                "EN 1992-1-1 §6.2.2", "EN 1992-1-1 §6.2.3", "EN 1992-1-1 §9.2.2",
            ],
            "country_scope": [COUNTRY],
            "source_type": "manual_reference",
            "source_document": _source(
                "treillis compte barre par barre, ecrasement par la "
                "trigonometrie de la bielle"
            ),
            "harness": "ec2.beam_shear",
            "input_dataset": {
                **common_in,
                "V_Ed": {"value": 300.0, "unit": "kN"},
                "cot_theta": cot,
                "links": {"A_sw": {"value": A_sw, "unit": "mm**2"},
                          "s": {"value": s, "unit": "mm"}},
            },
            "expected_outputs": {
                "V_Rd_c_kN": v_c,
                "V_Rd_s_kN": v_s,
                "V_Rd_max_kN": v_max,
                "V_Rd_kN": min(v_s, v_max),
                "Asw_over_s_min_mm2_per_m": asw_min,
                "s_l_max_mm": S_L_MAX_C * d,
                "delta_F_td_kN": 0.5 * 300.0 * cot,
            },
            "tolerance_rules": [{"output": "*", "rel": 1e-9}],
            "notes": (
                "L'ecrasement des bielles gouverne (V_Rd,max < V_Rd,s), "
                "consequence previsible d'un cot(theta) eleve."
            ),
        },
        {
            "reference_id": "EC2-SH-102",
            "title": (
                "Effort tranchant ELU sans armatures calculees — meme section, "
                "V_Ed=80 kN < V_Rd,c"
            ),
            "normative_scope": ["EN 1992-1-1 §6.2.1", "EN 1992-1-1 §6.2.2"],
            "country_scope": [COUNTRY],
            "source_type": "manual_reference",
            "source_document": _source("eq. (6.2a) developpee, plancher v_min evalue a part"),
            "harness": "ec2.beam_shear",
            "input_dataset": {
                **common_in,
                "V_Ed": {"value": 80.0, "unit": "kN"},
                "cot_theta": 1.0,
            },
            "expected_outputs": {
                "V_Rd_c_kN": v_c,
                "V_Rd_kN": v_c,
                "Asw_over_s_min_mm2_per_m": asw_min,
                "s_l_max_mm": S_L_MAX_C * d,
                "delta_F_td_kN": 0.0,
            },
            "tolerance_rules": [{"output": "*", "rel": 1e-9}],
            "notes": (
                "V_Ed <= V_Rd,c: aucune armature calculee. V_Rd,s et V_Rd,max "
                "sont ABSENTS des sorties, et non nuls — le §6.2.1 ne les "
                "calcule pas dans ce regime. Le plancher v_min "
                + ("gouverne" if floor_governs else "ne gouverne pas") + " ici."
            ),
        },
        {
            "reference_id": "EC2-AN-101",
            "title": "Ancrage droit HA20, C30/37, bonnes conditions d'adherence",
            "normative_scope": ["EN 1992-1-1 §8.4", "EN 1992-1-1 §8.7"],
            "country_scope": [COUNTRY],
            "source_type": "manual_reference",
            "source_document": _source(
                "equilibre de la barre: traction sur la section contre "
                "adherence sur la surface laterale"
            ),
            "harness": "ec2.anchorage",
            "input_dataset": {
                "country": COUNTRY, "as_of": AS_OF, "strict_ndp": False,
                "concrete_grade": "C30/37", "steel_grade": "B500B",
                "phi": {"value": 20.0, "unit": "mm"},
                "bond_condition": "good", "in_tension": True,
            },
            "expected_outputs": anchorage_mm(20.0, FYK / GAMMA_S, 1.0),
            "tolerance_rules": [{"output": "*", "rel": 1e-9}],
            "notes": "Tous les coefficients du Tableau 8.2 valent 1,0.",
        },
        {
            "reference_id": "EC2-AN-102",
            "title": "Ancrage HA16 en mauvaises conditions d'adherence",
            "normative_scope": ["EN 1992-1-1 §8.4.2"],
            "country_scope": [COUNTRY],
            "source_type": "manual_reference",
            "source_document": _source("meme equilibre, eta_1 = 0,7"),
            "harness": "ec2.anchorage",
            "input_dataset": {
                "country": COUNTRY, "as_of": AS_OF, "strict_ndp": False,
                "concrete_grade": "C30/37", "steel_grade": "B500B",
                "phi": {"value": 16.0, "unit": "mm"},
                "bond_condition": "poor", "in_tension": True,
            },
            "expected_outputs": anchorage_mm(16.0, FYK / GAMMA_S, 0.7),
            "tolerance_rules": [{"output": "*", "rel": 1e-9}],
            "notes": (
                "eta_1 = 0,7 coute 1/0,7 = 43 % de longueur en plus, a section "
                "et beton identiques."
            ),
        },
    ]
    return cases


def main(argv: list[str]) -> int:
    cases = build()
    payload = {
        "_comment": (
            "Cas de reference a valeurs attendues DERIVEES INDEPENDAMMENT. "
            "Regenerer avec scripts/generate_shear_anchorage_references.py. "
            "Ne jamais recopier une valeur depuis une sortie du moteur: le cas "
            "attesterait alors que le moteur est d'accord avec lui-meme."
        ),
        "cases": cases,
    }
    out = LIBRARY / "ec2_beam_shear_anchorage.json"
    if "--dry-run" not in argv:
        out.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    for c in cases:
        print(f"{c['reference_id']}  {c['title'][:62]}")
        for k, v in c["expected_outputs"].items():
            print(f"     {k:28s} {v:14.6f}")
    print(f"\n{len(cases)} cas ecrits dans {out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
