"""Traceability primitives: clauses, provenance, calculation journal.

This module implements the blocking requirement of cahier des charges
section 8.1:

    "Un utilisateur doit pouvoir cliquer sur n'importe quel nombre de la note
     de calcul et remonter jusqu'a sa source."

Every number produced by the engine is a :class:`CalcStep` carrying

* the exact normative clause it comes from,
* the symbolic formula and the same formula with the numbers substituted,
* the symbols of the upstream steps it depends on,
* for inputs, a :class:`Provenance` saying whether the value was typed by the
  user, extracted from a document (with page and bounding box), or read from
  the National Annex parameter set.

The steps of a calculation therefore form a directed acyclic graph that the
frontend can render as an expandable tree, and the PDF generator can render as
"formule symbolique -> application numerique -> resultat -> clause".

Nothing in this module computes anything. It records.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Sequence

from .units import Quantity, fmt, magnitude

__all__ = [
    "Clause",
    "EC0",
    "EC1",
    "EC2",
    "EC3",
    "EC5",
    "EC7",
    "EC8",
    "ProvenanceKind",
    "Provenance",
    "CalcStep",
    "Journal",
]


# --------------------------------------------------------------------------
# Normative clauses
# --------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class Clause:
    """A citable reference to a normative clause.

    :param standard: e.g. ``"EN 1992-1-1"``.
    :param clause: e.g. ``"§6.2.3(3)"``.
    :param equation: e.g. ``"(6.8)"``, when the value comes from a numbered
        equation.
    :param national_note: the National Annex qualification, when the clause is
        nationally determined, e.g.
        ``"AN BE (NBN EN 1992-1-1 ANB): cot θ ∈ [1,0 ; 2,5]"``.
    """

    standard: str
    clause: str
    equation: str | None = None
    national_note: str | None = None

    def cite(self) -> str:
        """Render the citation as it appears in the note de calcul."""
        parts = [f"{self.standard} {self.clause}"]
        if self.equation:
            parts.append(f"eq. {self.equation}")
        text = ", ".join(parts)
        if self.national_note:
            text += f" — {self.national_note}"
        return text

    def to_dict(self) -> dict[str, Any]:
        return {
            "standard": self.standard,
            "clause": self.clause,
            "equation": self.equation,
            "national_note": self.national_note,
            "cite": self.cite(),
        }


def _clause_factory(standard: str):
    def make(
        clause: str,
        equation: str | None = None,
        national_note: str | None = None,
    ) -> Clause:
        return Clause(standard, clause, equation, national_note)

    return make


# Convenience constructors for the standards covered so far.
EC0 = _clause_factory("EN 1990")
EC1 = _clause_factory("EN 1991-1-1")
EC2 = _clause_factory("EN 1992-1-1")
EC3 = _clause_factory("EN 1993-1-1")
EC5 = _clause_factory("EN 1995-1-1")
EC7 = _clause_factory("EN 1997-1")
EC8 = _clause_factory("EN 1998-1")


# --------------------------------------------------------------------------
# Provenance of input values
# --------------------------------------------------------------------------
class ProvenanceKind(str, Enum):
    """Where an input value came from.

    ``DOCUMENT_EXTRACTION`` values are proposals produced by the ingestion
    service. Cahier des charges section 3 and 6.3: they must have been
    confirmed by a human before reaching the engine. The orchestrator is
    responsible for that gate; the engine records which values carry that
    origin so the note de calcul can state it.
    """

    USER_INPUT = "user_input"
    DOCUMENT_EXTRACTION = "document_extraction"
    NATIONAL_ANNEX = "national_annex"
    STANDARD_CONSTANT = "standard_constant"
    DERIVED = "derived"


@dataclass(frozen=True, slots=True)
class Provenance:
    """Origin of a value that enters the calculation."""

    kind: ProvenanceKind
    detail: str
    document_id: str | None = None
    page: int | None = None
    #: [x0, y0, x1, y1] in PDF points, so the UI can highlight the source.
    bbox: tuple[float, float, float, float] | None = None
    ndp_key: str | None = None
    confirmed_by: str | None = None
    confirmed_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "detail": self.detail,
            "document_id": self.document_id,
            "page": self.page,
            "bbox": list(self.bbox) if self.bbox else None,
            "ndp_key": self.ndp_key,
            "confirmed_by": self.confirmed_by,
            "confirmed_at": self.confirmed_at,
        }

    @staticmethod
    def user(detail: str) -> "Provenance":
        return Provenance(ProvenanceKind.USER_INPUT, detail)

    @staticmethod
    def standard(detail: str) -> "Provenance":
        return Provenance(ProvenanceKind.STANDARD_CONSTANT, detail)

    @staticmethod
    def national_annex(key: str, detail: str) -> "Provenance":
        return Provenance(ProvenanceKind.NATIONAL_ANNEX, detail, ndp_key=key)


# --------------------------------------------------------------------------
# Calculation steps
# --------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class CalcStep:
    """One traceable line of a calculation.

    :param symbol: unique key inside a journal, e.g. ``"f_cd"``. Used as the
        anchor a user clicks on in the note de calcul.
    :param description: what the quantity is, in the note's language.
    :param value: the resulting quantity.
    :param clause: the normative reference justifying the step.
    :param latex: symbolic formula, LaTeX, without numbers.
    :param numeric: the same formula with the input numbers substituted.
    :param depends_on: symbols of the upstream steps, forming the trace graph.
    :param provenance: set for input steps; ``None`` for derived steps.
    """

    symbol: str
    description: str
    value: Quantity
    clause: Clause | None = None
    latex: str | None = None
    numeric: str | None = None
    depends_on: tuple[str, ...] = ()
    provenance: Provenance | None = None
    display_unit: str | None = None

    def to_dict(self) -> dict[str, Any]:
        unit = self.display_unit or f"{self.value.units:~P}"
        return {
            "symbol": self.symbol,
            "description": self.description,
            "value": magnitude(self.value, str(self.value.units)),
            "unit": unit,
            "formatted": fmt(self.value, self.display_unit),
            "clause": self.clause.to_dict() if self.clause else None,
            "latex": self.latex,
            "numeric": self.numeric,
            "depends_on": list(self.depends_on),
            "provenance": self.provenance.to_dict() if self.provenance else None,
        }


@dataclass
class Journal:
    """Ordered, append-only record of a calculation.

    The journal is the audit trail that the PDF generator walks to produce the
    "verifications element par element" section, and that the API returns so the
    frontend can make every number clickable.
    """

    title: str
    steps: list[CalcStep] = field(default_factory=list)
    _index: dict[str, int] = field(default_factory=dict, repr=False)

    def add(self, step: CalcStep) -> Quantity:
        """Append *step* and return its value, so calls can be inlined.

        :raises KeyError: if the symbol is already used, or if a declared
            dependency has not been recorded yet. Both indicate a bug in the
            calling module, and both would silently break traceability.
        """
        if step.symbol in self._index:
            raise KeyError(f"symbole deja utilise dans le journal: {step.symbol}")
        for dep in step.depends_on:
            if dep not in self._index:
                raise KeyError(
                    f"l'etape '{step.symbol}' declare dependre de '{dep}', "
                    "qui n'a pas ete enregistre avant elle"
                )
        self._index[step.symbol] = len(self.steps)
        self.steps.append(step)
        return step.value

    def input(
        self,
        symbol: str,
        description: str,
        value: Quantity,
        provenance: Provenance,
        clause: Clause | None = None,
        display_unit: str | None = None,
    ) -> Quantity:
        """Record an input value together with where it came from."""
        return self.add(
            CalcStep(
                symbol=symbol,
                description=description,
                value=value,
                clause=clause,
                provenance=provenance,
                display_unit=display_unit,
            )
        )

    def step(
        self,
        symbol: str,
        description: str,
        value: Quantity,
        clause: Clause,
        latex: str,
        numeric: str,
        depends_on: Sequence[str] = (),
        display_unit: str | None = None,
    ) -> Quantity:
        """Record a derived value with its symbolic and numeric formulas."""
        return self.add(
            CalcStep(
                symbol=symbol,
                description=description,
                value=value,
                clause=clause,
                latex=latex,
                numeric=numeric,
                depends_on=tuple(depends_on),
                display_unit=display_unit,
            )
        )

    def get(self, symbol: str) -> CalcStep:
        return self.steps[self._index[symbol]]

    def symbols(self) -> list[str]:
        return [s.symbol for s in self.steps]

    def clauses(self) -> list[str]:
        """Every distinct clause cited, in first-citation order."""
        seen: list[str] = []
        for s in self.steps:
            if s.clause is not None:
                c = s.clause.cite()
                if c not in seen:
                    seen.append(c)
        return seen

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "steps": [s.to_dict() for s in self.steps],
            "clauses": self.clauses(),
        }

    def to_json(self) -> str:
        """Deterministic JSON serialization (stable key order)."""
        return json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False, indent=2)
