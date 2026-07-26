"""Determinism and non-regression — cahier des charges sections 8.2 and 11.

    "Le meme projet recalcule donne un resultat bit-a-bit identique."

    "Tests de non-regression (« golden tests ») : un resultat valide ne change
     jamais silencieusement ; tout changement de valeur exige un changement de
     version majeure et une note de release."

The frozen values below were produced by eurostruct-engine 0.1.0 and
hand-verified in ``test_ec2_beam_flexure.py::test_hand_calculation_case``.
Comparison is exact: ``==`` on floats, not ``approx``. If one of these changes,
that is not a test to relax — it is a MAJOR version bump plus a release note
naming every value that moved. See ``docs/VALIDATION.md``.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap

import pytest

from datetime import date

from eurostruct_engine.ec2 import RectangularSection, design_flexure
from eurostruct_engine.materials import concrete, reinforcement
from eurostruct_engine.materials.reinforcement import bars_area
from eurostruct_engine.units import Q_
from eurostruct_engine.version import ENGINE_VERSION

#: Frozen result of the reference case, eurostruct-engine 0.1.0.
#: b=300, h=600, d=550 mm, C30/37, B500B, M_Ed=250 kN.m, BE parameter set,
#: reinforcement provided 4 HA20.
GOLDEN_0_1_0 = {
    "mu": 0.1377410468319559,
    "xi": 0.18601727990998934,
    "xi_lim": 0.44800000000000006,
    "eps_s": 0.015315456293595906,
    "As_strength_mm2": 1129.4969236134557,
    "As_min_mm2": 248.51696759748907,
    "As_max_mm2": 7200.0,
    "As_required_mm2": 1129.4969236134557,
    "As_provided_mm2": 1256.6370614359173,
    "x_mm": 102.30950395049413,
    "z_mm": 509.0761984198023,
    "M_Rd_kNm": 275.62403730974995,
    "utilisation": 0.9070326464997198,
}


def _reference_case(params):
    return design_flexure(
        section=RectangularSection(b=Q_(300, "mm"), h=Q_(600, "mm"), d=Q_(550, "mm")),
        concrete=concrete("C30/37"),
        steel=reinforcement("B500B"),
        M_Ed=Q_(250, "kN*m"),
        params=params,
        element="P1",
        A_s_provided=bars_area(4, 20),
    )


@pytest.mark.golden
def test_reference_case_values_are_frozen(params_be) -> None:
    """Exact equality. Any drift is a deliberate, versioned change."""
    got = _reference_case(params_be).to_dict()
    drift = {
        k: (expected, got[k])
        for k, expected in GOLDEN_0_1_0.items()
        if got[k] != expected
    }
    assert not drift, (
        "Un resultat fige a change:\n"
        + "\n".join(f"  {k}: attendu {e!r}, obtenu {g!r}" for k, (e, g) in drift.items())
        + "\n\nSi ce changement est voulu: incrementer la version MAJEURE du "
        "moteur et documenter chaque valeur modifiee dans la note de release. "
        "Ne pas relacher ce test."
    )


@pytest.mark.golden
def test_engine_version_is_recorded_in_the_result(params_be) -> None:
    """A result that cannot say which engine produced it is not defensible."""
    assert _reference_case(params_be).engine_version == ENGINE_VERSION


def test_recalculating_gives_an_identical_serialisation(params_be) -> None:
    a = _reference_case(params_be).to_dict()
    b = _reference_case(params_be).to_dict()
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_determinism_across_processes() -> None:
    """Different interpreter, different hash seed, identical bytes.

    Runs the reference case in two subprocesses with different
    ``PYTHONHASHSEED`` values. A result that depended on set or dict iteration
    order would diverge here and nowhere else.
    """
    script = textwrap.dedent(
        """
        import json
        from datetime import date

        from eurostruct_engine.ec2 import RectangularSection, design_flexure
        from eurostruct_engine.materials import concrete, reinforcement
        from eurostruct_engine.materials.reinforcement import bars_area
        from eurostruct_engine.ndp import load_parameter_set
        from eurostruct_engine.units import Q_

        params = load_parameter_set("BE", strict=False, as_of=date(2026, 7, 26))
        r = design_flexure(
            section=RectangularSection(b=Q_(300, "mm"), h=Q_(600, "mm"), d=Q_(550, "mm")),
            concrete=concrete("C30/37"), steel=reinforcement("B500B"),
            M_Ed=Q_(250, "kN*m"), params=params,
            element="P1", A_s_provided=bars_area(4, 20),
        )
        print(json.dumps(r.to_dict(), sort_keys=True))
        """
    )

    def run(seed: str) -> str:
        out = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, check=True,
            env={"PYTHONHASHSEED": seed, "PATH": "/usr/bin:/bin"},
        )
        return out.stdout

    assert run("0") == run("12345")


@pytest.mark.golden
def test_journal_structure_is_stable(params_be) -> None:
    """The note de calcul walks these symbols in this order."""
    symbols = _reference_case(params_be).journal.symbols()
    assert symbols == [
        "b", "h", "d", "f_ck", "f_yk", "M_Ed",
        "EN 1992-1-1:gamma_C_persistent", "EN 1992-1-1:gamma_S_persistent",
        "EN 1992-1-1:alpha_cc",
        "EN 1992-1-1:k1_redistribution", "EN 1992-1-1:k2_redistribution",
        "EN 1992-1-1:As_min_coeff", "EN 1992-1-1:As_min_floor",
        "EN 1992-1-1:As_max_ratio",
        "f_cd", "f_yd", "eps_yd", "lambda", "eta",
        "mu", "xi_lim", "mu_lim", "xi", "x", "z",
        "A_s_calc", "eps_s", "f_ctm", "A_s_min", "A_s_max", "A_s_req",
        "A_s_prov", "chk_x", "chk_z", "chk_eps_s", "chk_M_Rd",
    ]


@pytest.mark.golden
def test_numeric_application_strings_are_frozen(params_be) -> None:
    """These strings are printed verbatim in the PDF; they must not drift."""
    j = _reference_case(params_be).journal
    assert j.get("f_cd").numeric == "1 · 30 MPa / 1.5"
    assert j.get("f_yd").numeric == "500 MPa / 1.15"
    assert j.get("mu").numeric == "250 kN·m / (300 mm · 550 mm² · 1 · 20 MPa)"
    assert j.get("xi_lim").numeric == "(1 − 0.44) / 1.25"


@pytest.mark.golden
def test_clause_citations_are_frozen(params_be) -> None:
    """Section 8.1: each number cites the clause it comes from."""
    j = _reference_case(params_be).journal
    assert j.get("f_cd").clause.cite() == "EN 1992-1-1 §3.1.6(1)P, eq. (3.15)"
    assert j.get("f_yd").clause.cite() == "EN 1992-1-1 §3.2.7(2), eq. (3.14)"
    assert j.get("A_s_min").clause.cite() == "EN 1992-1-1 §9.2.1.1(1), eq. (9.1N)"
    assert j.get("xi_lim").clause.cite() == "EN 1992-1-1 §5.5(4), eq. (5.10a)"
    # The National Annex qualification travels with the parameter.
    assert "ANB" in j.get("EN 1992-1-1:alpha_cc").clause.cite()
