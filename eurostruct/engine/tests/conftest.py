"""Shared fixtures.

Note on ``strict=False``: the seeded National Annex data sets carry the status
``na_pending_verification``, because no one has yet read the published ANB / NA
and confirmed the values. The engine therefore refuses to use them in strict
mode, which is the intended production behaviour. The tests below exercise the
*mechanics* of the engine and so opt out explicitly — and
``test_ndp.py::test_strict_mode_refuses_unverified_parameter`` proves the guard
itself works.
"""

from __future__ import annotations

from datetime import date

import pytest

from eurostruct_engine.ec2 import RectangularSection
from eurostruct_engine.materials import concrete, reinforcement
from eurostruct_engine.ndp import load_parameter_set
from eurostruct_engine.units import Q_

#: Pinned so a calculation stays reproducible regardless of when the suite runs.
AS_OF = date(2026, 7, 26)


@pytest.fixture
def params_be():
    return load_parameter_set("BE", strict=False, as_of=AS_OF)


@pytest.fixture
def params_fr():
    return load_parameter_set("FR", strict=False, as_of=AS_OF)


@pytest.fixture
def params_be_shear():
    """Belgium, with a HYPOTHETICAL scalar bound on the strut angle.

    NBN EN 1992-1-1 ANB §6.2.3(2) fixes cot θ_max by an expression the scalar
    model cannot hold, so real Belgian data refuses the shear check outright —
    which ``test_belgium_is_refused_for_want_of_a_strut_bound`` verifies.

    That refusal also makes the Belgian alpha_cc branching unreachable in a
    shear calculation, and that branching is the whole reason the conditional
    mechanism was built. So this fixture rebuilds the registry with the EN
    recommendation substituted for that ONE parameter, purely to reach the code
    path. The value 2,5 is not asserted anywhere and never leaves the tests;
    what is asserted is that alpha_cc resolves to the "other" branch.
    """
    import dataclasses

    from eurostruct_engine.ndp.model import ValidationStatus
    from eurostruct_engine.ndp.registry import ParameterSet

    base = load_parameter_set("BE", strict=False, as_of=AS_OF)
    annex = base.registry.annex_for("EN 1992-1-1", AS_OF)
    patched = tuple(
        dataclasses.replace(
            p,
            parameter_value=2.5,
            validation_status=ValidationStatus.PENDING_VERIFICATION,
            notes="HYPOTHESE DE TEST — pas la valeur de l'ANB belge.",
        )
        if p.parameter_name == "cot_theta_max" else p
        for p in annex.parameters
    )
    registry = dataclasses.replace(
        base.registry,
        annexes=tuple(
            dataclasses.replace(a, parameters=patched) if a is annex else a
            for a in base.registry.annexes
        ),
    )
    return ParameterSet(registry=registry, region=None, as_of=AS_OF, strict=False)


@pytest.fixture
def c30():
    return concrete("C30/37")


@pytest.fixture
def b500b():
    return reinforcement("B500B")


@pytest.fixture
def section_300x600():
    """The reference section used across the hand-checked cases."""
    return RectangularSection(b=Q_(300, "mm"), h=Q_(600, "mm"), d=Q_(550, "mm"))


@pytest.fixture
def params_fr_sls():
    """France, with a HYPOTHETICAL scalar k3 for crack spacing.

    NF EN 1992-1-1/NA §7.3.4(3) keeps k3 = 3,4 only up to a 25 mm cover; beyond
    that it becomes ``3,4 (25/c)^{2/3}``, a formula in the cover. The scalar
    model cannot hold that, so real French data refuses the crack-width check
    outright — which ``test_france_refuses_crack_width_for_want_of_a_formula``
    verifies.

    That refusal also makes every downstream assembly unreachable for France:
    the note de calcul cannot carry a serviceability section, and the §7.2
    stress limits — which France does NOT modify — become untestable with it.
    So this fixture substitutes the EN recommendation for that ONE parameter,
    purely to reach the code path. The value 3,4 is not asserted anywhere and
    never leaves the tests; what is exercised is the assembly around it.
    """
    import dataclasses

    from eurostruct_engine.ndp.model import ValidationStatus
    from eurostruct_engine.ndp.registry import ParameterSet

    base = load_parameter_set("FR", strict=False, as_of=AS_OF)
    annex = base.registry.annex_for("EN 1992-1-1", AS_OF)
    patched = tuple(
        dataclasses.replace(
            p,
            parameter_value=3.4,
            validation_status=ValidationStatus.PENDING_VERIFICATION,
            notes="HYPOTHESE DE TEST — pas ce que dit le NA francais.",
        )
        if p.parameter_name == "k3_crack_spacing" else p
        for p in annex.parameters
    )
    registry = dataclasses.replace(
        base.registry,
        annexes=tuple(
            dataclasses.replace(a, parameters=patched) if a is annex else a
            for a in base.registry.annexes
        ),
    )
    return ParameterSet(registry=registry, region=None, as_of=AS_OF, strict=False)
