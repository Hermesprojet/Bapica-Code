"""Physical units for the calculation engine.

Cahier des charges section 5.2 / 8.2: every physical quantity carries its unit.
There is no bare numeric constant in the domain code, and adding kN to kN*m is a
hard error rather than a silent bug.

A single :class:`pint.UnitRegistry` is shared process-wide: Pint quantities
built from different registries cannot be combined, so the registry must never
be re-instantiated per call.

Determinism note
----------------
Pint stores magnitudes as plain Python floats and does not reorder operations,
so a calculation expressed with quantities is as reproducible as the same
calculation on floats. Conversions are exact powers of ten for the unit systems
used here (mm/m, N/kN, MPa/GPa).
"""

from __future__ import annotations

from typing import Any, Final

import pint

from .exceptions import UnitError

__all__ = [
    "ureg",
    "Q_",
    "Quantity",
    "mm",
    "m",
    "mm2",
    "mm3",
    "mm4",
    "kN",
    "kNm",
    "MPa",
    "GPa",
    "dimensionless",
    "require_dimension",
    "magnitude",
    "fmt",
]

#: Process-wide unit registry. Import this, never build another one.
ureg: Final[pint.UnitRegistry] = pint.UnitRegistry(system="mks")

# Short pretty format ("25 MPa"). Pint moved this onto the formatter object in
# 0.24; keep working on both without emitting a DeprecationWarning, since CI
# treats warnings as failures.
if hasattr(ureg, "formatter"):
    ureg.formatter.default_format = "~P"
else:  # pragma: no cover - pint < 0.24
    ureg.default_format = "~P"

Quantity = ureg.Quantity
Q_ = ureg.Quantity

# --- Shorthand units used across the structural modules ---------------------
mm: Final = ureg.mm
m: Final = ureg.m
mm2: Final = ureg.mm**2
mm3: Final = ureg.mm**3
mm4: Final = ureg.mm**4
kN: Final = ureg.kN
kNm: Final = ureg.kN * ureg.m
MPa: Final = ureg.MPa
GPa: Final = ureg.GPa
dimensionless: Final = ureg.dimensionless


def require_dimension(value: Any, dimension: str, name: str) -> Quantity:
    """Validate that *value* is a quantity of the expected dimensionality.

    :param value: the quantity to check.
    :param dimension: a Pint dimensionality string, e.g. ``"[length]"`` or
        ``"[force] * [length]"``. Use ``""`` for dimensionless.
    :param name: symbol name, used in the error message.
    :raises UnitError: if *value* is not a quantity or has the wrong dimension.

    Plain numbers are accepted only where *dimension* is dimensionless; this is
    deliberate, so that a bare ``0.85`` cannot be passed where a stress is
    expected.
    """
    if not isinstance(value, Quantity):
        if dimension in ("", "dimensionless"):
            return Q_(float(value), "dimensionless")
        raise UnitError(
            f"'{name}' doit etre une grandeur avec unite ({dimension}), "
            f"recu un nombre nu: {value!r}. "
            "Utiliser par exemple Q_(25, 'MPa')."
        )

    expected = ureg.get_dimensionality(dimension) if dimension else {}
    if dict(value.dimensionality) != dict(expected):
        raise UnitError(
            f"'{name}' a la dimension {value.dimensionality} "
            f"mais {dimension or 'dimensionless'} est attendu."
        )
    return value


def magnitude(value: Quantity, unit: str) -> float:
    """Return the float magnitude of *value* expressed in *unit*.

    Used at serialization boundaries (JSON, DXF, PDF) where a plain number is
    required. Keeping this explicit means the unit of every stored number is
    recorded next to it.
    """
    return float(value.to(unit).magnitude)


def fmt(value: Quantity | float, unit: str | None = None, digits: int = 3) -> str:
    """Format a quantity for the numeric application line of a calculation step.

    The output is stable for a given input, which matters because these strings
    end up verbatim in the note de calcul and are covered by golden tests.

    >>> fmt(Q_(25.0, "MPa"))
    '25 MPa'
    >>> fmt(Q_(1234.5678, "mm**2"), "mm**2", digits=1)
    '1234.6 mm²'
    """
    if isinstance(value, Quantity):
        q = value.to(unit) if unit else value
        num = _trim(float(q.magnitude), digits)
        sym = f"{q.units:~P}"
        return f"{num} {sym}".strip()
    return _trim(float(value), digits)


def _trim(x: float, digits: int) -> str:
    """Fixed-decimal formatting with trailing zeros removed, locale-independent."""
    s = f"{x:.{digits}f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s if s not in ("-0", "") else "0"
