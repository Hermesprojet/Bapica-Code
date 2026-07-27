"""EN 1992-1-1 §6.2 — shear, correctness of the design module.

The strongest test here is :func:`test_web_crushing_by_strut_geometry`, which
reaches ``V_Rd,max`` through the trigonometry of the strut rather than through
the algebraic identity the module uses. If ``1/(cot θ + tan θ)`` had been
mis-transcribed, that test would fail while every formula agreeing with the
module still passed.
"""

from __future__ import annotations

import math

import pytest

from eurostruct_engine.basis import DesignSituation
from eurostruct_engine.ec2 import ShearLinks, ShearSection, design_shear
from eurostruct_engine.ec2.beam_shear import EC2_11, required_parameters
from eurostruct_engine.exceptions import InconsistentInput, OutOfValidationDomain
from eurostruct_engine.materials import concrete, reinforcement
from eurostruct_engine.materials.reinforcement import bars_area
from eurostruct_engine.units import Q_

B_W, D = 300.0, 550.0


def _section(**kw) -> ShearSection:
    base = dict(b_w=Q_(B_W, "mm"), d=Q_(D, "mm"), A_sl=bars_area(4, 20))
    base.update(kw)
    return ShearSection(**base)


def _design(params, V_kN=300.0, **kw):
    defaults = dict(
        section=_section(),
        concrete=concrete("C30/37"),
        steel=reinforcement("B500B"),
        V_Ed=Q_(V_kN, "kN"),
        params=params,
        cot_theta=2.5,
        links=ShearLinks(A_sw=Q_(157.0, "mm**2"), s=Q_(150.0, "mm")),
        element="P1",
    )
    defaults.update(kw)
    return design_shear(**defaults)


# ---------------------------------------------------------------------------
# Hand calculation
# ---------------------------------------------------------------------------
@pytest.mark.reference
def test_hand_calculation_case(params_fr) -> None:
    """b_w=300, d=550, 4 HA20, C30/37, B500B, cot θ = 2,5, cadres HA10/150.

    Worked by hand with the French parameter set (alpha_cc = 1,0):

        k       = 1 + √(200/550)                 = 1,60302
        rho_l   = 1256,64 / (300 × 550)          = 0,0076160
        C_Rd,c  = 0,18 / 1,5                     = 0,12
        v_Rd,c  = 0,12 × 1,6030227 × (100 × 0,007615982 × 30)^(1/3)
                = 0,12 × 1,6030227 × 2,837586    = 0,545846 MPa
        v_min   = 0,035 × 1,6030227^1,5 × √30    = 0,389079 MPa   (non gouvernant)
        V_Rd,c  = 0,545846 × 300 × 550           = 90 064,6 N = 90,065 kN

        z       = 0,9 × 550                      = 495 mm
        f_ywd   = 500 / 1,15                     = 434,783 MPa
        nu_1    = 0,6 (1 − 30/250)               = 0,528
        f_cd    = 1,0 × 30 / 1,5                 = 20 MPa
        V_Rd,max= 1,0 × 300 × 495 × 0,528 × 20 / (2,5 + 0,4)
                = 1 568 160 / 2,9                = 540 744,8 N = 540,745 kN
        A_sw/s  = 157 / 150                      = 1,04667 mm²/mm
        V_Rd,s  = 1,04667 × 495 × 434,7826 × 2,5 = 563 152,2 N = 563,152 kN

    V_Rd = min(V_Rd,s ; V_Rd,max) = 540,74 kN: l'ecrasement des bielles
    gouverne, ce que le choix d'un cot θ eleve rendait previsible.
    """
    r = _design(params_fr)
    assert r.V_Rd_c.to("kN").magnitude == pytest.approx(90.065, abs=5e-4)
    assert r.V_Rd_max.to("kN").magnitude == pytest.approx(540.745, abs=5e-4)
    assert r.V_Rd_s.to("kN").magnitude == pytest.approx(563.152, abs=5e-4)
    assert r.V_Rd.to("kN").magnitude == pytest.approx(540.745, abs=5e-4)


