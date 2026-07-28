#!/usr/bin/env python3
"""Derive the expected values of the §7.2 / §7.3 reference cases.

Same discipline as ``generate_shear_anchorage_references.py``: every figure is
produced here by a route the engine does not take, so that agreement means
something.

* the **cracked neutral axis** comes from bisection on the equilibrium residual
  ``b x²/2 − α_e A_s (d − x)``. The engine solves the quadratic in closed form;
  a sign slip in that root would not survive a comparison with bisection.
* the **uncracked** section used for the §7.1(2) verdict is assembled about its
  own centroid from first principles, not by any shortcut.
* ``E_cm`` and ``f_ctm`` are recomputed from Table 3.1 rather than read off the
  material objects, so a wrong constant in the material layer would show up as
  a reference failure and not as two modules agreeing on the same error.
* ``s_r,max`` and ``w_k`` are assembled term by term from (7.11) and (7.8).

Three cases, chosen to reach three different branches:

``EC2-SLS-101``   nominal beam, XC3 — equation (7.11), the (7.9) bracket governs
``EC2-SLS-102``   lightly loaded — the ``0,6 σ_s/E_s`` floor governs, section
                  uncracked, so ``is_cracked`` must come back 0
``EC2-SLS-103``   widely spaced bars — equation (7.14) instead of (7.11)

Belgium is used throughout, and the choice is forced rather than preferred.
France cannot run this module at all: NF EN 1992-1-1/NA §7.3.4(3) makes ``k3``
a formula in the cover — ``3,4 (25/c)^{2/3}`` beyond 25 mm — which the scalar
parameter model cannot hold, so the preflight refuses. NBN EN 1992-1-1 ANB
§7.3.4(3) declares the recommended 3,4 and 0,425 normative, which the model can.

These cases were originally built on France and went red the day the French
annex was actually read. That is the reference suite doing its job: it caught a
change in the NORMATIVE data, not in the arithmetic.

``w_max`` is pinned here only as the value the data set carries. Both annexes
replace Table 7.1N — Belgium with 7.1N-ANB, France with 7.1NF — and neither
table's cells extract from the copies in hand. The number these cases lock is
therefore the EN table's, and it is not evidence about either country.

Run from engine/:
    python scripts/generate_serviceability_references.py [--dry-run]
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
LIBRARY = HERE / "src/eurostruct_engine/reference/library"

COUNTRY = "BE"
AS_OF = "2026-07-26"

FCK, FYK, ES = 30.0, 500.0, 200000.0
#: §7.3.4(2)-(3) — fixed in the EN text, not nationally determined.
K_T = 0.4
K1_BOND, K2_BENDING = 0.8, 0.5
#: §7.3.4(3) and §7.2 — nationally determined; the values below are the EN
#: recommendations, which is what the Belgian ANB declares normative.
K3_CRACK, K4_CRACK = 3.4, 0.425
K1_STRESS, K3_STEEL = 0.6, 0.8


def E_cm(fck: float) -> float:
    """Tab. 3.1: E_cm = 22 (f_cm/10)^0,3 in GPa, f_cm = f_ck + 8."""
    return 22000.0 * ((fck + 8.0) / 10.0) ** 0.3


def f_ctm(fck: float) -> float:
    """Tab. 3.1, fck <= 50 MPa."""
    return 0.30 * fck ** (2.0 / 3.0)


def neutral_axis(b: float, d: float, A_s: float, alpha_e: float) -> float:
    """Bisection on b x²/2 − α_e A_s (d − x) = 0, bracketed in (0, d).

    Deliberately not the closed-form root: two routes to the same number.
    """
    def residual(x: float) -> float:
        return b * x * x / 2.0 - alpha_e * A_s * (d - x)

    lo, hi = 1e-12, d
    for _ in range(400):
        mid = 0.5 * (lo + hi)
        if residual(mid) > 0.0:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def cracked(b: float, d: float, A_s: float, alpha_e: float, M: float
            ) -> tuple[float, float, float, float]:
    """(x, I, sigma_c, sigma_s) — M in N·mm."""
    x = neutral_axis(b, d, A_s, alpha_e)
    I = b * x**3 / 3.0 + alpha_e * A_s * (d - x) ** 2
    return x, I, M * x / I, alpha_e * M * (d - x) / I


def uncracked_tension(b: float, h: float, d: float, A_s: float,
                      alpha_e: float, M: float) -> float:
    """Extreme tensile fibre stress on the uncracked transformed section."""
    A_t = b * h + (alpha_e - 1.0) * A_s
    x_I = (b * h * h / 2.0 + (alpha_e - 1.0) * A_s * d) / A_t
    I_I = (
        b * h**3 / 12.0
        + b * h * (x_I - h / 2.0) ** 2
        + (alpha_e - 1.0) * A_s * (d - x_I) ** 2
    )
    return M * (h - x_I) / I_I


def solve(*, b: float, h: float, d: float, A_s: float, M_qp: float, M_char: float,
          phi_creep: float, phi_bar: float, cover: float, spacing: float,
          w_max: float) -> dict[str, float]:
    """Everything the harness publishes, by the independent route."""
    ecm = E_cm(FCK)
    fctm = f_ctm(FCK)
    ae_short = ES / ecm
    ae_long = ES / (ecm / (1.0 + phi_creep))

    x_qp, I_qp, _, ss_qp = cracked(b, d, A_s, ae_long, M_qp)
    x_ch, _, sc_ch, ss_ch = cracked(b, d, A_s, ae_short, M_char)

    h_c_ef = min(2.5 * (h - d), (h - x_qp) / 3.0, h / 2.0)
    rho = A_s / (b * h_c_ef)

    bracket = ss_qp - K_T * (fctm / rho) * (1.0 + ae_short * rho)
    eps = max(bracket / ES, 0.6 * ss_qp / ES)

    if spacing > 5.0 * (cover + phi_bar / 2.0):
        s_r_max = 1.3 * (h - x_qp)
    else:
        s_r_max = K3_CRACK * cover + K1_BOND * K2_BENDING * K4_CRACK * phi_bar / rho

    w_k = s_r_max * eps
    sigma_c_limit = K1_STRESS * FCK
    is_cracked = uncracked_tension(b, h, d, A_s, ae_long, M_qp) > fctm

    return {
        "alpha_e_short": ae_short,
        "alpha_e_long": ae_long,
        "x_qp_mm": x_qp,
        "I_qp_mm4": I_qp,
        "sigma_s_qp_MPa": ss_qp,
        "x_char_mm": x_ch,
        "sigma_c_char_MPa": sc_ch,
        "sigma_s_char_MPa": ss_ch,
        "h_c_ef_mm": h_c_ef,
        "rho_p_eff": rho,
        "eps_diff": eps,
        "s_r_max_mm": s_r_max,
        "w_k_mm": w_k,
        "w_max_mm": w_max,
        "sigma_c_limit_MPa": sigma_c_limit,
        "is_cracked": 1.0 if is_cracked else 0.0,
        "utilisation": max(
            w_k / w_max, sc_ch / sigma_c_limit, ss_ch / (K3_STEEL * FYK)
        ),
    }


def _source(method: str) -> dict[str, str]:
    return {
        "title": "Resolution independante — " + method,
        "publisher": "EUROSTRUCT — scripts/generate_serviceability_references.py",
        "edition": "1",
        "locator": "",
        "notes": (
            "Valeurs attendues obtenues par une voie DISTINCTE de celle du "
            "moteur: axe neutre par dichotomie sur le residu d'equilibre, "
            "E_cm et f_ctm recalcules depuis le Tableau 3.1. L'accord des deux "
            "atteste l'algebre; il ne remplace pas un exemple resolu publie, et "
            "les cas 'official_worked_example' de planned_coverage.json "
            "restent des lacunes ouvertes."
        ),
    }


def build() -> list[dict]:
    b, h, d = 300.0, 600.0, 550.0
    A_s = 4 * math.pi * 20.0**2 / 4.0

    common = {
        "country": COUNTRY, "as_of": AS_OF, "strict_ndp": False,
        "b": {"value": b, "unit": "mm"},
        "h": {"value": h, "unit": "mm"},
        "d": {"value": d, "unit": "mm"},
        "A_s": {"value": A_s, "unit": "mm**2"},
        "concrete_grade": "C30/37", "steel_grade": "B500B",
        "phi_creep": 2.0,
    }
    detail = {
        "phi": {"value": 20.0, "unit": "mm"},
        "cover": {"value": 40.0, "unit": "mm"},
        "bar_spacing": {"value": 60.0, "unit": "mm"},
    }
    wide_detail = dict(detail, bar_spacing={"value": 400.0, "unit": "mm"})

    nominal = solve(
        b=b, h=h, d=d, A_s=A_s, M_qp=120e6, M_char=180e6, phi_creep=2.0,
        phi_bar=20.0, cover=40.0, spacing=60.0, w_max=0.3,
    )
    light = solve(
        b=b, h=h, d=d, A_s=A_s, M_qp=30e6, M_char=45e6, phi_creep=2.0,
        phi_bar=20.0, cover=40.0, spacing=60.0, w_max=0.3,
    )
    wide = solve(
        b=b, h=h, d=d, A_s=A_s, M_qp=120e6, M_char=180e6, phi_creep=2.0,
        phi_bar=20.0, cover=40.0, spacing=400.0, w_max=0.3,
    )

    return [
        {
            "reference_id": "EC2-SLS-101",
            "title": (
                "ELS fissuration et contraintes — 300x600 mm, d=550, 4 HA20, "
                "C30/37, XC3, M_qp=120 kN·m, M_car=180 kN·m, phi=2,0"
            ),
            "normative_scope": [
                "EN 1992-1-1 §7.2", "EN 1992-1-1 §7.3.2", "EN 1992-1-1 §7.3.4",
            ],
            "country_scope": [COUNTRY],
            "source_type": "manual_reference",
            "source_document": _source(
                "axe neutre fissure par dichotomie, (7.9) et (7.11) assemblees "
                "terme a terme"
            ),
            "harness": "ec2.serviceability",
            "input_dataset": {
                **common,
                "M_qp": {"value": 120.0, "unit": "kN*m"},
                "M_char": {"value": 180.0, "unit": "kN*m"},
                "detail": detail,
                "exposure_class": "XC3",
            },
            "expected_outputs": nominal,
            "tolerance_rules": [{"output": "*", "rel": 1e-9}],
            "notes": (
                "Cas nominal: section fissuree, le crochet de (7.9) gouverne "
                "devant le plancher 0,6 sigma_s/E_s, et l'espacement des "
                "barres autorise la formule (7.11). C'est la contrainte du "
                "beton sous combinaison caracteristique qui gouverne le taux "
                "de travail, pas l'ouverture de fissure."
            ),
        },
        {
            "reference_id": "EC2-SLS-102",
            "title": (
                "ELS — section peu chargee: plancher de (7.9) et section non "
                "fissuree, M_qp=30 kN·m"
            ),
            "normative_scope": ["EN 1992-1-1 §7.1(2)", "EN 1992-1-1 §7.3.4(2)"],
            "country_scope": [COUNTRY],
            "source_type": "manual_reference",
            "source_document": _source(
                "meme dichotomie; le plancher 0,6 sigma_s/E_s est evalue a "
                "part et compare, et la contrainte de traction non fissuree "
                "est assemblee sur la section homogeneisee complete"
            ),
            "harness": "ec2.serviceability",
            "input_dataset": {
                **common,
                "M_qp": {"value": 30.0, "unit": "kN*m"},
                "M_char": {"value": 45.0, "unit": "kN*m"},
                "detail": detail,
                "exposure_class": "XC3",
            },
            "expected_outputs": light,
            "tolerance_rules": [{"output": "*", "rel": 1e-9}],
            "notes": (
                "Deux branches a la fois: le crochet de (7.9) devient negatif "
                "et le plancher 0,6 sigma_s/E_s gouverne — sans lui w_k "
                "sortirait negatif; et sigma_ct n'atteint pas f_ctm, donc "
                "is_cracked doit revenir a 0. L'ouverture de fissure reste "
                "calculee, ce qui est securitaire, mais elle ne decrit aucune "
                "fissure reelle."
            ),
        },
        {
            "reference_id": "EC2-SLS-103",
            "title": (
                "ELS — barres largement espacees: formule (7.14) au lieu de "
                "(7.11), espacement 400 mm"
            ),
            "normative_scope": ["EN 1992-1-1 §7.3.4(3)"],
            "country_scope": [COUNTRY],
            "source_type": "manual_reference",
            "source_document": _source("s_r,max = 1,3 (h - x) evalue separement"),
            "harness": "ec2.serviceability",
            "input_dataset": {
                **common,
                "M_qp": {"value": 120.0, "unit": "kN*m"},
                "M_char": {"value": 180.0, "unit": "kN*m"},
                "detail": wide_detail,
                "exposure_class": "XC3",
            },
            "expected_outputs": wide,
            "tolerance_rules": [{"output": "*", "rel": 1e-9}],
            "notes": (
                "400 mm > 5(40 + 20/2) = 250 mm: la formule (7.11) ne decrit "
                "plus le faisceau de fissures et (7.14) prend le relais. Toutes "
                "les autres sorties sont identiques a EC2-SLS-101, ce qui isole "
                "l'effet de la bascule."
            ),
        },
    ]


def main(argv: list[str]) -> int:
    cases = build()
    payload = {
        "_comment": (
            "Cas de reference a valeurs attendues DERIVEES INDEPENDAMMENT. "
            "Regenerer avec scripts/generate_serviceability_references.py. "
            "Ne jamais recopier une valeur depuis une sortie du moteur: le cas "
            "attesterait alors que le moteur est d'accord avec lui-meme."
        ),
        "cases": cases,
    }
    out = LIBRARY / "ec2_serviceability.json"
    if "--dry-run" not in argv:
        out.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    for c in cases:
        print(f"{c['reference_id']}  {c['title'][:64]}")
        for k, v in c["expected_outputs"].items():
            print(f"     {k:22s} {v:18.8f}")
        print()
    print(f"{len(cases)} cas ecrits dans {out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
