"""Types of the National Annex import pipeline.

Design invariant, and the reason this package exists at all:

    **An extraction candidate can never be confirmed.**

There is no code path from a PDF to a ``confirmed`` national parameter. The
extractor produces *candidates*; only a :class:`ReviewDecision` signed by a
named engineer, at a recorded time, against a recorded page of a recorded
document, produces a value the engine will use in strict mode.

That is not a convention: :class:`ExtractionCandidate` has no status field to
set, and :func:`ndp_import.emit.to_engine_records` refuses to emit a confirmed
record without the four pieces of evidence the cahier des charges requires
(official source, document reference, named verifier, timestamp).

Why this package is separate from ``eurostruct_engine``
------------------------------------------------------
It depends on ``pdfplumber``. The engine's dependency audit
(``engine/scripts/audit_engine_dependencies.py``) allows fourteen packages and
refuses everything else, so a PDF parser cannot live inside the calculation
core. The separation is enforced by CI, not by discipline: the importer writes
JSON, the engine reads JSON, and they never share a process.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Sequence

__all__ = [
    "DocumentStatus",
    "SourceDocument",
    "ExtractionCandidate",
    "ExtractionRun",
    "ReviewOutcome",
    "ReviewDecision",
    "ReviewedParameter",
    "EXTRACTOR_VERSION",
]

#: Bumped whenever extraction behaviour changes, so a candidate can be traced
#: back to the code that produced it.
EXTRACTOR_VERSION = "0.1.0"


class DocumentStatus(str, Enum):
    """Where a catalogue entry stands."""

    NOT_ACQUIRED = "not_acquired"
    ACQUIRED = "acquired"
    EXTRACTED = "extracted"
    REVIEWED = "reviewed"


class DocumentRole(str, Enum):
    """What a document *is*, normatively — interdiction 2 made structural.

    The distinction matters more than it looks. "NF EN 1991-1-1" and
    "NBN EN 1991-1-3" are the base Eurocode adopted as a national standard:
    they carry the Eurocode's own *recommended* values, in their Notes. The
    National Annex is a different document, and it is the only one that fixes
    what a country actually adopted.

    A value read from a base Eurocode is therefore ``en_recommended``, never
    ``national_annex`` — and since the database refuses ``confirmed`` unless
    ``source_type = 'national_annex'``, such a value can never become usable in
    strict mode. That is the intended behaviour, not a limitation.
    """

    #: The Eurocode itself, in any national adoption (EN, NF EN, NBN EN, DIN EN).
    #: Contains recommended values. Cannot yield a confirmed national parameter.
    BASE_EUROCODE = "base_eurocode"
    #: The National Annex proper (ANB, /NA, Anexo Nacional). The only document
    #: that fixes nationally determined parameters.
    NATIONAL_ANNEX = "national_annex"
    #: National regulation outside the Eurocode system (CTE, Codigo
    #: Estructural, NCSE-02, MVV TB, DTU).
    NATIONAL_REGULATION = "national_regulation"
    #: Guidance, worked examples, technical articles (CSTC/WTCB, JRC, CSTB).
    #: Useful to a reviewer, never a source of an enforceable value.
    SECONDARY_PUBLICATION = "secondary_publication"

    @property
    def can_fix_national_parameters(self) -> bool:
        return self in (
            DocumentRole.NATIONAL_ANNEX, DocumentRole.NATIONAL_REGULATION
        )


@dataclass(frozen=True, slots=True)
class SourceDocument:
    """An official document deposited into the importer.

    The metadata is **declared by the depositing engineer**, not guessed from
    the file. An edition read out of a PDF header is a guess; an edition typed
    by the person holding the document is a statement they answer for.
    """

    doc_id: str                      # sha256 of the file
    filename: str
    #: What this document is normatively. Declared by the depositing engineer,
    #: because a filename saying "NBN" does not make a document an ANB.
    role: DocumentRole
    country_code: str
    standard_family: str
    part: str
    reference: str                   # "NBN EN 1992-1-1 ANB"
    publisher: str
    edition: str
    effective_from: date
    language: str
    page_count: int
    deposited_by: str
    deposited_at: str
    effective_to: date | None = None
    notes: str | None = None

    @staticmethod
    def digest(path: Path) -> str:
        """sha256 of the file, so a candidate can never be attached to a
        document that was silently swapped."""
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()

    @property
    def standard(self) -> str:
        return f"{self.standard_family}-{self.part}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "filename": self.filename,
            "role": self.role.value,
            "can_fix_national_parameters": self.role.can_fix_national_parameters,
            "country_code": self.country_code,
            "standard_family": self.standard_family,
            "part": self.part,
            "standard": self.standard,
            "reference": self.reference,
            "publisher": self.publisher,
            "edition": self.edition,
            "effective_from": self.effective_from.isoformat(),
            "effective_to": self.effective_to.isoformat() if self.effective_to else None,
            "language": self.language,
            "page_count": self.page_count,
            "deposited_by": self.deposited_by,
            "deposited_at": self.deposited_at,
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class ExtractionCandidate:
    """A *proposal* read out of a document. Never a value the engine will use.

    Note what is absent: any status field. A candidate has no way to declare
    itself verified.

    :param parsed_value: ``None`` when the extractor located the clause but
        could not read a number from it. That is a normal, useful outcome: it
        tells the reviewer where to look. It is never filled with a guess.
    :param confidence: informational only. It orders the review queue; it opens
        no automatic path to acceptance.
    """

    candidate_id: str
    doc_id: str
    parameter_name: str
    page: int                        # 1-based, as printed in the document
    snippet: str                     # surrounding text, for the reviewer
    raw_value: str | None = None     # the numeric token as written, "1,0"
    parsed_value: float | None = None
    unit: str = "dimensionless"
    clause: str | None = None
    bbox: tuple[float, float, float, float] | None = None
    pattern_id: str | None = None
    confidence: float = 0.0
    extractor_version: str = EXTRACTOR_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "doc_id": self.doc_id,
            "parameter_name": self.parameter_name,
            "page": self.page,
            "snippet": self.snippet,
            "raw_value": self.raw_value,
            "parsed_value": self.parsed_value,
            "unit": self.unit,
            "clause": self.clause,
            "bbox": list(self.bbox) if self.bbox else None,
            "pattern_id": self.pattern_id,
            "confidence": self.confidence,
            "extractor_version": self.extractor_version,
        }


@dataclass(frozen=True, slots=True)
class ExtractionRun:
    """One pass of the extractor over one document."""

    doc: SourceDocument
    candidates: tuple[ExtractionCandidate, ...]
    run_at: str
    extractor_version: str = EXTRACTOR_VERSION
    #: Parameters the catalogue expects from this document and for which the
    #: extractor found nothing. Reported, never filled in.
    not_found: tuple[str, ...] = ()
    #: Pages excluded because a vertical watermark is interleaved with their
    #: glyphs. Carried explicitly so ``not_found`` cannot be read as "the annex
    #: is silent on this" when the truth is "we refused to read that page".
    #: A reviewer opens these by hand.
    pages_skipped_overlay: tuple[int, ...] = ()

    def by_parameter(self) -> dict[str, list[ExtractionCandidate]]:
        out: dict[str, list[ExtractionCandidate]] = {}
        for c in self.candidates:
            out.setdefault(c.parameter_name, []).append(c)
        for lst in out.values():
            lst.sort(key=lambda c: (-c.confidence, c.page))
        return dict(sorted(out.items()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "document": self.doc.to_dict(),
            "run_at": self.run_at,
            "extractor_version": self.extractor_version,
            "candidates": [c.to_dict() for c in self.candidates],
            "not_found": list(self.not_found),
            "pages_skipped_overlay": list(self.pages_skipped_overlay),
        }


class ReviewOutcome(str, Enum):
    """What the engineer decided about a candidate."""

    #: The extracted value is what the annex says.
    ACCEPTED = "accepted"
    #: The annex says something else; the engineer supplies the value.
    CORRECTED = "corrected"
    #: Not a national parameter, or the extractor misread the clause.
    REJECTED = "rejected"
    #: The engineer could not decide — flagged for a second reader.
    DEFERRED = "deferred"


@dataclass(frozen=True, slots=True)
class ReviewDecision:
    """A named engineer's decision about one candidate.

    This is the only thing that can turn a proposal into a usable value, and it
    carries all four pieces of evidence §9 requires: the official source and
    its document reference come from the :class:`SourceDocument`, the verifier
    and the timestamp from here.
    """

    candidate_id: str
    outcome: ReviewOutcome
    verified_by: str                 # named engineer, not a user id alone
    verified_at: str                 # ISO 8601
    #: Required for ACCEPTED and CORRECTED. The value that enters the engine.
    final_value: float | None = None
    unit: str = "dimensionless"
    #: The page the engineer actually read, which may differ from the
    #: extractor's guess.
    source_page: int | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        if self.outcome in (ReviewOutcome.ACCEPTED, ReviewOutcome.CORRECTED):
            if self.final_value is None:
                raise ValueError(
                    f"decision '{self.outcome.value}' sur {self.candidate_id} sans "
                    "final_value: une valeur acceptee doit etre explicite."
                )
            if not self.verified_by.strip():
                raise ValueError(
                    f"decision '{self.outcome.value}' sur {self.candidate_id} sans "
                    "verificateur nomme. Un identifiant technique ne suffit pas: "
                    "inscrire le nom de l'ingenieur qui engage sa responsabilite."
                )
            try:
                datetime.fromisoformat(self.verified_at)
            except ValueError as exc:
                raise ValueError(
                    f"verified_at invalide sur {self.candidate_id}: "
                    f"{self.verified_at!r} (ISO 8601 attendu)"
                ) from exc

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "outcome": self.outcome.value,
            "verified_by": self.verified_by,
            "verified_at": self.verified_at,
            "final_value": self.final_value,
            "unit": self.unit,
            "source_page": self.source_page,
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True)
class ReviewedParameter:
    """A candidate plus the decision taken on it, ready to be emitted."""

    candidate: ExtractionCandidate
    decision: ReviewDecision
    document: SourceDocument

    @property
    def confirmed(self) -> bool:
        return self.decision.outcome in (
            ReviewOutcome.ACCEPTED, ReviewOutcome.CORRECTED
        )

    @property
    def value(self) -> float | None:
        return self.decision.final_value

    @property
    def source_page(self) -> int:
        return self.decision.source_page or self.candidate.page
