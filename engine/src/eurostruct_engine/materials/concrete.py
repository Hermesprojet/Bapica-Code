"""Concrete material properties — EN 1992-1-1 §3.1.

All properties are derived from the characteristic cylinder strength ``fck``
using the closed-form expressions of Table 3.1, rather than by interpolating a
stored table. That way a non-standard grade behaves consistently with a
standard one, and every value carries the equation it comes from.

None of the values in this module are nationally determined: Table 3.1 is
common to every National Annex. The partial factor ``gamma_C`` and the
coefficient ``alpha_cc`` *are* nationally determined and therefore live in
:mod:`eurostruct_engine.ndp`, not here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from ..exceptions import OutOfValidationDomain
from ..units import GPa, MPa, Q_, Quantity, require_dimension

__all__ = ["Concrete", "STANDARD_GRADES", "concrete"]

#: Standard grades of EN 1992-1-1 Table 3.1, as fck in MPa.
STANDARD_GRADES: Final[dict[str, float]] = {
    "C12/15": 12.0,
    "C16/20": 16.0,
    "C20/25": 20.0,
    "C25/30": 25.0,
    "C30/37": 30.0,
    "C35/45": 35.0,
    "C40/50": 40.0,
    "C45/55": 45.0,
    "C50/60": 50.0,
    "C55/67": 55.0,
    "C60/75": 60.0,
    "C70/85": 70.0,
    "C80/95": 80.0,
    "C90/105": 90.0,
}


@dataclass(frozen=True, slots=True)
class Concrete:
    """A concrete grade with its EN 1992-1-1 §3.1 properties.

    :param name: grade designation, e.g. ``"C30/37"``.
    :param fck: characteristic cylinder compressive strength at 28 days.
    """

    name: str
    fck: Quantity

    def __post_init__(self) -> None:
        require_dimension(self.fck, "[mass] / [length] / [time] ** 2", "fck")
        f = self.fck.to("MPa").magnitude
        if not (12.0 <= f <= 90.0):
            raise OutOfValidationDomain(
                "fck_out_of_range",
                f"fck = {f} MPa hors de la plage couverte par l'EN 1992-1-1 "
                "(C12/15 a C90/105).",
                clause="EN 1992-1-1 §3.1.2(2)P, Tab. 3.1",
            )

    # --- strengths ---------------------------------------------------------
    @property
    def fcm(self) -> Quantity:
        """Mean compressive strength — Table 3.1: fcm = fck + 8 MPa."""
        return self.fck + Q_(8.0, "MPa")

    @property
    def fctm(self) -> Quantity:
        """Mean axial tensile strength — Table 3.1."""
        f = self.fck.to("MPa").magnitude
        if f <= 50.0:
            return Q_(0.30 * f ** (2.0 / 3.0), "MPa")
        fcm = self.fcm.to("MPa").magnitude
        return Q_(2.12 * math.log(1.0 + fcm / 10.0), "MPa")

    @property
    def fctk_005(self) -> Quantity:
        """5% fractile tensile strength — Table 3.1: 0,7 fctm."""
        return 0.7 * self.fctm

    @property
    def fctk_095(self) -> Quantity:
        """95% fractile tensile strength — Table 3.1: 1,3 fctm."""
        return 1.3 * self.fctm

    @property
    def Ecm(self) -> Quantity:
        """Secant modulus of elasticity — Table 3.1: 22 (fcm/10)^0,3 in GPa."""
        fcm = self.fcm.to("MPa").magnitude
        return Q_(22.0 * (fcm / 10.0) ** 0.3, "GPa")

    # --- strains, rectangular stress block ---------------------------------
    @property
    def eps_cu3(self) -> float:
        """Ultimate strain for the bilinear/rectangular diagram — Table 3.1.

        Returned as a plain float in absolute strain (not per mille), because
        strain is dimensionless.
        """
        f = self.fck.to("MPa").magnitude
        if f <= 50.0:
            return 3.5e-3
        return (2.6 + 35.0 * ((90.0 - f) / 100.0) ** 4) * 1e-3

    @property
    def eps_c3(self) -> float:
        """Strain at reaching the maximum strength, bilinear diagram — Table 3.1."""
        f = self.fck.to("MPa").magnitude
        if f <= 50.0:
            return 1.75e-3
        return (1.75 + 0.55 * (f - 50.0) / 40.0) * 1e-3

    @property
    def eps_cu2(self) -> float:
        """Ultimate strain, parabola-rectangle diagram — Table 3.1."""
        f = self.fck.to("MPa").magnitude
        if f <= 50.0:
            return 3.5e-3
        return (2.6 + 35.0 * ((90.0 - f) / 100.0) ** 4) * 1e-3

    @property
    def eps_c2(self) -> float:
        """Strain at reaching maximum strength, parabola-rectangle — Table 3.1."""
        f = self.fck.to("MPa").magnitude
        if f <= 50.0:
            return 2.0e-3
        return (2.0 + 0.085 * (f - 50.0) ** 0.53) * 1e-3

    @property
    def lambda_(self) -> float:
        """Effective height factor of the rectangular stress block.

        EN 1992-1-1 §3.1.7(3), eq. (3.19) and (3.20).
        """
        f = self.fck.to("MPa").magnitude
        if f <= 50.0:
            return 0.8
        return 0.8 - (f - 50.0) / 400.0

    @property
    def eta(self) -> float:
        """Effective strength factor of the rectangular stress block.

        EN 1992-1-1 §3.1.7(3), eq. (3.21) and (3.22).
        """
        f = self.fck.to("MPa").magnitude
        if f <= 50.0:
            return 1.0
        return 1.0 - (f - 50.0) / 200.0

    # --- design values (need nationally determined parameters) -------------
    def fcd(self, alpha_cc: float, gamma_C: float) -> Quantity:
        """Design compressive strength — §3.1.6(1)P, eq. (3.15).

        ``alpha_cc`` and ``gamma_C`` are nationally determined and must be read
        from the project's :class:`~eurostruct_engine.ndp.registry.ParameterSet`.
        They are arguments rather than defaults so that no national value can be
        assumed by omission.
        """
        return alpha_cc * self.fck / gamma_C

    def fctd(self, alpha_ct: float, gamma_C: float) -> Quantity:
        """Design tensile strength — §3.1.6(2)P, eq. (3.16)."""
        return alpha_ct * self.fctk_005 / gamma_C


def concrete(name: str) -> Concrete:
    """Build a standard grade by designation, e.g. ``concrete("C30/37")``.

    :raises OutOfValidationDomain: for a designation that is not in Table 3.1.
        Non-standard strengths are still available through :class:`Concrete`
        directly, which keeps the standard catalogue unambiguous.
    """
    key = name.strip().upper()
    if key not in STANDARD_GRADES:
        raise OutOfValidationDomain(
            "unknown_concrete_grade",
            f"classe de beton '{name}' inconnue. Classes normalisees: "
            f"{', '.join(STANDARD_GRADES)}.",
            clause="EN 1992-1-1 Tab. 3.1",
        )
    return Concrete(name=key, fck=Q_(STANDARD_GRADES[key], "MPa"))