# ---------------------------------------------------------------------------
# Independent verification
# ---------------------------------------------------------------------------
@pytest.mark.reference
@pytest.mark.parametrize("cot_theta", [1.0, 1.5, 2.0, 2.5])
def test_web_crushing_by_strut_geometry(params_fr, cot_theta: float) -> None:
    """Reach V_Rd,max through the strut's trigonometry, not through the identity.

    The module divides by ``cot θ + tan θ``. Equilibrium of the inclined strut
    gives the web compression as ``V / (b_w z sin θ cos θ)``, so capping it at
    ``nu_1 f_cd`` yields ``V = alpha_cw nu_1 f_cd b_w z sin θ cos θ``. The two
    agree only because ``sin θ cos θ = 1/(cot θ + tan θ)`` — an identity this
    test does not assume.
    """
    r = _design(params_fr, cot_theta=cot_theta)

    theta = math.atan(1.0 / cot_theta)
    nu1 = 0.6 * (1.0 - 30.0 / 250.0)
    fcd = 1.0 * 30.0 / 1.5
    z = 0.9 * D
    expected_N = 1.0 * nu1 * fcd * B_W * z * math.sin(theta) * math.cos(theta)

    assert r.V_Rd_max.to("N").magnitude == pytest.approx(expected_N, rel=1e-12)


@pytest.mark.reference
def test_truss_carries_the_links_it_crosses(params_fr) -> None:
    """V_Rd,s counted link by link, rather than by the closed formula.

    A diagonal crack of horizontal extent ``z cot θ`` crosses ``z cot θ / s``
    sets of links, each yielding ``A_sw f_ywd``.
    """
    s, A_sw = 150.0, 157.0
    r = _design(params_fr, links=ShearLinks(A_sw=Q_(A_sw, "mm**2"), s=Q_(s, "mm")))

    z = 0.9 * D
    n_crossed = z * r.cot_theta / s
    expected_N = n_crossed * A_sw * (500.0 / 1.15)

    assert r.V_Rd_s.to("N").magnitude == pytest.approx(expected_N, rel=1e-12)


# ---------------------------------------------------------------------------
# The two regimes of §6.2.1 are exclusive
# ---------------------------------------------------------------------------
def test_below_V_Rd_c_no_designed_links_are_required(params_fr) -> None:
    r = _design(params_fr, V_kN=80.0)
    assert not r.links_required
    assert r.V_Rd_s is None and r.V_Rd_max is None
    assert r.V_Rd == r.V_Rd_c
    # Les cadres minimaux restent dus: c'est une poutre.
    assert r.Asw_over_s_required == r.Asw_over_s_min


def test_above_V_Rd_c_the_truss_carries_everything(params_fr) -> None:
    """§6.2.1: the two contributions are NOT added — a classic unsafe error."""
    r = _design(params_fr, V_kN=300.0)
    assert r.links_required
    assert r.V_Rd.to("kN").magnitude < (
        r.V_Rd_c.to("kN").magnitude + r.V_Rd_s.to("kN").magnitude
    )
    assert r.V_Rd == min(r.V_Rd_s, r.V_Rd_max, key=lambda q: q.to("kN").magnitude)


def test_the_regime_boundary_is_V_Rd_c(params_fr) -> None:
    V_c = _design(params_fr, V_kN=1.0).V_Rd_c.to("kN").magnitude
    assert not _design(params_fr, V_kN=V_c * 0.999).links_required
    assert _design(params_fr, V_kN=V_c * 1.001).links_required


# ---------------------------------------------------------------------------
# Detailing and the shift rule
# ---------------------------------------------------------------------------
def test_minimum_web_reinforcement(params_fr) -> None:
    """rho_w,min = 0,08 √fck / fyk — eq. (9.5N)."""
    r = _design(params_fr)
    expected = 0.08 * math.sqrt(30.0) / 500.0 * B_W * 1000.0   # mm²/m
    assert r.Asw_over_s_min.to("mm**2/m").magnitude == pytest.approx(expected, rel=1e-12)


def test_maximum_longitudinal_spacing(params_fr) -> None:
    r = _design(params_fr)
    assert r.s_l_max.to("mm").magnitude == pytest.approx(0.75 * D, rel=1e-12)


