"""The note de calcul, assembled mechanically from the journals.

Interdiction 1 of the cahier des charges — *never let a language model produce
a calculation result* — is not a policy here, it is the shape of the code. This
module owns no arithmetic and writes no prose about numbers. Every figure that
reaches the page comes from a :class:`~eurostruct_engine.traceability.CalcStep`
or a :class:`~eurostruct_engine.verification.Check` that a calculation module
already produced, and travels with the clause it came from.

The consequence worth stating: there is no code path from a number to the page
that does not pass through a journal entry. A section cannot contain a value
that no module computed, because a section is *built from* the journal rather
than written alongside it. :func:`~eurostruct_engine.note.render.render_html`
walks this model and emits markup; it has no access to the design functions.

What a note must carry, and why each is refused if absent
---------------------------------------------------------
* **The mandatory notice** (§12, interdiction 8). A note without it claims an
  authority the software does not have.
* **The regulatory framework** (interdiction 4). A Spanish study verified under
  the Eurocodes alone is not verified: the Código Estructural, the CTE and
  NCSE-02 are what bind. The note says which framework applied.
* **The engine version and the parameter set** (§8.2). A result nobody can
  reproduce is not defensible ten years later, and a décennale runs for ten.
* **The unverified parameters** (interdiction 2). A note built on values nobody
  has read in the published annex must say so, in the note, not in a log.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable, Sequence

from ..legal import SOFTWARE_ROLE, Language, notice
from ..traceability import CalcStep, Journal
from ..verification import Check, VerificationReport
from ..version import ENGINE_VERSION

__all__ = [
    "NoteSection",
    "CalculationNote",
    "section_from_design",
]


@dataclass(frozen=True, slots=True)
class NoteSection:
    """One calculation, as it appears in the note.

    Holds no values of its own: the journal and the report are the ones the
    calculation module produced, passed through unchanged.
    """

    title: str
    #: The standard and clause range this section works under, e.g.
    #: "EN 1992-1-1 §6.1".
    basis: str
    journal: Journal
    report: VerificationReport | None = None
    #: Assumptions the module made that a reader must be able to challenge —
    #: "z = 0,9 d", "cot θ = 2,5 chosen by the engineer". Stated, not hidden in
    #: a formula.
    assumptions: tuple[str, ...] = ()

    @property
    def steps(self) -> tuple[CalcStep, ...]:
        return tuple(self.journal.steps)

    @property
    def checks(self) -> tuple[Check, ...]:
        return () if self.report is None else tuple(self.report.checks)

    @property
    def passed(self) -> bool | None:
        """``None`` when the section carries no verification, not ``True``.

        A section that checks nothing has not passed anything, and a reader
        must not be able to read a green tick into silence.
        """
        return None if self.report is None else self.report.passed

    def clauses(self) -> tuple[str, ...]:
        """Every clause this section cites, in first-appearance order."""
        seen: list[str] = []
        for step in self.steps:
            if step.clause is not None:
                cite = step.clause.cite()
                if cite not in seen:
                    seen.append(cite)
        for check in self.checks:
            cite = check.clause.cite()
            if cite not in seen:
                seen.append(cite)
        return tuple(seen)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "basis": self.basis,
            "assumptions": list(self.assumptions),
            "journal": self.journal.to_dict(),
            "verification": None if self.report is None else self.report.to_dict(),
            "clauses": list(self.clauses()),
            "passed": self.passed,
        }


@dataclass(frozen=True, slots=True)
class CalculationNote:
    """A complete note de calcul for one element.

    :param ndp_summary: what
        :meth:`~eurostruct_engine.ndp.registry.ParameterSet.summary` returned
        for the calculation. Carries the country, the annexes with their
        editions, the regulatory framework and the unverified keys.
    """

    project: str
    element: str
    sections: tuple[NoteSection, ...]
    ndp_summary: dict[str, Any]
    issued_on: date
    language: Language = Language.FR
    engine_version: str = ENGINE_VERSION
    #: Free text the engineer wrote. Never a number: an observation about the
    #: study, not a result. Kept apart from the sections for exactly that
    #: reason — nothing here is traceable to a clause.
    remarks: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.sections:
            raise ValueError(
                "une note de calcul sans aucune section ne verifie rien. "
                "Emettre un document vide reviendrait a attester le neant."
            )
        if not self.ndp_summary.get("regulatory_framework"):
            raise ValueError(
                "la note doit declarer le cadre reglementaire applique "
                "(interdiction 4): un pays n'est pas toujours « Eurocode pur »."
            )

    @property
    def notice(self) -> str:
        """The mandatory validation notice, in the note's language."""
        return notice(self.language)

    @property
    def software_role(self) -> str:
        return SOFTWARE_ROLE[self.language]

    @property
    def passed(self) -> bool:
        """Whether every section that verifies something is satisfied."""
        return all(s.passed for s in self.sections if s.passed is not None)

    @property
    def max_utilisation(self) -> float:
        """The worst utilisation across the whole note, 0 if nothing checked."""
        ratios = [
            c.utilisation for s in self.sections for c in s.checks
        ]
        return max(ratios) if ratios else 0.0

    @property
    def unverified_parameters(self) -> tuple[str, ...]:
        """National values nobody has read in the published annex.

        Printed in the note itself. A study resting on unread values is not
        wrong — it is unverified, and the difference has to be visible to
        whoever signs.
        """
        return tuple(self.ndp_summary.get("unverified", ()))

    def clauses(self) -> tuple[str, ...]:
        seen: list[str] = []
        for s in self.sections:
            for c in s.clauses():
                if c not in seen:
                    seen.append(c)
        return tuple(seen)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project": self.project,
            "element": self.element,
            "issued_on": self.issued_on.isoformat(),
            "language": self.language.value,
            "engine_version": self.engine_version,
            "passed": self.passed,
            "max_utilisation": self.max_utilisation,
            "sections": [s.to_dict() for s in self.sections],
            "ndp": self.ndp_summary,
            "unverified_parameters": list(self.unverified_parameters),
            "clauses": list(self.clauses()),
            "remarks": list(self.remarks),
            "notice": self.notice,
            "software_role": self.software_role,
        }


def section_from_design(
    design: Any,
    *,
    title: str,
    basis: str,
    assumptions: Sequence[str] = (),
) -> NoteSection:
    """Build a section from any design result carrying a journal.

    Deliberately duck-typed on ``journal`` and ``report``: the three EC2
    modules produce different result classes and the note has no business
    knowing which is which. What it needs is a journal — and a result without
    one could not be written up anyway.
    """
    journal = getattr(design, "journal", None)
    if journal is None:
        raise TypeError(
            f"{type(design).__name__} ne porte pas de journal: impossible d'en "
            "faire une section de note. Un resultat sans journal n'a pas de "
            "tracabilite, donc rien a imprimer."
        )
    return NoteSection(
        title=title,
        basis=basis,
        journal=journal,
        report=getattr(design, "report", None),
        assumptions=tuple(assumptions),
    )
