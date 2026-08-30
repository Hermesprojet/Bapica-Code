"""Request and response contract for the EC2 beam flexure verification.

This is the contract between the Next.js orchestrator and the Python engine.
The TypeScript types consumed by the frontend are generated from these models
by ``scripts/export_contracts.py`` — they are never written by hand, so the two
sides cannot drift.
"""

from __future__ import annotations

from pydantic import Field, field_validator, model_validator

from .common import (
    CountryCode,
    DesignSituationDTO,
    JournalDTO,
    NdpSummaryDTO,
    ProvenanceDTO,
    QuantityDTO,
    Strict,
    VerificationReportDTO,
)

__all__ = [
    "RectangularSectionDTO",
    "MaterialsDTO",
    "Ec2BeamFlexureRequest",
    "Ec2BeamFlexureResult",
    "Ec2BeamFlexureResponse",
    "BarRowDTO",
    "BeamSectionDrawingRequest",
    "RebarScheduleRowDTO",
]


class RectangularSectionDTO(Strict):
    b: QuantityDTO = Field(description="Width")
    h: QuantityDTO = Field(description="Overall depth")
    d: QuantityDTO = Field(description="Effective depth to the tension reinforcement")


class MaterialsDTO(Strict):
    concrete_grade: str = Field(
        description="EN 1992-1-1 Table 3.1 designation.", examples=["C30/37"]
    )
    steel_grade: str = Field(
        description="Reinforcement designation.", examples=["B500B"]
    )


class Ec2BeamFlexureRequest(Strict):
    """Input of the ULS bending verification of a rectangular section."""

    project_id: str
    element: str = Field(default="poutre", description="Element mark shown in the note.")

    country: CountryCode
    region: str | None = Field(
        default=None,
        description="Sub-national region where it changes the parameters "
        "(Wallonie / Vlaanderen / Bruxelles, Land, Comunidad autonoma).",
    )
    as_of: str | None = Field(
        default=None,
        description="Project reference date (ISO 8601) used to select the edition "
        "of the National Annex in force. Pin it on a real project so the "
        "calculation stays reproducible after a newer edition is published. "
        "Defaults to today.",
    )
    strict_ndp: bool = Field(
        default=True,
        description="When true, an unverified National Annex parameter causes a "
        "refusal. Required for any deliverable intended to be signed; set false "
        "only for exploratory work.",
    )

    section: RectangularSectionDTO
    materials: MaterialsDTO
    situation: DesignSituationDTO = DesignSituationDTO.PERSISTENT

    M_Ed: QuantityDTO = Field(
        description="Design moment from the governing EN 1990 combination. "
        "The engine does not build combinations."
    )
    A_s_provided: QuantityDTO | None = Field(
        default=None,
        description="Area of the bars actually detailed. When omitted, the ULS "
        "check is made against the exact required area and its utilisation is 1,000.",
    )

    provenance: dict[str, ProvenanceDTO] = Field(
        default_factory=dict,
        description="Origin of each input, keyed by symbol (b, h, d, M_Ed). "
        "Values extracted from a document must carry confirmed_by/confirmed_at.",
    )

    @field_validator("M_Ed")
    @classmethod
    def _moment_is_positive(cls, v: QuantityDTO) -> QuantityDTO:
        if v.value < 0:
            raise ValueError(
                "M_Ed doit etre positif; orienter la section pour que la fibre "
                "tendue corresponde a la hauteur utile d."
            )
        return v

    @model_validator(mode="after")
    def _extracted_values_must_be_confirmed(self) -> "Ec2BeamFlexureRequest":
        """Interdiction 5: no dimension taken from a drawing without confirmation."""
        for symbol, p in self.provenance.items():
            if p.kind.value == "document_extraction" and not p.confirmed_by:
                raise ValueError(
                    f"la valeur '{symbol}' provient d'une extraction documentaire "
                    "non confirmee. Toute cote extraite d'un plan doit etre "
                    "validee explicitement par un utilisateur avant d'entrer "
                    "dans le calcul."
                )
        return self


class Ec2BeamFlexureResult(Strict):
    """Numeric outcome. Every field is also reachable through the journal."""

    As_strength: QuantityDTO = Field(description="Area required by strength alone")
    As_min: QuantityDTO = Field(description="§9.2.1.1(1), eq. (9.1N)")
    As_max: QuantityDTO = Field(description="§9.2.1.1(3)")
    As_required: QuantityDTO = Field(description="max(As_strength, As_min)")
    As_provided: QuantityDTO
    x: QuantityDTO = Field(description="Neutral axis depth")
    z: QuantityDTO = Field(description="Lever arm")
    M_Rd: QuantityDTO
    mu: float
    xi: float
    xi_lim: float
    eps_s: float
    utilisation: float


