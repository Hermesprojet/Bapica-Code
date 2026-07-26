"""Material properties against EN 1992-1-1 Table 3.1.

Table 3.1 is a *printed* table: every entry is rounded to the precision shown
(one decimal for the strengths in MPa, whole numbers for Ecm in GPa), and the
derived rows are computed from the already-rounded fctm. This module therefore
compares against the table with an absolute tolerance matching that printing
precision, rather than a relative tolerance, which would be the wrong
instrument: at C12/15 the rounding of fctm from 1,572 to 1,6 is a 1,8 %
relative difference and says nothing about the formula being wrong.

The formulas themselves are checked exactly, separately.
"""

from __future__ import annotations

import pytest

from eurostruct_engine.exceptions import OutOfValidationDomain
from eurostruct_engine.materials import concrete, reinforcement
from eurostruct_engine.materials.reinforcement import bar_area, bars_area
from eurostruct_engine.units import Q_

# grade -> (fcm, fctm, fctk_0.05, fctk_0.95, Ecm) as printed in Table 3.1
TABLE_3_1 = {
    "C12/15": (20.0, 1.6, 1.1, 2.0, 27.0),
    "C16/20": (24.0, 1.9, 1.3, 2.5, 29.0),
    "C20/25": (28.0, 2.2, 1.5, 2.9, 30.0),
    "C25/30": (33.0, 2.6, 1.8, 3.3, 31.0),
    "C30/37": (38.0, 2.9, 2.0, 3.8, 33.0),
    "C35/45": (43.0, 3.2, 2.2, 4.2, 34.0),
    "C40/50": (48.0, 3.5, 2.5, 4.6, 35.0),
    "C45/55": (53.0, 3.8, 2.7, 4.9, 36.0),
    "C50/60": (58.0, 4.1, 2.9, 5.3, 37.0),
}

#: Half of the last printed digit of the strength columns.
TOL_STRENGTH = 0.05
#: fctk,0,05 and fctk,0,95 are tabulated from the rounded fctm, so their
#: rounding error can accumulate to just over half a digit.
TOL_DERIVED = 0.06
#: Ecm is printed as a whole number of GPa.
TOL_ECM = 0.5


@pytest.mark.reference
@pytest.mark.parametrize("grade", sorted(TABLE_3_1))
def test_concrete_matches_table_3_1(grade: str) -> None:
    fcm, fctm, fctk05, fctk95, ecm = TABLE_3_1[grade]
    c = concrete(grade)
    assert c.fcm.to("MPa").magnitude == pytest.approx(fcm, abs=TOL_STRENGTH)
    assert c.fctm.to("MPa").magnitude == pytest.approx(fctm, abs=TOL_STRENGTH)
    assert c.fctk_005.to("MPa").magnitude == pytest.approx(fctk05, abs=TOL_DERIVED)
    assert c.fctk_095.to("MPa").magnitude == pytest.approx(fctk95, abs=TOL_DERIVED)
    assert c.Ecm.to("GPa").magnitude == pytest.approx(ecm, abs=TOL_ECM)


def test_fctk_are_exact_fractions_of_fctm() -> None:
    """Table 3.1 defines fctk,0,05 = 0,7 fctm and fctk,0,95 = 1,3 fctm."""
    for grade in TABLE_3_1:
        c = concrete(grade)
        assert c.fctk_005.to("MPa").magnitude == pytest.approx(
            0.7 * c.fctm.to("MPa").magnitude, rel=1e-12
        )
        assert c.fctk_095.to("MPa").magnitude == pytest.approx(
            1.3 * c.fctm.to("MPa").magnitude, rel=1e-12
        )


def test_stress_block_parameters_below_c50() -> None:
    """§3.1.7(3): lambda = 0,8 and eta = 1,0 up to C50/60."""
    for grade in TABLE_3_1:
        c = concrete(grade)
        assert c.lambda_ == 0.8
        assert c.eta == 1.0
        assert c.eps_cu3 == pytest.approx(3.5e-3)
        assert c.eps_cu2 == pytest.approx(3.5e-3)
        assert c.eps_c2 == pytest.approx(2.0e-3)


def test_stress_block_parameters_above_c50() -> None:
    """§3.1.7(3) eq. (3.20) and (3.22) for high strength concrete."""
    c = concrete("C90/105")
    assert c.lambda_ == pytest.approx(0.8 - 40.0 / 400.0)
    assert c.eta == pytest.approx(1.0 - 40.0 / 200.0)
    # eps_cu3 at fck = 90 MPa reduces to 2,6 permille.
    assert c.eps_cu3 == pytest.approx(2.6e-3)


def test_design_strengths_require_explicit_national_parameters() -> None:
    """fcd and fyd cannot be obtained without passing the NDPs explicitly."""
    c = concrete("C30/37")
    assert c.fcd(alpha_cc=1.0, gamma_C=1.5).to("MPa").magnitude == pytest.approx(20.0)
    s = reinforcement("B500B")
    assert s.fyd(gamma_S=1.15).to("MPa").magnitude == pytest.approx(500.0 / 1.15)
    assert s.eps_yd(gamma_S=1.15) == pytest.approx(500.0 / 1.15 / 200_000.0)


def test_unknown_grades_are_refused() -> None:
    with pytest.raises(OutOfValidationDomain):
        concrete("C33/40")
    with pytest.raises(OutOfValidationDomain):
        reinforcement("B550X")


def test_concrete_outside_en_range_is_refused() -> None:
    from eurostruct_engine.materials.concrete import Concrete

    with pytest.raises(OutOfValidationDomain):
        Concrete(name="C100", fck=Q_(100, "MPa"))


def test_bar_areas() -> None:
    """Nominal areas, cross-checked against the values used in practice."""
    assert bar_area(20).to("mm**2").magnitude == pytest.approx(314.159, abs=1e-3)
    assert bar_area(12).to("mm**2").magnitude == pytest.approx(113.097, abs=1e-3)
    assert bars_area(4, 20).to("mm**2").magnitude == pytest.approx(1256.637, abs=1e-3)
