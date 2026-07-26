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
def c30():
    return concrete("C30/37")


@pytest.fixture
def b500b():
    return reinforcement("B500B")


@pytest.fixture
def section_300x600():
    """The reference section used across the hand-checked cases."""
    return RectangularSection(b=Q_(300, "mm"), h=Q_(600, "mm"), d=Q_(550, "mm"))
