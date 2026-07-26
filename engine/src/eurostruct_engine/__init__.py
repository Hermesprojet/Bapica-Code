"""EUROSTRUCT — deterministic structural calculation engine.

This package contains **no** language model and no network call. It is a pure
function of its inputs: the same project recalculated yields a bit-for-bit
identical result, which is what makes a note de calcul defensible.

Layers::

    units / traceability      physical quantities, clause citations, journal
    ndp                       nationally determined parameters, per country
    materials                 EN 1992-1-1 §3.1 / §3.2 material laws
    ec2                       reinforced concrete verifications
    drawing                   deterministic DXF output (ezdxf)

See ``docs/VALIDATION.md`` for the validation policy and the versioning
contract.
"""

from __future__ import annotations

from .basis import ConsequenceClass, DesignSituation, LimitState
from .exceptions import (
    EurostructEngineError,
    InconsistentInput,
    OutOfValidationDomain,
    UnitError,
    UnverifiedNationalParameter,
)
from .traceability import Clause, Journal, Provenance, ProvenanceKind
from .units import Q_, Quantity, ureg
from .verification import Check, CheckStatus, VerificationReport
from .version import ENGINE_NAME, ENGINE_VERSION, engine_stamp

__all__ = [
    "ureg",
    "Q_",
    "Quantity",
    "Clause",
    "Journal",
    "Provenance",
    "ProvenanceKind",
    "Check",
    "CheckStatus",
    "VerificationReport",
    "DesignSituation",
    "ConsequenceClass",
    "LimitState",
    "EurostructEngineError",
    "OutOfValidationDomain",
    "UnverifiedNationalParameter",
    "InconsistentInput",
    "UnitError",
    "ENGINE_NAME",
    "ENGINE_VERSION",
    "engine_stamp",
]
