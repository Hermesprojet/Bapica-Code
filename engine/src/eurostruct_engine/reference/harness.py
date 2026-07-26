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
from ..ec2.beam_flexure import RectangularSection, design_flexure
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
