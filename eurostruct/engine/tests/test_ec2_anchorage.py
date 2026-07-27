"""EN 1992-1-1 §8.4 and §8.7 — anchorage and lap lengths.

The independent check here is :func:`test_bond_develops_the_bar_force`, which
derives ``l_b,rqd`` from force equilibrium on the bar — the tension it carries
against the bond stress on its perimeter — instead of applying eq. (8.3).
"""

from __future__ import annotations

import math

import pytest

from eurostruct_engine.basis import DesignSituation
from eurostruct_engine.ec2 import (
    AnchorageCoefficients,
    BondCondition,
    design_anchorage,
)
from eurostruct_engine.ec2.anchorage import EC2_11, required_parameters
from eurostruct_engine.exceptions import InconsistentInput, OutOfValidationDomain
from eurostruct_engine.materials import concrete, reinforcement
from eurostruct_engine.units import Q_


def _anchor(params, phi_mm=20.0, **kw):
    defaults = dict(
        concrete=concrete("C30/37"),
        steel=reinforcement("B500B"),
        phi=Q_(phi_mm, "mm"),
        params=params,
        element="P1",
    )
    defaults.update(kw)
    return design_anchorage(**defaults)


# ---------------------------------------------------------------------------
# Hand calculation
# ---------------------------------------------------------------------------
@pytest.mark.reference
def test_hand_calculation_case(params_be) -> None:
    """HA20, C30/37, B500B, bonnes conditions d'adherence, coefficients a 1,0.

        f_ctm       = 0,30 × 30^(2/3)             = 2,89647 MPa
        f_ctk;0,05  = 0,7 × 2,89647               = 2,02753 MPa
        f_ctd       = 1,0 × 2,02753 / 1,5         = 1,35169 MPa
        f_bd        = 2,25 × 1,0 × 1,0 × 1,35169  = 3,04130 MPa
        sigma_sd    = 500 / 1,15                  = 434,7826 MPa
        l_b,rqd     = (20/4) × 434,7826 / 3,04130 = 714,80 mm

    alpha_ct vaut 1,0 en Belgique — c'est le coefficient de TRACTION, que
    l'ANB ne rend pas conditionnel, contrairement a alpha_cc.
    """
    r = _anchor(params_be)
    assert r.f_bd.to("MPa").magnitude == pytest.approx(3.04130, abs=5e-5)
    assert r.l_b_rqd.to("mm").magnitude == pytest.approx(714.80, abs=5e-2)
    assert r.l_bd.to("mm").magnitude == pytest.approx(714.80, abs=5e-2)
    assert not r.l_b_min_governs


# ---------------------------------------------------------------------------
# Independent verification
# ---------------------------------------------------------------------------
@pytest.mark.reference
@pytest.mark.parametrize("phi_mm", [8.0, 12.0, 20.0, 32.0])
def test_bond_develops_the_bar_force(params_be, phi_mm: float) -> None:
    """l_b,rqd from equilibrium on the bar, not from eq. (8.3).

    The bar carries ``sigma_sd × pi phi²/4``. The bond delivers ``f_bd`` over
    the lateral surface ``pi phi l``. Equating the two gives the length, and
    the ``phi/4`` of eq. (8.3) is exactly the ratio of area to perimeter — a
    simplification this test does not perform.
    """
    r = _anchor(params_be, phi_mm=phi_mm)

    force_N = float(r.sigma_sd.to("MPa").magnitude) * math.pi * phi_mm**2 / 4.0
    bond_per_mm = float(r.f_bd.to("MPa").magnitude) * math.pi * phi_mm
    expected_mm = force_N / bond_per_mm

    assert r.l_b_rqd.to("mm").magnitude == pytest.approx(expected_mm, rel=1e-12)


# ---------------------------------------------------------------------------
# The bond stress
# ---------------------------------------------------------------------------
def test_poor_bond_conditions_lengthen_the_anchorage(params_be) -> None:
    """eta_1 = 0,7 costs 1/0,7 = 43 % more length, all else equal."""
    good = _anchor(params_be, bond_condition=BondCondition.GOOD)
    poor = _anchor(params_be, bond_condition=BondCondition.POOR)
    assert poor.f_bd.magnitude == pytest.approx(0.7 * good.f_bd.magnitude, rel=1e-12)
    assert poor.l_b_rqd.magnitude == pytest.approx(
        good.l_b_rqd.magnitude / 0.7, rel=1e-12
    )


def test_an_unknown_bond_condition_is_refused(params_be) -> None:
    with pytest.raises(InconsistentInput, match="condition d'adherence"):
        _anchor(params_be, bond_condition="moyenne")


def test_bond_uses_the_tensile_coefficient_not_the_compression_one(params_be) -> None:
    """alpha_ct, not alpha_cc: a different value for a different quantity.

    In Belgium alpha_cc is conditional (0,85 / 1,0) and alpha_ct is a plain
    1,0. Reading the wrong one here would be silent and wrong.
    """
    r = _anchor(params_be)
    symbols = r.journal.symbols()
    assert f"{EC2_11}:alpha_ct" in symbols
    assert f"{EC2_11}:alpha_cc" not in symbols