def test_spacing_beyond_the_maximum_fails_the_check(params_fr) -> None:
    r = _design(params_fr, links=ShearLinks(A_sw=Q_(157, "mm**2"), s=Q_(500, "mm")))
    spacing = next(c for c in r.report.checks if "Espacement" in c.name)
    assert not spacing.passed


def test_additional_longitudinal_force_follows_the_strut(params_fr) -> None:
    """eq. (6.18): flatter struts pull harder on the tension chord."""
    flat = _design(params_fr, cot_theta=2.5).delta_F_td.to("kN").magnitude
    steep = _design(params_fr, cot_theta=1.0).delta_F_td.to("kN").magnitude
    assert flat == pytest.approx(0.5 * 300.0 * 2.5)
    assert steep == pytest.approx(0.5 * 300.0 * 1.0)
    assert flat > steep


def test_no_truss_means_no_additional_force(params_fr) -> None:
    """Reported as zero rather than omitted: the note never leaves it unsaid."""
    r = _design(params_fr, V_kN=80.0)
    assert r.delta_F_td.magnitude == 0.0
    assert "delta_F_td" in r.journal.symbols()


# ---------------------------------------------------------------------------
# alpha_cc — the reason the conditional mechanism came first
# ---------------------------------------------------------------------------
def test_shear_reads_the_other_cases_branch_of_alpha_cc(params_be_shear) -> None:
    """§3.1.6(1)P: shear is « les autres cas », so alpha_cc = 1,0 in Belgium.

    Inheriting the bending value (0,85) would under-estimate f_cd by 15 %, and
    through V_Rd,max the web crushing resistance — in the unsafe direction.
    """
    r = _design(params_be_shear)
    step = r.journal.get(f"{EC2_11}:alpha_cc")
    assert step.value.magnitude == 1.0
    assert "other" in step.provenance.detail
    # f_cd = 1,0 x 30 / 1,5 et non 0,85 x 30 / 1,5.
    assert r.journal.get("f_cd").value.to("MPa").magnitude == pytest.approx(20.0)


# ---------------------------------------------------------------------------
# Refusals
# ---------------------------------------------------------------------------
def test_belgium_is_refused_for_want_of_a_strut_bound(params_be) -> None:
    """cot θ_max has no scalar value in the Belgian annex, so the check stops.

    Substituting the EN recommendation of 2,5 would use a value NBN EN
    1992-1-1 ANB §6.2.3(2) explicitly does not adopt. An unchecked bound is a
    missing verification.
    """
    from eurostruct_engine.exceptions import NationalAnnexIncomplete

    with pytest.raises(NationalAnnexIncomplete) as e:
        _design(params_be)
    keys = {b.key for b in e.value.blocking}
    assert f"{EC2_11}:cot_theta_max" in keys
    assert {b.reason for b in e.value.blocking} == {"not_representable"}


def test_a_strut_angle_outside_the_national_bounds_is_refused(params_fr) -> None:
    with pytest.raises(OutOfValidationDomain) as e:
        _design(params_fr, cot_theta=3.0)
    assert e.value.what == "strut_angle_out_of_bounds"

    with pytest.raises(OutOfValidationDomain):
        _design(params_fr, cot_theta=0.5)


def test_high_strength_concrete_is_refused(params_fr) -> None:
    with pytest.raises(OutOfValidationDomain) as e:
        _design(params_fr, concrete=concrete("C60/75"))
    assert e.value.what == "high_strength_concrete"


def test_negative_shear_is_refused(params_fr) -> None:
    with pytest.raises(InconsistentInput):
        _design(params_fr, V_kN=-100.0)


def test_axial_force_without_the_concrete_area_is_refused() -> None:
    with pytest.raises(InconsistentInput, match="A_c"):
        _section(N_Ed=Q_(200, "kN"))


def test_required_parameters_are_declared_for_preflight() -> None:
    """TICKET 1.3: the module states its needs before computing anything."""
    required = required_parameters(DesignSituation.PERSISTENT)
    assert f"{EC2_11}:cot_theta_max" in required
    assert f"{EC2_11}:alpha_cc" in required
    assert len(set(required)) == len(required)
