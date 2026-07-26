"""Reinforcing steel properties — EN 1992-1-1 §3.2 and Annex C.

The modulus of elasticity is fixed by §3.2.7(4) at 200 GPa and is *not* a
nationally determined parameter. The partial factor ``gamma_S`` is, and lives
in :mod:`eurostruct_engine.ndp`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Final

from ..exceptions import OutOfValidationDomain
from ..units import Q_, Quantity, require_dimension

__all__ = [
    "DuctilityClass",
    "Reinforcement",
    "STANDARD_GRADES",
    "reinforcement",
    "BAR_DIAMETERS",
    "bar_area",
    "bars_area",
]

#: Design value of the modulus of elasticity — EN 1992-1-1 §3.2.7(4).
ES: Final[Quantity] = Q_(200.0, "GPa")


class DuctilityClass(str, Enum):
    """Ductility class — EN 1992-1-1 Annex C, Table C.1.

    Class A is excluded from some seismic and redistribution applications;
    EN 1998-1 restricts the classes usable in DCM/DCH.
    """

    A = "A"
    B = "B"
    C = "C"


#: Characteristic yield strength by designation.
STANDARD_GRADES: Final[dict[str, tuple[float, DuctilityClass]]] = {
    "B400A": (400.0, DuctilityClass.A),
    "B400B": (400.0, DuctilityClass.B),
    "B400C": (400.0, DuctilityClass.C),
    "B500A": (500.0, DuctilityClass.A),
    "B500B": (500.0, DuctilityClass.B),
    "B500C": (500.0, DuctilityClass.C),
    "B600A": (600.0, DuctilityClass.A),
    "B600B": (600.0, DuctilityClass.B),
    "B600C": (600.0, DuctilityClass.C),
}

#: Minimum characteristic strain at maximum force — Annex C, Table C.1.
_EPS_UK: Final[dict[DuctilityClass, float]] = {
    DuctilityClass.A: 2.5e-2,
    DuctilityClass.B: 5.0e-2,
    DuctilityClass.C: 7.5e-2,
}

#: Preferred bar diameters (mm) used by the detailing and drawing modules.
BAR_DIAMETERS: Final[tuple[int, ...]] = (6, 8, 10, 12, 14, 16, 20, 25, 32, 40)


@dataclass(frozen=True, slots=True)
class Reinforcement:
    """A reinforcing steel grade."""

    name: str
    fyk: Quantity
    ductility: DuctilityClass

    def __post_init__(self) -> None:
        require_dimension(self.fyk, "[mass] / [length] / [time] ** 2", "fyk")
        f = self.fyk.to("MPa").magnitude
        if not (400.0 <= f <= 600.0):
            raise OutOfValidationDomain(
                "fyk_out_of_range",
                f"fyk = {f} MPa hors du domaine d'application de "
                "l'EN 1992-1-1 (400 a 600 MPa).",
                clause="EN 1992-1-1 §3.2.2(3)P",
            )

    @property
    def Es(self) -> Quantity:
        """Modulus of elasticity — §3.2.7(4): 200 GPa."""
        return ES

    @property
    def eps_uk(self) -> float:
        """Characteristic strain at maximum force — Annex C, Tab. C.1."""
        return _EPS_UK[self.ductility]

    def fyd(self, gamma_S: float) -> Quantity:
        """Design yield strength — §3.2.7(2), eq. (3.14): fyd = fyk / gamma_S.

        ``gamma_S`` is nationally determined and must be supplied from the
        project parameter set.
        """
        return self.fyk / gamma_S

    def eps_yd(self, gamma_S: float) -> float:
        """Design yield strain — §3.2.7(2): eps_yd = fyd / Es."""
        return float((self.fyd(gamma_S) / self.Es).to("dimensionless").magnitude)


def reinforcement(name: str) -> Reinforcement:
    """Build a standard grade by designation, e.g. ``reinforcement("B500B")``."""
    key = name.strip().upper()
    if key not in STANDARD_GRADES:
        raise OutOfValidationDomain(
            "unknown_reinforcement_grade",
            f"nuance d'acier '{name}' inconnue. Nuances disponibles: "
            f"{', '.join(STANDARD_GRADES)}.",
            clause="EN 1992-1-1 §3.2, Annexe C",
        )
    fyk, ductility = STANDARD_GRADES[key]
    return Reinforcement(name=key, fyk=Q_(fyk, "MPa"), ductility=ductility)


def bar_area(diameter_mm: float) -> Quantity:
    """Cross-sectional area of one bar of the given nominal diameter."""
    return Q_(math.pi * diameter_mm**2 / 4.0, "mm**2")


def bars_area(count: int, diameter_mm: float) -> Quantity:
    """Total area of *count* bars of nominal diameter *diameter_mm*."""
    if count < 0:
        raise ValueError("le nombre de barres ne peut pas etre negatif")
    return count * bar_area(diameter_mm)
