"""Adapter between the wire contract and the engine.

This is the only place where DTOs meet domain objects. Keeping the conversion
here means the calculation modules never deal with untyped payloads, and the
orchestrator never touches Pint quantities.

Refusals are converted to :class:`~eurostruct_engine.schemas.common.EngineErrorDTO`
by :func:`error_of`, which the HTTP layer returns with status 422. A refusal is
never downgraded into a partial result.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from .basis import DesignSituation
from .drawing.beam_section import BarRow, BeamSectionSpec, build_beam_section
from .ec2.beam_flexure import RectangularSection, design_flexure
from .exceptions import (
    DeprecatedNationalParameter,
    EurostructEngineError,
    InconsistentInput,
    NationalAnnexIncomplete,
    OutOfValidationDomain,
    UnitError,
    UnverifiedNationalParameter,
)
from .materials import concrete as concrete_grade
from .materials import reinforcement as steel_grade
from .ndp import load_parameter_set
from .schemas.common import (
    EngineErrorDTO,
    PreflightReportDTO,
    ProvenanceDTO,
    QuantityDTO,
)
from .schemas.ec2_beam import (
    Ec2BeamFlexureRequest,
    Ec2BeamFlexureResponse,
    Ec2BeamFlexureResult,
    RebarScheduleRowDTO,
)
from .schemas.ec2_beam import BeamSectionDrawingRequest
from .traceability import Provenance, ProvenanceKind
from .units import Q_, Quantity

__all__ = ["run_ec2_beam_flexure", "render_beam_section", "error_of", "to_quantity", "of_quantity"]


def to_quantity(dto: QuantityDTO) -> Quantity:
    """DTO -> Pint quantity. The unit string is parsed, never assumed."""
    return Q_(dto.value, dto.unit)


def of_quantity(q: Quantity, unit: str) -> QuantityDTO:
    """Pint quantity -> DTO, expressed in *unit*."""
    return QuantityDTO(value=float(q.to(unit).magnitude), unit=unit)


def _provenance(dto: ProvenanceDTO) -> Provenance:
    return Provenance(
        kind=ProvenanceKind(dto.kind.value),
        detail=dto.detail,
        document_id=dto.document_id,
        page=dto.page,
        bbox=dto.bbox,
        ndp_key=dto.ndp_key,
        confirmed_by=dto.confirmed_by,
        confirmed_at=dto.confirmed_at,
    )


def run_ec2_beam_flexure(req: Ec2BeamFlexureRequest) -> Ec2BeamFlexureResponse:
    """Execute the ULS bending verification described by *req*.

    :raises EurostructEngineError: on any refusal; the caller converts it with
        :func:`error_of`.
    """
    params = load_parameter_set(
        req.country,
        req.region,
        strict=req.strict_ndp,
        as_of=date.fromisoformat(req.as_of) if req.as_of else None,
    )

    design = design_flexure(
        section=RectangularSection(
            b=to_quantity(req.section.b),
            h=to_quantity(req.section.h),
            d=to_quantity(req.section.d),
        ),
        concrete=concrete_grade(req.materials.concrete_grade),
        steel=steel_grade(req.materials.steel_grade),
        M_Ed=to_quantity(req.M_Ed),
        params=params,
        situation=DesignSituation(req.situation.value),
        element=req.element,
        provenance={k: _provenance(v) for k, v in req.provenance.items()},
        A_s_provided=to_quantity(req.A_s_provided) if req.A_s_provided else None,
    )

    return Ec2BeamFlexureResponse.model_validate(
        {
            "element": design.element,
            "engine_version": design.engine_version,
            "result": Ec2BeamFlexureResult(
                As_strength=of_quantity(design.As_strength, "mm**2"),
                As_min=of_quantity(design.As_min, "mm**2"),
                As_max=of_quantity(design.As_max, "mm**2"),
                As_required=of_quantity(design.As_required, "mm**2"),
                As_provided=of_quantity(design.As_provided, "mm**2"),
                x=of_quantity(design.x, "mm"),
                z=of_quantity(design.z, "mm"),
                M_Rd=of_quantity(design.resistance.M_Rd, "kN*m"),
                mu=design.mu,
                xi=design.xi,
                xi_lim=design.xi_lim,
                eps_s=design.eps_s,
                utilisation=design.utilisation,
            ),
            "verification": design.report.to_dict(),
            "journal": design.journal.to_dict(),
            "ndp": design.ndp_summary,
        }
    )


def render_beam_section(
    req: BeamSectionDrawingRequest,
) -> tuple[Any, list[RebarScheduleRowDTO]]:
    """Build the DXF document and the rebar schedule for a cross-section."""
    spec = BeamSectionSpec(
        b=req.b,
        h=req.h,
        cover=req.cover,
        link_diameter=req.link_diameter,
        bottom=tuple(
            BarRow(count=r.count, diameter=r.diameter, mark=r.mark, length=r.length)
            for r in req.bottom
        ),
        top=tuple(
            BarRow(count=r.count, diameter=r.diameter, mark=r.mark, length=r.length)
            for r in req.top
        ),
        link_spacing=req.link_spacing,
        link_mark=req.link_mark,
        plot_scale=req.plot_scale,
        element=req.element,
        project=req.project,
        concrete_grade=req.concrete_grade,
        steel_grade=req.steel_grade,
        exposure_class=req.exposure_class,
        index=req.index,
        date=req.date,
    )
    doc, schedule = build_beam_section(spec)
    return doc, [RebarScheduleRowDTO.model_validate(r.to_dict()) for r in schedule]


def error_of(exc: EurostructEngineError) -> EngineErrorDTO:
    """Map a refusal onto the wire error type."""
    if isinstance(exc, OutOfValidationDomain):
        return EngineErrorDTO(
            error="out_of_validation_domain",
            what=exc.what,
            detail=exc.detail,
            clause=exc.clause,
        )
    if isinstance(exc, NationalAnnexIncomplete):
        # The whole blocker list travels with the error, so the caller can show
        # every parameter to fix in one pass (TICKET 1.3).
        return EngineErrorDTO(
            error="national_annex_incomplete",
            what=f"{len(exc.blocking)} parametre(s) national(aux) bloquant(s)",
            detail=str(exc),
            preflight=PreflightReportDTO.model_validate(exc.to_dict()),
        )
    if isinstance(exc, UnverifiedNationalParameter):
        return EngineErrorDTO(
            error="unverified_national_parameter",
            what=exc.key,
            detail=str(exc),
            clause=None,
        )
    if isinstance(exc, DeprecatedNationalParameter):
        return EngineErrorDTO(
            error="deprecated_national_parameter", what=exc.key, detail=str(exc)
        )
    if isinstance(exc, UnitError):
        return EngineErrorDTO(error="unit_error", what="unit", detail=str(exc))
    if isinstance(exc, InconsistentInput):
        return EngineErrorDTO(
            error="inconsistent_input", what="inconsistent_input", detail=str(exc)
        )
    raise exc  # unknown engine error: do not swallow it
