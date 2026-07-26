"""Verification results: checks, utilisation ratios, reports.

Cahier des charges section 8.3:

    "Affichage systematique des taux de travail, jamais un simple « OK »."

A :class:`Check` therefore always carries the acting value, the resisting
value and their ratio. A check cannot be constructed without them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Sequence

from .traceability import Clause
from .units import Quantity, fmt

__all__ = ["CheckStatus", "Check", "VerificationReport", "FLOAT_TOLERANCE"]

#: Relative tolerance absorbing IEEE-754 round-off when comparing E_d to R_d.
#:
#: This is **not** an engineering allowance, and interdiction 9 of the cahier
#: des charges ("arrondir, approximer ou lisser un resultat pour qu'il passe une
#: verification") is not being bent here. At 1e-9 it sits roughly fifteen orders
#: of magnitude below the first significant figure of any structural quantity.
#: It exists for one situation: a check that is satisfied *exactly* by
#: construction -- reinforcement sized so that M_Rd equals M_Ed -- must not read
#: as a failure because the last bit of the mantissa rounded the other way.
#:
#: Any real overstress is orders of magnitude larger and is reported as a
#: failure. The utilisation ratio itself is never modified: it is stored and
#: displayed as computed.
FLOAT_TOLERANCE: float = 1e-9


class CheckStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    #: The check could not be performed because the configuration is outside
    #: the validated domain. Never silently treated as a pass.
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True, slots=True)
class Check:
    """One normative verification with its utilisation ratio.

    :param name: short identifier, e.g. ``"ULS flexion"``.
    :param acting: design value of the action effect (E_d).
    :param resisting: design value of the resistance (R_d).
    :param clause: the clause the check enforces.
    :param utilisation: E_d / R_d. Supplied explicitly rather than recomputed,
        because some checks compare quantities that are not a simple ratio
        (e.g. a strain against a limit).
    :param detail: explanation shown when the check fails, so the user learns
        *which* clause is not satisfied and why — cahier des charges section 6.8.
    """

    name: str
    acting: Quantity
    resisting: Quantity
    utilisation: float
    clause: Clause
    status: CheckStatus
    detail: str | None = None
    remedy: str | None = None

    @staticmethod
    def from_ratio(
        name: str,
        acting: Quantity,
        resisting: Quantity,
        clause: Clause,
        detail: str | None = None,
        remedy: str | None = None,
        display_unit: str | None = None,
    ) -> "Check":
        """Build a check where utilisation is ``acting / resisting``.

        A non-positive resistance is reported as a failure with an infinite
        utilisation rather than raising, so that a report can list it alongside
        the other results.
        """
        r = float(resisting.to(acting.units).magnitude)
        a = float(acting.magnitude)
        if r <= 0.0:
            ratio = float("inf")
        else:
            ratio = a / r
        return Check(
            name=name,
            acting=acting,
            resisting=resisting,
            utilisation=ratio,
            clause=clause,
            status=(
                CheckStatus.PASS
                if ratio <= 1.0 + FLOAT_TOLERANCE
                else CheckStatus.FAIL
            ),
            detail=detail,
            remedy=remedy,
        )

    @property
    def passed(self) -> bool:
        return self.status is CheckStatus.PASS

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "utilisation": self.utilisation,
            "acting": fmt(self.acting),
            "resisting": fmt(self.resisting),
            "clause": self.clause.to_dict(),
            "detail": self.detail,
            "remedy": self.remedy,
        }


@dataclass
class VerificationReport:
    """The set of checks performed on one element."""

    element: str
    checks: list[Check] = field(default_factory=list)

    def add(self, check: Check) -> Check:
        self.checks.append(check)
        return check

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def governing(self) -> Check | None:
        """The check with the highest utilisation — the one that governs."""
        if not self.checks:
            return None
        return max(self.checks, key=lambda c: c.utilisation)

    @property
    def max_utilisation(self) -> float:
        g = self.governing
        return g.utilisation if g else 0.0

    def failures(self) -> list[Check]:
        """Failing checks, most utilised first.

        The UI lists these before anything else — cahier des charges section 6.8.
        """
        return sorted(
            (c for c in self.checks if not c.passed),
            key=lambda c: c.utilisation,
            reverse=True,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "element": self.element,
            "passed": self.passed,
            "max_utilisation": self.max_utilisation,
            "checks": [c.to_dict() for c in self.checks],
        }
