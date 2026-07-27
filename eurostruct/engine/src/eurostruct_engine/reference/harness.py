"""Harnesses: how a reference case is replayed against the engine.

A case names a ``harness`` (``"ec2.beam_flexure"``); the registry here maps it
to the function that turns the stored ``input_dataset`` into a flat dictionary
of named outputs. Adding a validated module means registering one harness — the
runner, the comparison and the CI reporting are unchanged.

A harness that is not registered is not an error: the case is reported as
``awaiting_module``, which is how the library tracks planned coverage without
pretending it exists.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Callable, Mapping

from ..basis import DesignSituation
from ..ec2.anchorage import AnchorageCoefficients, design_anchorage
from ..ec2.beam_flexure import RectangularSection, design_flexure
from ..ec2.beam_shear import ShearLinks, ShearSection, design_shear
from ..materials import concrete, reinforcement
from ..ndp import load_parameter_set
from ..units import Q_

__all__ = ["register", "get_harness", "available_harnesses", "HarnessFn"]

HarnessFn = Callable[[Mapping[str, Any]], dict[str, float]]

_REGISTRY: dict[str, HarnessFn] = {}


def register(name: str) -> Callable[[HarnessFn], HarnessFn]:
    def deco(fn: HarnessFn) -> HarnessFn:
        if name in _REGISTRY:
            raise KeyError(f"harness deja enregistre: {name}")
        _REGISTRY[name] = fn
        return fn

    return deco


def get_harness(name: str) -> HarnessFn | None:
    return _REGISTRY.get(name)


def available_harnesses() -> tuple[str, ...]:
    return tuple(sorted(_REGISTRY))


def _quantity(spec: Mapping[str, Any]):
    """``{"value": 300, "unit": "mm"}`` -> Pint quantity.

    Inputs of a reference case carry their unit like everything else that
    crosses a boundary; a bare number would defeat the point.
    """
    return Q_(float(spec["value"]), spec["unit"])


@register("ec2.beam_flexure")
def _ec2_beam_flexure(inputs: Mapping[str, Any]) -> dict[str, float]:
    """Replay a rectangular-section ULS bending case."""
    params = load_parameter_set(
        inputs["country"],
        inputs.get("region"),
        strict=bool(inputs.get("strict_ndp", False)),
        as_of=date.fromisoformat(inputs["as_of"]),
    )
    design = design_flexure(
        section=RectangularSection(
            b=_quantity(inputs["b"]),
            h=_quantity(inputs["h"]),
            d=_quantity(inputs["d"]),
        ),
        concrete=concrete(inputs["concrete_grade"]),
        steel=reinforcement(inputs["steel_grade"]),
        M_Ed=_quantity(inputs["M_Ed"]),
        params=params,
        situation=DesignSituation(inputs.get("situation", "persistent")),
        element=inputs.get("element", "reference"),
        A_s_provided=(
            _quantity(inputs["A_s_provided"]) if inputs.get("A_s_provided") else None
        ),
    )
    return {
        "mu": design.mu,
        "xi": design.xi,
        "xi_lim": design.xi_lim,
        "eps_s": design.eps_s,
        "x_mm": float(design.x.to("mm").magnitude),
        "z_mm": float(design.z.to("mm").magnitude),
        "As_strength_mm2": float(design.As_strength.to("mm**2").magnitude),
        "As_min_mm2": float(design.As_min.to("mm**2").magnitude),
        "As_max_mm2": float(design.As_max.to("mm**2").magnitude),
        "As_required_mm2": float(design.As_required.to("mm**2").magnitude),
        "M_Rd_kNm": float(design.resistance.M_Rd.to("kN*m").magnitude),
        "utilisation": design.utilisation,
    }


def _params(inputs: Mapping[str, Any]):
    """The parameter set a case pins itself to — country, region and date."""
    return load_parameter_set(
        inputs["country"],
        inputs.get("region"),
        strict=bool(inputs.get("strict_ndp", False)),
        as_of=date.fromisoformat(inputs["as_of"]),
    )


@register("ec2.beam_shear")
def _ec2_beam_shear(inputs: Mapping[str, Any]) -> dict[str, float]:
    """Replay a shear case, §6.2.

    ``V_Rd_s`` and ``V_Rd_max`` are absent from the outputs in the no-links
    regime rather than reported as zero: §6.2.1 does not compute them there,
    and a zero would read as "no resistance" instead of "not applicable".
    """
    links = inputs.get("links")
    design = design_shear(
        section=ShearSection(
            b_w=_quantity(inputs["b_w"]),
            d=_quantity(inputs["d"]),
            A_sl=_quantity(inputs["A_sl"]),
            N_Ed=_quantity(inputs["N_Ed"]) if inputs.get("N_Ed") else None,
            A_c=_quantity(inputs["A_c"]) if inputs.get("A_c") else None,
        ),
        concrete=concrete(inputs["concrete_grade"]),
        steel=reinforcement(inputs["steel_grade"]),
        V_Ed=_quantity(inputs["V_Ed"]),
        params=_params(inputs),
        cot_theta=float(inputs.get("cot_theta", 1.0)),
        links=(
            ShearLinks(A_sw=_quantity(links["A_sw"]), s=_quantity(links["s"]))
            if links else None
        ),
        situation=DesignSituation(inputs.get("situation", "persistent")),
        element=inputs.get("element", "reference"),
    )
    out = {
        "V_Rd_c_kN": float(design.V_Rd_c.to("kN").magnitude),
        "V_Rd_kN": float(design.V_Rd.to("kN").magnitude),
        "Asw_over_s_min_mm2_per_m": float(
            design.Asw_over_s_min.to("mm**2/m").magnitude
        ),
        "s_l_max_mm": float(design.s_l_max.to("mm").magnitude),
        "delta_F_td_kN": float(design.delta_F_td.to("kN").magnitude),
        "utilisation": design.utilisation,
    }
    if design.V_Rd_s is not None:
        out["V_Rd_s_kN"] = float(design.V_Rd_s.to("kN").magnitude)
    if design.V_Rd_max is not None:
        out["V_Rd_max_kN"] = float(design.V_Rd_max.to("kN").magnitude)
    return out


@register("ec2.anchorage")
def _ec2_anchorage(inputs: Mapping[str, Any]) -> dict[str, float]:
    """Replay an anchorage and lap case, §8.4 and §8.7."""
    coeff = inputs.get("coefficients") or {}
    design = design_anchorage(
        concrete=concrete(inputs["concrete_grade"]),
        steel=reinforcement(inputs["steel_grade"]),
        phi=_quantity(inputs["phi"]),
        params=_params(inputs),
        sigma_sd=_quantity(inputs["sigma_sd"]) if inputs.get("sigma_sd") else None,
        A_s_required=(
            _quantity(inputs["A_s_required"]) if inputs.get("A_s_required") else None
        ),
        A_s_provided=(
            _quantity(inputs["A_s_provided"]) if inputs.get("A_s_provided") else None
        ),
        in_tension=bool(inputs.get("in_tension", True)),
        bond_condition=inputs.get("bond_condition", "good"),
        coefficients=AnchorageCoefficients(**coeff) if coeff else None,
        situation=DesignSituation(inputs.get("situation", "persistent")),
        element=inputs.get("element", "reference"),
    )
    return {
        "f_bd_MPa": float(design.f_bd.to("MPa").magnitude),
        "l_b_rqd_mm": float(design.l_b_rqd.to("mm").magnitude),
        "l_bd_mm": float(design.l_bd.to("mm").magnitude),
        "l_b_min_mm": float(design.l_b_min.to("mm").magnitude),
        "l_0_mm": float(design.l_0.to("mm").magnitude),
        "l_0_min_mm": float(design.l_0_min.to("mm").magnitude),
        "sigma_sd_MPa": float(design.sigma_sd.to("MPa").magnitude),
    }