# ---------------------------------------------------------------------------
# Bar stress, §8.4.3
# ---------------------------------------------------------------------------
def test_an_over_reinforced_section_needs_a_shorter_anchorage(params_be) -> None:
    """§8.4.3: sigma_sd = f_yd A_s,req/A_s,prov, not f_yd unconditionally."""
    full = _anchor(params_be)
    half = _anchor(
        params_be,
        A_s_required=Q_(600, "mm**2"),
        A_s_provided=Q_(1200, "mm**2"),
    )
    assert half.sigma_sd.magnitude == pytest.approx(0.5 * full.sigma_sd.magnitude)
    assert half.l_b_rqd.magnitude == pytest.approx(0.5 * full.l_b_rqd.magnitude)


def test_more_steel_required_than_provided_is_refused(params_be) -> None:
    with pytest.raises(InconsistentInput, match="n'est pas ferraillee"):
        _anchor(params_be, A_s_required=Q_(1200, "mm**2"),
                A_s_provided=Q_(600, "mm**2"))


def test_an_explicit_stress_overrides_everything(params_be) -> None:
    r = _anchor(params_be, sigma_sd=Q_(200, "MPa"))
    assert r.sigma_sd.to("MPa").magnitude == pytest.approx(200.0)
    assert "declaree par l'ingenieur" in r.journal.get("sigma_sd").numeric


# ---------------------------------------------------------------------------
# Table 8.2 coefficients
# ---------------------------------------------------------------------------
def test_coefficients_default_to_the_conservative_reading() -> None:
    c = AnchorageCoefficients()
    assert (c.alpha_1, c.alpha_2, c.alpha_3, c.alpha_4, c.alpha_5, c.alpha_6) == (
        1.0, 1.0, 1.0, 1.0, 1.0, 1.0
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [("alpha_1", 0.6), ("alpha_2", 1.1), ("alpha_5", 0.5), ("alpha_6", 1.6),
     ("alpha_6", 0.9)],
)
def test_a_coefficient_outside_table_8_2_is_refused(field: str, value: float) -> None:
    with pytest.raises(InconsistentInput, match="Tableau 8.2/8.3"):
        AnchorageCoefficients(**{field: value})


def test_the_confinement_product_has_a_floor() -> None:
    """§8.4.4(2): alpha_2 alpha_3 alpha_5 >= 0,7 — the effects do not stack."""
    AnchorageCoefficients(alpha_2=0.9, alpha_3=0.9, alpha_5=0.9)   # 0,729 : ok
    with pytest.raises(InconsistentInput, match="plancher"):
        AnchorageCoefficients(alpha_2=0.8, alpha_3=0.8, alpha_5=0.8)  # 0,512


def test_a_hook_does_not_anchor_a_bar_in_compression(params_be) -> None:
    with pytest.raises(InconsistentInput, match="compression"):
        _anchor(params_be, in_tension=False,
                coefficients=AnchorageCoefficients(alpha_1=0.7))


# ---------------------------------------------------------------------------
# Floors, §8.4.4(1) and §8.7.3(1)
# ---------------------------------------------------------------------------
def test_a_lightly_stressed_bar_falls_back_on_the_minimum(params_be) -> None:
    r = _anchor(params_be, phi_mm=8.0, sigma_sd=Q_(20, "MPa"))
    assert r.l_b_min_governs
    # max(0,3 l_b,rqd ; 10 phi ; 100 mm) — ici le plancher absolu.
    assert r.l_b_min.to("mm").magnitude == pytest.approx(100.0)
    assert r.l_bd == r.l_b_min


def test_compression_has_a_higher_floor_than_tension(params_be) -> None:
    """0,6 l_b,rqd against 0,3: a compressed bar may not be anchored as short."""
    t = _anchor(params_be, in_tension=True)
    c = _anchor(params_be, in_tension=False)
    assert c.l_b_min.magnitude == pytest.approx(2.0 * t.l_b_min.magnitude)


def test_the_lap_floor_is_higher_than_the_anchorage_floor(params_be) -> None:
    r = _anchor(params_be, phi_mm=8.0, sigma_sd=Q_(20, "MPa"))
    assert r.l_0_min.to("mm").magnitude == pytest.approx(200.0)
    assert r.l_0 == r.l_0_min


def test_lapping_more_bars_at_one_section_lengthens_the_lap(params_be) -> None:
    """Table 8.3: alpha_6 = 1,4 at 50 % lapped."""
    quarter = _anchor(params_be)
    half = _anchor(params_be, coefficients=AnchorageCoefficients(alpha_6=1.4))
    assert half.l_0.magnitude == pytest.approx(1.4 * quarter.l_0.magnitude, rel=1e-12)


# ---------------------------------------------------------------------------
# Refusals
# ---------------------------------------------------------------------------
def test_a_bar_larger_than_32_mm_is_refused(params_be) -> None:
    with pytest.raises(OutOfValidationDomain) as e:
        _anchor(params_be, phi_mm=40.0)
    assert e.value.what == "large_diameter_bar"


def test_high_strength_concrete_is_refused(params_be) -> None:
    with pytest.raises(OutOfValidationDomain) as e:
        _anchor(params_be, concrete=concrete("C60/75"))
    assert e.value.what == "high_strength_concrete"


def test_a_negative_diameter_is_refused(params_be) -> None:
    with pytest.raises(InconsistentInput):
        _anchor(params_be, phi_mm=-20.0)


def test_required_parameters_are_declared_for_preflight() -> None:
    required = required_parameters(DesignSituation.PERSISTENT)
    assert f"{EC2_11}:alpha_ct" in required
    # alpha_cc n'a rien a faire ici: l'adherence depend de la traction.
    assert f"{EC2_11}:alpha_cc" not in required