class Ec2BeamFlexureResponse(Strict):
    """Output of a successful verification.

    A refusal is *not* represented here: it is returned as
    :class:`~eurostruct_engine.schemas.common.EngineErrorDTO` with HTTP 422, so
    a caller cannot mistake a refusal for a result.
    """

    element: str
    engine_version: str = Field(
        description="Stamped into the note de calcul and every drawing."
    )
    result: Ec2BeamFlexureResult
    verification: VerificationReportDTO
    journal: JournalDTO
    ndp: NdpSummaryDTO


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------
class BarRowDTO(Strict):
    count: int = Field(ge=1)
    diameter: float = Field(gt=0, description="Nominal bar diameter, mm")
    mark: str
    length: float | None = Field(default=None, description="Developed length, mm")


class ReinforcementChoiceDTO(Strict):
    """The bars the engineer chose. Never deduced from the calculation.

    ``As_required`` says how much steel is needed; it says nothing about how
    many bars, of which diameter, arranged how. That choice is the engineer's,
    and this is where it enters — separately from the geometry, which comes
    from the calculation that was verified.
    """

    cover: float = Field(ge=0, description="Nominal cover c_nom, mm")
    link_diameter: float = Field(ge=0, description="Link diameter, mm")
    link_spacing: float | None = None
    link_mark: str = "C1"
    #: Tension face. At least one row: a section with no tension steel is not
    #: a reinforced section, and drawing it would be drawing nothing.
    bottom: list[BarRowDTO] = Field(min_length=1)
    top: list[BarRowDTO] = Field(default_factory=list)


class Ec2BeamSectionRequest(Strict):
    """Verify the chosen bars, **then** draw them — never the reverse.

    WHY THE CALCULATION TRAVELS WITH THE DRAWING REQUEST
    -----------------------------------------------------
    Measured on 30/08: the interface sent a hard-coded 300 x 500 to the drawing
    endpoint whatever section had just been calculated. The engineer received a
    plan of a beam that was never verified, carrying the mandatory notice and
    their own element mark.

    Nothing could catch it, because the drawing endpoint had no way to know
    what had been calculated: it was handed a geometry and drew it, correctly.
    Sending the **verified request itself** removes the gap by construction —
    the drawn section and the checked section are the same object, and no
    caller can hold two of them.

    ``A_s_provided`` is deliberately absent: it is **computed here** from the
    bars, so that no client has to, and so that none can claim an area its
    bars do not have.
    """

    calculation: Ec2BeamFlexureRequest
    reinforcement: ReinforcementChoiceDTO
    plot_scale: float = Field(default=20.0, gt=0)
    exposure_class: str = ""
    index: str = "A"
    date: str = ""


class BeamSectionDrawingRequest(Strict):
    """Input of the DXF cross-section generator.

    Kept as the **drawing** contract: it knows a geometry and bars, and nothing
    about whether they were verified. :class:`Ec2BeamSectionRequest` is what a
    client should send; this one is what the renderer consumes once the check
    has passed.
    """

    project: str = ""
    element: str = ""
    b: float = Field(gt=0, description="Width, mm")
    h: float = Field(gt=0, description="Overall depth, mm")
    cover: float = Field(ge=0, description="Nominal cover c_nom, mm")
    link_diameter: float = Field(ge=0, description="Link diameter, mm")
    bottom: list[BarRowDTO] = Field(default_factory=list)
    top: list[BarRowDTO] = Field(default_factory=list)
    link_spacing: float | None = None
    link_mark: str = "C1"
    plot_scale: float = Field(default=20.0, gt=0)
    concrete_grade: str = ""
    steel_grade: str = ""
    exposure_class: str = ""
    index: str = "A"
    date: str = ""


class RebarScheduleRowDTO(Strict):
    """One line of the nomenclature — section 7.2."""

    mark: str
    diameter_mm: float
    count: int
    unit_length_mm: float | None
    total_length_mm: float | None
    mass_kg: float | None
    shape_code: str = Field(description="Shape code per EN ISO 3766")
    comment: str = ""
