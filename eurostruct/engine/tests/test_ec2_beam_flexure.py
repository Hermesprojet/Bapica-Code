"""EN 1992-1-1 ULS bending — correctness of the design module.

The strongest test here is :func:`test_independent_equilibrium`, which does not
reuse the module's closed-form inversion at all. It integrates the rectangular
stress block numerically and checks that the section the engine designed is in
equilibrium under the applied moment. If the algebra of
``xi = (1 - sqrt(1 - 2 mu)) / lambda`` were wrong, that test would fail even
though every other formula in the module agreed with it.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from eurostruct_engine.basis import DesignSituation
from eurostruct_engine.ec2 import RectangularSection, design_flexure, moment_resistance
from eurostruct_engine.exceptions import InconsistentInput, OutOfValidationDomain
from eurostruct_engine.materials import concrete, reinforcement
from eurostruct_engine.materials.reinforcement import bars_area
from eurostruct_engine.units import Q_


def _design(params, M_kNm=250.0, **kw):
    defaults = dict(
        section=RectangularSection(b=Q_(300, "mm"), h=Q_(600, "mm"), d=Q_(550, "mm")),
        concrete=concrete("C30/37"),
        steel=reinforcement("B500B"),
        M_Ed=Q_(M_kNm, "kN*m"),
        params=params,
    )
    defaults.update(kw)
    return design_flexure(**defaults)


# ---------------------------------------------------------------------------
# Hand calculation
# ---------------------------------------------------------------------------
@pytest.mark.reference
def test_hand_calculation_case(params_be) -> None:
    """b=300, h=600, d=550, C30/37, B500B, M_Ed = 250 kN.m.

    Worked by hand with alpha_cc = 1,0 / gamma_C = 1,5 / gamma_S = 1,15:

        fcd  = 30 / 1,5                       = 20,000 MPa
        fyd  = 500 / 1,15                     = 434,783 MPa
        mu   = 250e6 / (300 x 550^2 x 20)     = 0,137741
        xi   = (1 - sqrt(1 - 2 mu)) / 0,8     = 0,186017
        x    = 0,186017 x 550                 = 102,310 mm
        z    = 550 (1 - 0,8 x 0,186017 / 2)   = 509,076 mm
        As   = 250e6 / (434,783 x 509,076)    = 1129,50 mm2
    """
    r = _design(params_be)
    assert r.mu == pytest.approx(0.137741, abs=5e-7)
    assert r.xi == pytest.approx(0.186017, abs=5e-7)
    assert r.x.to("mm").magnitude == pytest.approx(102.310, abs=5e-4)
    assert r.z.to("mm").magnitude == pytest.approx(509.076, abs=5e-4)
    assert r.As_strength.to("mm**2").magnitude == pytest.approx(1129.50, abs=5e-3)


# ---------------------------------------------------------------------------
# Independent verification
# ---------------------------------------------------------------------------
@pytest.mark.reference
@pytest.mark.parametrize("M_kNm", [60.0, 120.0, 250.0, 400.0, 500.0])
def test_independent_equilibrium(params_be, M_kNm: float) -> None:
    """Numerically integrate the stress block and check section equilibrium.

    Compression resultant and its centroid are obtained by quadrature over the
    depth of the block, without using ``z = d - lambda x / 2``. Both horizontal
    equilibrium and moment equilibrium about the tension steel must hold.
    """
    r = _design(params_be, M_kNm=M_kNm)

    b = 300.0                       # mm
    d = 550.0                       # mm
    fcd = 20.0                      # MPa = N/mm2
    fyd = 500.0 / 1.15              # MPa
    lam, eta = 0.8, 1.0

    x = r.x.to("mm").magnitude
    As = r.As_strength.to("mm**2").magnitude

    # Quadrature over the compression block, measured down from the top face.
    depth = lam * x
    ys = np.linspace(0.0, depth, 200_001)
    stress = np.full(ys.shape, eta * fcd)
    Fc = float(np.trapezoid(stress * b, ys))                 # N
    y_c = float(np.trapezoid(stress * b * ys, ys) / Fc)      # mm below top face

    Fs = As * fyd                                            # N

    # Horizontal equilibrium.
    assert Fc == pytest.approx(Fs, rel=1e-9)
    # Centroid of the block, independent of the closed form.
    assert y_c == pytest.approx(depth / 2.0, rel=1e-9)
    # Moment equilibrium about the tension reinforcement.
    M_int = Fs * (d - y_c)                                   # N.mm
    assert M_int == pytest.approx(M_kNm * 1e6, rel=1e-9)


@pytest.mark.reference
def test_moment_resistance_inverts_the_design(params_be) -> None:
    """Designing for M_Ed then evaluating M_Rd must return M_Ed."""
    for M in (75.0, 180.0, 320.0, 450.0):
        r = _design(params_be, M_kNm=M)
        assert r.resistance.M_Rd.to("kN*m").magnitude == pytest.approx(M, rel=1e-9)


def test_steel_yields_in_the_validated_domain(params_be) -> None:
    r = _design(params_be)
    eps_yd = reinforcement("B500B").eps_yd(1.15)
    assert r.eps_s > eps_yd
    assert r.resistance.steel_yields


# ---------------------------------------------------------------------------
# Detailing limits
# ---------------------------------------------------------------------------
def test_minimum_reinforcement_governs_when_lightly_loaded(params_be) -> None:
    """§9.2.1.1(1): a nearly unloaded beam still carries A_s,min."""
    r = _design(params_be, M_kNm=5.0)
    assert r.As_strength < r.As_min
    assert r.As_required == r.As_min
    # And the ULS check is then comfortably satisfied.
    assert r.report.checks[0].utilisation < 0.3


def test_as_min_formula(params_be) -> None:
    """A_s,min = max(0,26 fctm/fyk bt d ; 0,0013 bt d) — eq. (9.1N)."""
    r = _design(params_be)
    fctm = concrete("C30/37").fctm.to("MPa").magnitude
    expected = max(0.26 * fctm / 500.0 * 300.0 * 550.0, 0.0013 * 300.0 * 550.0)
    assert r.As_min.to("mm**2").magnitude == pytest.approx(expected, rel=1e-12)


def test_as_max_is_four_percent_of_gross_area(params_be) -> None:
    r = _design(params_be)
    assert r.As_max.to("mm**2").magnitude == pytest.approx(0.04 * 300.0 * 600.0)


# ---------------------------------------------------------------------------
# Provided reinforcement
# ---------------------------------------------------------------------------
def test_provided_reinforcement_yields_a_real_utilisation(params_be) -> None:
    """With real bars chosen above A_s,req, utilisation drops below 1."""
    As = bars_area(4, 20)  # 1256,6 mm2 against 1129,5 required
    r = _design(params_be, A_s_provided=As)
    uls = r.report.checks[0]
    assert uls.passed
    assert 0.85 < uls.utilisation < 0.95
    assert r.As_provided.to("mm**2").magnitude == pytest.approx(1256.637, abs=1e-3)


def test_insufficient_provided_reinforcement_fails_the_check(params_be) -> None:
    """Under-reinforcing must fail, and the failure must be listed first."""
    r = _design(params_be, A_s_provided=bars_area(3, 16))
    uls = r.report.checks[0]
    assert not uls.passed
    assert uls.utilisation > 1.0
    assert r.report.failures()[0].name == uls.name
    assert not r.report.passed


def test_exact_required_area_is_not_reported_as_a_failure(params_be) -> None:
    """M_Rd equals M_Ed by construction; float round-off must not read as FAIL."""
    r = _design(params_be)
    assert r.report.checks[0].passed
    assert r.report.checks[0].utilisation == pytest.approx(1.0, abs=1e-9)


# ---------------------------------------------------------------------------
# Refusals — the engine must not answer outside its validated domain
# ---------------------------------------------------------------------------
def test_high_strength_concrete_is_refused(params_be) -> None:
    with pytest.raises(OutOfValidationDomain) as e:
        _design(params_be, concrete=concrete("C60/75"))
    assert e.value.what == "high_strength_concrete"


def test_over_reinforced_section_is_refused(params_be) -> None:
    """Beyond mu_lim the section needs compression steel: refuse, don't guess."""
    with pytest.raises(OutOfValidationDomain) as e:
        _design(params_be, M_kNm=800.0)
    assert e.value.what == "compression_reinforcement_required"
    # The message must tell the engineer what to change.
    assert "augmenter" in e.value.detail.lower()


