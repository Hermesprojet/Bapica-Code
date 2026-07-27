"""Reference cases as first-class validation objects — TICKET 2.1.

The third of the three layers kept apart by EPIC 1: Eurocode formulas live in
the calculation modules, national values in :mod:`eurostruct_engine.ndp`, and
the cases used to prove the engine right live here.

A reference case is a *contract with a document*: it names the source, records
the inputs read from it, the outputs it publishes, and the tolerance within
which the engine must reproduce them. Expected and computed outputs are stored
separately and never merged, so a case cannot silently be "fixed" by copying
the engine's own answer into the expectation.

Honesty of the shipped library
------------------------------
``source_type`` distinguishes what a case actually rests on:

``OFFICIAL_WORKED_EXAMPLE``
    An example published by a standards body or in an Eurocode guide.

``DESIGN_EXAMPLE``
    A worked example from professional literature.

``MANUAL_REFERENCE``
    A calculation performed independently of the engine — by hand, or by a
    separate implementation using a different numerical method. Legitimate, and
    weaker than a published example: it proves internal consistency and correct
    algebra, not agreement with the profession.

A case whose expected values are not yet available carries
``AWAITING_SOURCE``. It is declared, tracked and reported, but it does not
pretend to validate anything. Inventing a citation would be worse than the gap.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence

__all__ = [
    "ReferenceSourceType",
    "ReferenceStatus",
    "SourceDocument",
    "ToleranceRule",
    "ReferenceCase",
    "Delta",
    "ReferenceResult",
]


class ReferenceSourceType(str, Enum):
    OFFICIAL_WORKED_EXAMPLE = "official_worked_example"
    DESIGN_EXAMPLE = "design_example"
    MANUAL_REFERENCE = "manual_reference"


class ReferenceStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    #: Declared, but the published expected values have not been entered yet.
    AWAITING_SOURCE = "awaiting_source"
    #: The engine module this case exercises does not exist yet.
    AWAITING_MODULE = "awaiting_module"
    #: The case refused to run for a reason that is itself the expected outcome.
    REFUSED = "refused"
    NOT_RUN = "not_run"


@dataclass(frozen=True, slots=True)
class SourceDocument:
    """Where the expected values come from. Enough to find the page again."""

    title: str
    publisher: str | None = None
    edition: str | None = None
    #: Example or section identifier inside the document.
    locator: str | None = None
    isbn_or_url: str | None = None
    notes: str | None = None

    def cite(self) -> str:
        parts = [self.title]
        for extra in (self.publisher, self.edition, self.locator):
            if extra:
                parts.append(extra)
        return " — ".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "publisher": self.publisher,
            "edition": self.edition,
            "locator": self.locator,
            "isbn_or_url": self.isbn_or_url,
            "notes": self.notes,
            "cite": self.cite(),
        }


@dataclass(frozen=True, slots=True)
class ToleranceRule:
    """How closely one output must match.

    Cahier des charges §8.2 sets 1 % as the ceiling for a reference case. A rule
    may tighten that — an analytically exact expectation should be matched to
    machine precision, not to 1 %.

    :param output: output key, or ``"*"`` as the fallback for any output
        without a specific rule.
    :param rel: relative tolerance.
    :param abs: absolute tolerance, in the output's own unit.
    """

    output: str
    rel: float | None = None
    abs: float | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.rel is None and self.abs is None:
            raise ValueError(
                f"la regle de tolerance pour '{self.output}' doit fixer rel ou abs"
            )
        if self.rel is not None and self.rel > 0.01:
            raise ValueError(
                f"tolerance relative {self.rel} pour '{self.output}' au-dela du "
                "plafond de 1 % fixe par le cahier des charges §8.2"
            )

    def accepts(self, expected: float, computed: float) -> tuple[bool, float, float]:
        """:returns: ``(within, abs_diff, rel_diff)``.

        A relative tolerance means nothing against an expected value of zero:
        the ratio is either ``inf`` or undefined, whatever the agreement. A
        case with a legitimately null output — the additional tensile force of
        §6.2.3(7) when no truss carries the shear — was therefore reported as
        out of tolerance while matching exactly, and would have stayed red for
        ever.

        So an expected zero is judged on the ABSOLUTE difference, and only an
        exact zero passes. That keeps the guard: 5 against an expected 0 is
        still a failure, which a lenient relative rule could never have caught
        either.
        """
        abs_diff = abs(computed - expected)
        if expected == 0.0:
            rel_diff = 0.0 if abs_diff == 0.0 else math.inf
            ok = abs_diff == 0.0 or (self.abs is not None and abs_diff <= self.abs)
            return ok, abs_diff, rel_diff

        rel_diff = abs_diff / abs(expected)
        ok = False
        if self.abs is not None and abs_diff <= self.abs:
            ok = True
        if self.rel is not None and rel_diff <= self.rel:
            ok = True
        return ok, abs_diff, rel_diff

    def to_dict(self) -> dict[str, Any]:
        return {
            "output": self.output, "rel": self.rel, "abs": self.abs,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class ReferenceCase:
    """One validation case, replayable and comparable."""

    reference_id: str
    title: str
    #: Clauses this case exercises, e.g. ``("EN 1992-1-1 §6.1",)``.
    normative_scope: tuple[str, ...]
    #: Countries the case is meaningful for; ``("*",)`` when independent of the
    #: National Annex.
    country_scope: tuple[str, ...]
    source_type: ReferenceSourceType
    source_document: SourceDocument
    #: Which engine entry point replays it — see :mod:`.harness`.
    harness: str
    input_dataset: Mapping[str, Any]
    #: Published values. Empty when the case is ``awaiting_source``.
    expected_outputs: Mapping[str, float]
    tolerance_rules: tuple[ToleranceRule, ...]
    #: Set when the expected behaviour is a refusal rather than a number.
    expect_refusal: str | None = None
    notes: str | None = None

    def tolerance_for(self, output: str) -> ToleranceRule | None:
        for rule in self.tolerance_rules:
            if rule.output == output:
                return rule
        for rule in self.tolerance_rules:
            if rule.output == "*":
                return rule
        return None

    @property
    def has_expectations(self) -> bool:
        return bool(self.expected_outputs) or self.expect_refusal is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "reference_id": self.reference_id,
            "title": self.title,
            "normative_scope": list(self.normative_scope),
            "country_scope": list(self.country_scope),
            "source_type": self.source_type.value,
            "source_document": self.source_document.to_dict(),
            "harness": self.harness,
            "input_dataset": dict(self.input_dataset),
            "expected_outputs": dict(self.expected_outputs),
            "tolerance_rules": [r.to_dict() for r in self.tolerance_rules],
            "expect_refusal": self.expect_refusal,
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class Delta:
    """Difference on one output. Journalised whether it passes or not."""

    output: str
    expected: float
    computed: float
    abs_diff: float
    rel_diff: float
    tolerance: ToleranceRule | None
    within: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "output": self.output,
            "expected": self.expected,
            "computed": self.computed,
            "abs_diff": self.abs_diff,
            "rel_diff": self.rel_diff,
            "tolerance": self.tolerance.to_dict() if self.tolerance else None,
            "within": self.within,
        }

    def render(self) -> str:
        flag = "OK " if self.within else "ECART"
        return (
            f"    [{flag}] {self.output}: attendu {self.expected!r}, "
            f"calcule {self.computed!r} "
            f"(ecart {self.abs_diff:.6g}, soit {self.rel_diff * 100:.4f} %)"
        )


@dataclass(frozen=True, slots=True)
class ReferenceResult:
    """Outcome of replaying one case.

    ``expected_outputs`` and ``computed_outputs`` stay in separate fields — see
    the module docstring.
    """

    case: ReferenceCase
    status: ReferenceStatus
    computed_outputs: Mapping[str, float] = field(default_factory=dict)
    delta_report: tuple[Delta, ...] = ()
    message: str | None = None

    @property
    def passed(self) -> bool:
        return self.status is ReferenceStatus.PASSED

    @property
    def blocking(self) -> bool:
        """Whether this outcome must fail CI.

        A case awaiting its source or its module is a *gap*, reported but not a
        regression. A case that ran and drifted is a regression.
        """
        return self.status is ReferenceStatus.FAILED

    def failures(self) -> tuple[Delta, ...]:
        return tuple(d for d in self.delta_report if not d.within)

    def to_dict(self) -> dict[str, Any]:
        return {
            "reference_id": self.case.reference_id,
            "title": self.case.title,
            "source_type": self.case.source_type.value,
            "source": self.case.source_document.cite(),
            "normative_scope": list(self.case.normative_scope),
            "status": self.status.value,
            "expected_outputs": dict(self.case.expected_outputs),
            "computed_outputs": dict(self.computed_outputs),
            "delta_report": [d.to_dict() for d in self.delta_report],
            "message": self.message,
        }

    def render(self) -> str:
        head = f"  [{self.status.value.upper()}] {self.case.reference_id} — {self.case.title}"
        lines = [head]
        if self.message:
            lines.append(f"    {self.message}")
        for d in self.delta_report:
            lines.append(d.render())
        return "\n".join(lines)


def sequence_of(rules: Sequence[ToleranceRule]) -> tuple[ToleranceRule, ...]:
    return tuple(rules)
