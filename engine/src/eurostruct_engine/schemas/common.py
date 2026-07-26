"""Shared wire types between the frontend, the orchestrator and the engine.

Design rule: **no bare number ever crosses a boundary**. Every physical value
travels as a :class:`QuantityDTO` carrying its unit, so a millimetre can never
be silently read as a metre. This is the wire-level counterpart of the Pint
typing used inside the engine.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "Strict",
    "QuantityDTO",
    "CountryCode",
    "DesignSituationDTO",
    "ProvenanceKindDTO",
    "ProvenanceDTO",
    "ClauseDTO",
    "CalcStepDTO",
    "JournalDTO",
    "CheckStatusDTO",
    "CheckDTO",
    "VerificationReportDTO",
    "NdpStatusDTO",
    "NdpEntryDTO",
    "NdpSummaryDTO",
    "EngineErrorDTO",
]


class Strict(BaseModel):
    """Base model: unknown fields are rejected rather than ignored.

    A typo in a payload key must fail loudly. Silently dropping an input is how
    a calculation ends up run on the wrong data.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)


class QuantityDTO(Strict):
    """A physical quantity with an explicit unit."""

    value: float
    unit: str = Field(
        description="Pint-parsable unit, e.g. 'mm', 'kN*m', 'MPa', 'dimensionless'.",
        examples=["mm", "kN*m", "MPa"],
    )


CountryCode = Literal["BE", "FR", "ES", "DE"]


class DesignSituationDTO(str, Enum):
    PERSISTENT = "persistent"
    TRANSIENT = "transient"
    ACCIDENTAL = "accidental"
    SEISMIC = "seismic"


class ProvenanceKindDTO(str, Enum):
    USER_INPUT = "user_input"
    DOCUMENT_EXTRACTION = "document_extraction"
    NATIONAL_ANNEX = "national_annex"
    STANDARD_CONSTANT = "standard_constant"
    DERIVED = "derived"


class ProvenanceDTO(Strict):
    """Where a value came from.

    ``document_extraction`` values must already have been confirmed by a human
    before the orchestrator submits them: ``confirmed_by`` and ``confirmed_at``
    are how the engine's output can state that the gate was passed.
    """

    kind: ProvenanceKindDTO
    detail: str
    document_id: str | None = None
    page: int | None = None
    bbox: tuple[float, float, float, float] | None = Field(
        default=None,
        description="[x0, y0, x1, y1] in PDF points, so the UI can highlight the source.",
    )
    ndp_key: str | None = None
    confirmed_by: str | None = None
    confirmed_at: str | None = None


class ClauseDTO(Strict):
    standard: str
    clause: str
    equation: str | None = None
    national_note: str | None = None
    cite: str


class CalcStepDTO(Strict):
    """One traceable line of the calculation — see section 8.1."""

    symbol: str
    description: str
    value: float
    unit: str
    formatted: str
    clause: ClauseDTO | None = None
    latex: str | None = None
    numeric: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    provenance: ProvenanceDTO | None = None


class JournalDTO(Strict):
    title: str
    steps: list[CalcStepDTO]
    clauses: list[str]


class CheckStatusDTO(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    NOT_APPLICABLE = "not_applicable"


class CheckDTO(Strict):
    name: str
    status: CheckStatusDTO
    utilisation: float = Field(description="E_d / R_d. Always reported, never just 'OK'.")
    acting: str
    resisting: str
    clause: ClauseDTO
    detail: str | None = None
    remedy: str | None = None


class VerificationReportDTO(Strict):
    element: str
    passed: bool
    max_utilisation: float
    checks: list[CheckDTO]


class NdpStatusDTO(str, Enum):
    EN_RECOMMENDED = "en_recommended"
    NA_CONFIRMED = "na_confirmed"
    NA_PENDING_VERIFICATION = "na_pending_verification"


class NdpEntryDTO(Strict):
    value: float
    unit: str
    status: NdpStatusDTO
    clause: str
    source: str
    en_recommended: float | None = None


class NdpSummaryDTO(Strict):
    """Printed verbatim in the 'referentiel applique' section of the note."""

    country: str
    region: str | None
    version: str
    published_at: str
    description: str
    strict: bool
    unverified: list[str] = Field(
        description="Parameters not yet confirmed against the published National Annex."
    )
    parameters: dict[str, NdpEntryDTO]


class EngineErrorDTO(Strict):
    """A refusal. The API returns this with HTTP 422, never a partial result."""

    error: Annotated[
        Literal[
            "out_of_validation_domain",
            "unverified_national_parameter",
            "inconsistent_input",
            "unit_error",
        ],
        Field(description="Machine-readable class of refusal."),
    ]
    what: str
    detail: str
    clause: str | None = None