def test_moment_just_below_and_above_the_ductility_limit(params_be) -> None:
    """The refusal boundary is mu_lim, and it is where it should be."""
    b, d, fcd, eta, lam = 300.0, 550.0, 20.0, 1.0, 0.8
    xi_lim = (1.0 - 0.44) / 1.25
    mu_lim = lam * xi_lim * (1.0 - lam * xi_lim / 2.0)
    M_lim_kNm = mu_lim * b * d**2 * eta * fcd / 1e6

    ok = _design(params_be, M_kNm=M_lim_kNm * 0.999)
    assert ok.xi < ok.xi_lim
    with pytest.raises(OutOfValidationDomain):
        _design(params_be, M_kNm=M_lim_kNm * 1.001)


def test_effective_depth_must_be_less_than_overall_depth() -> None:
    with pytest.raises(InconsistentInput):
        RectangularSection(b=Q_(300, "mm"), h=Q_(600, "mm"), d=Q_(600, "mm"))


def test_negative_moment_is_refused(params_be) -> None:
    with pytest.raises(InconsistentInput):
        _design(params_be, M_kNm=-100.0)


def test_over_reinforced_resistance_is_refused(params_be) -> None:
    """A section given far too much steel would fail in a brittle way."""
    c, s = concrete("C30/37"), reinforcement("B500B")
    with pytest.raises(OutOfValidationDomain) as e:
        moment_resistance(
            section=RectangularSection(b=Q_(300, "mm"), h=Q_(600, "mm"), d=Q_(550, "mm")),
            concrete=c, steel=s,
            A_s=Q_(12000, "mm**2"),
            fcd=Q_(20, "MPa"), fyd=Q_(500 / 1.15, "MPa"),
            eps_yd=s.eps_yd(1.15),
        )
    assert e.value.what == "steel_not_yielding"


# ---------------------------------------------------------------------------
# Design situation
# ---------------------------------------------------------------------------
def test_accidental_situation_uses_its_own_partial_factors(params_be) -> None:
    """gamma_C = 1,2 and gamma_S = 1,0 give a smaller required area."""
    persistent = _design(params_be, situation=DesignSituation.PERSISTENT)
    accidental = _design(params_be, situation=DesignSituation.ACCIDENTAL)
    assert accidental.As_strength < persistent.As_strength
    assert "EN 1992-1-1:gamma_C_accidental" in accidental.journal.symbols()
    assert "EN 1992-1-1:gamma_C_persistent" in persistent.journal.symbols()
