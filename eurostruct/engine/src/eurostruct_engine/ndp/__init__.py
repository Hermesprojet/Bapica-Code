"""Nationally determined parameters.

Three layers kept strictly apart (TICKET 1.1):
  model.py     — what a national parameter *is*: versioned, dated, sourced
  registry.py  — how it is loaded, resolved by date, and preflighted
  data/*.json  — the values themselves, per country

A calculation module never contains a national value. It declares the keys it
needs and asks the ParameterSet for them.
"""

from __future__ import annotations

from .model import (
    CountryRegistry,
    NationalAnnex,
    NationalParameter,
    RegulatoryFramework,
    SourceType,
    ValidationStatus,
    ValueProvenance,
)
from .registry import (
    BlockingParameter,
    ParameterSet,
    PreflightReport,
    available_countries,
    load_country_registry,
    load_parameter_set,
)

__all__ = [
    "ValidationStatus",
    "SourceType",
    "ValueProvenance",
    "NationalParameter",
    "NationalAnnex",
    "RegulatoryFramework",
    "CountryRegistry",
    "ParameterSet",
    "PreflightReport",
    "BlockingParameter",
    "load_parameter_set",
    "load_country_registry",
    "available_countries",
]
