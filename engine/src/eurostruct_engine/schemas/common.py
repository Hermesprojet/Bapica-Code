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
    "ValidationStatusDTO",
    "SourceTypeDTO",
    "ParameterVariantDTO",
    "NdpEntryDTO",
    "NationalAnnexDTO",
    "RegulatoryFrameworkDTO",
    "NdpSummaryDTO",
    "BlockingParameterDTO",
    "PreflightReportDTO",
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


class ValidationStatusDTO(str, Enum):
    """How far a national value has been verified — see TICKET 1.1."""

    CONFIRMED = "confirmed"
    PENDING_VERIFICATION = "pending_verification"
    DEPRECATED = "deprecated"
    #: The annex fixes the parameter as something other than a scalar (a
    #: formula, typically). ``parameter_value`` is then ``null``. Refused in
    #: every mode; no signature unblocks it.
    NOT_REPRESENTABLE = "not_representable"


class ParameterVariantDTO(Strict):
    """One branch of a parameter the National Annex makes conditional.

    Belgium's alpha_cc is 0,85 for axial force and bending, 1,0 otherwise. The
    frontend must never collapse this to one number for display without saying
    which case it shows.
    """

    condition: str = Field(
        description="Which verification this branch applies to, matched exactly."
    )
    value: float
    description: str = Field(description="What the annex says about this branch.")


class SourceTypeDTO(str, Enum):
    NATIONAL_ANNEX = "national_annex"
    EN_RECOMMENDED = "en_recommended"
    NATIONAL_REGULATION = "national_regulation"


class NdpEntryDTO(Strict):
    """One national parameter, at one version.

    Carries its own provenance so the note de calcul can print the annex
    reference, the edition and who checked it, next to the value.
    """

    country_code: str
    standard_family: str
    part: str
    standard: str
    key: str
    national_annex_reference: str
    edition: str
    effective_from: str
    effective_to: str | None = None
    parameter_name: str
    #: ``null`` when ``validation_status`` is ``not_representable`` (nothing to
    #: store), or when ``variants`` is non-empty (the value depends on which
    #: check is being made, and a default would be read by every caller that
    #: forgot to say). The contract says so rather than shipping a placeholder.
    parameter_value: float | None
    #: Per-check branches. When present, a consumer MUST pick by ``condition``.
    variants: list["ParameterVariantDTO"] = Field(default_factory=list)
    unit: str
    source_official: str
    source_url_or_doc_id: str | None = None
    source_doc_id: str | None = Field(
        default=None,
        description="sha256 of the deposited document the value was read from.",
    )
    source_page: int | None = Field(
        default=None, description="Page of that document, as printed."
    )
    source_type: SourceTypeDTO
    validation_status: ValidationStatusDTO
    verified_at: str | None = None
    verified_by: str | None = None
    notes: str | None = None
    clause: str
    description: str
    en_recommended: float | None = None


class NationalAnnexDTO(Strict):
    """One published National Annex document, at one edition."""

    country_code: str
    standard: str
    reference: str
    edition: str
    effective_from: str
    effective_to: str | None = None
    source_official: str
    source_url_or_doc_id: str | None = None


class RegulatoryFrameworkDTO(Strict):
    """What is legally binding in the country — not always the Eurocode.

    Interdiction 4: a Spanish project must state that the Código Estructural,
    the CTE and NCSE-02 are the enforceable reference.
    """

    binding_reference: str
    eurocode_status: str
    verification_regime: str
    notes: list[str] = Field(default_factory=list)


class NdpSummaryDTO(Strict):
    """Printed verbatim in the 'referentiel applique' section of the note."""

    country: str
    country_name: str
    region: str | None = None
    as_of: str = Field(
        description="Project reference date used to select the edition in force."
    )
    strict: bool
    regulatory_framework: RegulatoryFrameworkDTO
    annexes: list[NationalAnnexDTO]
    unverified: list[str] = Field(
        description="Parameters not yet confirmed against the published National Annex."
    )
    parameters: dict[str, NdpEntryDTO]


class BlockingParameterDTO(Strict):
    """One reason a calculation cannot proceed — TICKET 1.3."""

    key: str
    reason: Annotated[
        Literal["annex_missing", "missing", "pending_verification", "deprecated"],
        Field(description="Machine-readable cause, for CI."),
    ]
    detail: str
    standard: str
    parameter_name: str
    national_annex_reference: str | None = None
    clause: str | None = None


class PreflightReportDTO(Strict):
    """Result of checking every required national parameter before running.

    Returned in full on refusal, so the user fixes the whole list in one pass.
    """

    country_code: str
    as_of: str
    strict: bool
    ok: bool
    required: list[str]
    blocking: list[BlockingParameterDTO]


class EngineErrorDTO(Strict):
    """A refusal. The API returns this with HTTP 422, never a partial result."""

    error: Annotated[
        Literal[
            "out_of_validation_domain",
            "national_annex_incomplete",
            "unverified_national_parameter",
            "deprecated_national_parameter",
            "inconsistent_input",
            "unit_error",
        ],
        Field(description="Machine-readable class of refusal."),
    ]
    what: str
    detail: str
    clause: str | None = None
    #: Set when ``error == "national_annex_incomplete"``: the full blocker list.
    preflight: PreflightReportDTO | None = None
