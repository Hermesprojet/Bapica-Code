"""Property tests — cahier des charges section 8.2.

"Tests de proprietes : monotonie (plus de charge => plus de sollicitation),
 homogeneite dimensionnelle, cas limites, sections nulles, materiaux hors
 domaine."

These check invariants that must hold for *every* input in the domain, not just
the cases someone thought to tabulate.
"""

from __future__ import annotations

from itertools import pairwise

import pytest

from eurostruct_engine.ec2 import RectangularSection, design_flexure
from eurostruct_engine.materials import concrete, reinforcement
from eurostruct_engine.units import Q_

MOMENTS = [20.0, 60.0, 120.0, 200.0, 280.0, 360.0, 440.0]


def _run(params, M=250.0, b=300.0, h=600.0, d=550.0, grade="C30/37", steel="B500B"):
    return design_flexure(
        section=RectangularSection(b=Q_(b, "mm"), h=Q_(h, "mm"), d=Q_(d, "mm")),
        concrete=concrete(grade),
        steel=reinforcement(steel),
        M_Ed=Q_(M, "kN*m"),
        params=params,
    )


@pytest.mark.property
def test_required_area_increases_with_moment(params_be) -> None:
    areas = [_run(params_be, M=m).As_strength.to("mm**2").magnitude for m in MOMENTS]
    assert all(a < b for a, b in pairwise(areas))


@pytest.mark.property
def test_neutral_axis_deepens_with_moment(params_be) -> None:
    xs = [_run(params_be, M=m).xi for m in MOMENTS]
    assert all(a < b for a, b in pairwise(xs))


@pytest.mark.property
def test_lever_arm_shortens_as_moment_grows(params_be) -> None:
    zs = [_run(params_be, M=m).z.to("mm").magnitude for m in MOMENTS]
    assert all(a > b for a, b in pairwise(zs))


@pytest.mark.property
def test_deeper_section_needs_less_steel(params_be) -> None:
    areas = [
        _run(params_be, h=h, d=h - 50.0).As_strength.to("mm**2").magnitude
        # 450 mm sort du domaine avec alpha_cc = 0,85: mu depasse mu_lim.
        for h in (500.0, 550.0, 600.0, 700.0, 800.0)
    ]
    assert all(a > b for a, b in pairwise(areas))


@pytest.mark.property
def test_stronger_concrete_never_needs_more_steel(params_be) -> None:
    grades = ["C20/25", "C25/30", "C30/37", "C35/45", "C40/50", "C50/60"]
    areas = [_run(params_be, grade=g).As_strength.to("mm**2").magnitude for g in grades]
    assert all(a >= b for a, b in pairwise(areas))


@pytest.mark.property
def test_stronger_steel_needs_less_area(params_be) -> None:
    a400 = _run(params_be, steel="B400B").As_strength.to("mm**2").magnitude
    a500 = _run(params_be, steel="B500B").As_strength.to("mm**2").magnitude
    a600 = _run(params_be, steel="B600B").As_strength.to("mm**2").magnitude
    assert a400 > a500 > a600


@pytest.mark.property
def test_steel_strain_decreases_as_the_section_is_more_loaded(params_be) -> None:
    """More moment means a deeper neutral axis, so less strain in the steel."""
    eps = [_run(params_be, M=m).eps_s for m in MOMENTS]
    assert all(a > b for a, b in pairwise(eps))


@pytest.mark.property
def test_neutral_axis_stays_within_the_ductility_limit(params_be) -> None:
    for m in MOMENTS:
        r = _run(params_be, M=m)
        assert 0.0 < r.xi <= r.xi_lim


@pytest.mark.property
def test_vanishing_moment_tends_to_zero_required_area(params_be) -> None:
    """As M -> 0, the strength requirement vanishes; detailing still applies."""
    tiny = _run(params_be, M=1e-6)
    assert tiny.As_strength.to("mm**2").magnitude < 1e-3
    assert tiny.As_required == tiny.As_min  # §9.2.1.1(1) still governs


@pytest.mark.property
def test_scaling_the_section_scales_the_moment_capacity(params_be) -> None:
    """Doubling b doubles the resistance of a geometrically similar section."""
    a = _run(params_be, b=300.0, M=200.0)
    b = _run(params_be, b=600.0, M=400.0)
    assert b.As_strength.to("mm**2").magnitude == pytest.approx(
        2.0 * a.As_strength.to("mm**2").magnitude, rel=1e-12
    )
    assert b.xi == pytest.approx(a.xi, rel=1e-12)
    assert b.z.to("mm").magnitude == pytest.approx(a.z.to("mm").magnitude, rel=1e-12)


@pytest.mark.property
def test_utilisation_grows_with_moment_for_a_fixed_section(params_be) -> None:
    from eurostruct_engine.materials.reinforcement import bars_area

    As = bars_area(4, 25)
    utils = [
        _run_with_As(params_be, M=m, As=As).report.checks[0].utilisation
        for m in (100.0, 200.0, 300.0, 400.0)
    ]
    assert all(a < b for a, b in pairwise(utils))


def _run_with_As(params, M, As):
    return design_flexure(
        section=RectangularSection(b=Q_(300, "mm"), h=Q_(600, "mm"), d=Q_(550, "mm")),
        concrete=concrete("C30/37"), steel=reinforcement("B500B"),
        M_Ed=Q_(M, "kN*m"), params=params, A_s_provided=As,
    )
