"""Adapter between the wire contract and the engine.

This is the only place where DTOs meet domain objects. Keeping the conversion
here means the calculation modules never deal with untyped payloads, and the
orchestrator never touches Pint quantities.

Refusals are converted to :class:`~eurostruct_engine.schemas.common.EngineErrorDTO`
by :func:`error_of`, which the HTTP layer returns with status 422. A refusal is
never downgraded into a partial result.
"""

from __future__ import annotations

import math
from datetime import date
from typing import Any

from .basis import DesignSituation
from .drawing.beam_section import BarRow, BeamSectionSpec, build_beam_section
from .ec2.beam_flexure import (
    RectangularSection,
    design_flexure,
    required_parameters,
)
from .exceptions import (
    DeprecatedNationalParameter,
    EurostructEngineError,
    InconsistentInput,
    NationalAnnexIncomplete,
    OutOfValidationDomain,
    ReinforcementNotVerified,
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
    BarRowDTO,
    BeamSectionDrawingRequest,
    Ec2BeamFlexureRequest,
    Ec2BeamFlexureResponse,
    Ec2BeamFlexureResult,
    Ec2BeamSectionRequest,
    RebarScheduleRowDTO,
)
from .traceability import Provenance, ProvenanceKind
from .units import Q_, Quantity

__all__ = [
    "error_of",
    "of_quantity",
    "provided_area",
    "render_beam_section",
    "run_ec2_beam_flexure",
    "to_quantity",
    "verify_and_render_beam_section",
]


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


def run_ec2_beam_flexure(
    req: Ec2BeamFlexureRequest,
    *,
    provider: Any = None,
) -> Ec2BeamFlexureResponse:
    """Execute the ULS bending verification described by *req*.

    LE PORTILLON DU MODE STRICT PASSE PAR LE CHEMIN D'AUTORITE
    -----------------------------------------------------------
    ``provider`` est la source des confirmations. Quand il est fourni, chaque
    paramètre national requis est confronté aux attestations qui le visent —
    :func:`~eurostruct_engine.ndp.passerelle.confirmer_depuis_le_provider`
    appelle ``assess_confirmations``, et **seuls** les paramètres dont deux
    ingénieurs indépendants ont confirmé le sujet exact deviennent utilisables.

    Sans provider, aucune confirmation n'est connue : le mode strict refuse,
    ce qui est l'état de ce référentiel aujourd'hui. C'est un défaut
    **fail-closed** — l'absence de source ne débloque rien.

    Le moteur n'importe toujours aucun pilote de base : ``provider`` est un
    protocole, et le seul appel qu'on lui fait est de lire.

    :raises EurostructEngineError: on any refusal; the caller converts it with
        :func:`error_of`.
    """
    params = load_parameter_set(
        req.country,
        req.region,
        strict=req.strict_ndp,
        as_of=date.fromisoformat(req.as_of) if req.as_of else None,
    )

    if provider is not None and req.strict_ndp:
        from .ndp.passerelle import confirmer_depuis_le_provider

        # LES CLES DEMANDEES, ET AUCUNE AUTRE. Confirmer large « pendant qu'on
        # y est » ouvrirait des parametres que ce calcul n'utilise pas, sur la
        # foi d'un dossier que personne n'a demande a voir.
        params, _ = confirmer_depuis_le_provider(
            params, tuple(required_parameters(DesignSituation(req.situation.value))),
            provider=provider,
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


def provided_area(rows: list[BarRowDTO]) -> Quantity:
    """The steel area of *rows*. Computed **here**, never received.

    Geometry, not engineering — but it must not be left to a client. An area
    supplied alongside the bars can disagree with them, and the verification
    would then pass on a number that no bar in the drawing has. Deriving it
    from the bars makes that disagreement unrepresentable.
    """
    total = sum(r.count * math.pi * (r.diameter / 2.0) ** 2 for r in rows)
    return Q_(total, "mm**2")


def verify_and_render_beam_section(
    req: Ec2BeamSectionRequest,
) -> tuple[Any, list[RebarScheduleRowDTO], Ec2BeamFlexureResponse]:
    """Verify the chosen bars, then draw them. Never one without the other.

    The drawing is built from ``req.calculation.section`` — the very geometry
    the verification just ran on — so the plan cannot describe a beam that was
    never checked. That is the whole point of taking one request rather than
    two: a caller cannot hold two geometries and send the wrong one.

    :raises ReinforcementNotVerified: when the section as detailed fails a
        check. No document is produced.
    """
    aire = provided_area(req.reinforcement.bottom)
    calcul = req.calculation.model_copy(
        update={"A_s_provided": of_quantity(aire, "mm**2")}
    )
    reponse = run_ec2_beam_flexure(calcul)

    rapport = reponse.verification
    if not rapport.passed:
        rates = tuple(c.name for c in rapport.checks if c.status.value != "pass")
        raise ReinforcementNotVerified(
            "le ferraillage choisi ne verifie pas la section: "
            f"{', '.join(rates) or 'un controle'} — utilisation "
            f"{rapport.max_utilisation:.3f}. Aucun plan n'est produit: un "
            "dessin qui echoue a sa propre verification a l'air d'un dessin "
            "valide entre les mains de celui qui l'ouvre. Acier mis en oeuvre "
            f"{aire.magnitude:.0f} mm², requis "
            f"{reponse.result.As_required.value:.0f} mm².",
            utilisation=rapport.max_utilisation,
            failing=rates,
        )

    dessin = BeamSectionDrawingRequest(
        project=req.calculation.project_id,
        element=req.calculation.element,
        b=req.calculation.section.b.value,
        h=req.calculation.section.h.value,
        cover=req.reinforcement.cover,
        link_diameter=req.reinforcement.link_diameter,
        bottom=list(req.reinforcement.bottom),
        top=list(req.reinforcement.top),
        link_spacing=req.reinforcement.link_spacing,
        link_mark=req.reinforcement.link_mark,
        plot_scale=req.plot_scale,
        concrete_grade=req.calculation.materials.concrete_grade,
        steel_grade=req.calculation.materials.steel_grade,
        exposure_class=req.exposure_class,
        index=req.index,
        date=req.date,
    )
    doc, schedule = render_beam_section(dessin)
    return doc, schedule, reponse


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
    if isinstance(exc, ReinforcementNotVerified):
        # Un verdict d'ingenierie, pas une entree malformee: le dessin est
        # refuse parce que la section ne verifie pas, et le refus le dit.
        return EngineErrorDTO(
            error="reinforcement_not_verified",
            what=f"utilisation {exc.utilisation:.3f}",
            detail=exc.detail,
        )
    if isinstance(exc, UnitError):
        return EngineErrorDTO(error="unit_error", what="unit", detail=str(exc))
    if isinstance(exc, InconsistentInput):
        return EngineErrorDTO(
            error="inconsistent_input", what="inconsistent_input", detail=str(exc)
        )
    raise exc  # unknown engine error: do not swallow it
