"""Nationally determined parameters.

Three layers kept strictly apart (TICKET 1.1):
  model.py     — what a national parameter *is*: versioned, dated, sourced
  registry.py  — how it is loaded, resolved by date, and preflighted
  data/*.json  — the values themselves, per country

A calculation module never contains a national value. It declares the keys it
needs and asks the ParameterSet for them.
"""

from __future__ import annotations

# Les regles typees s'ENREGISTRENT a l'import. Sans cet import, find_rule()
# rendrait None pour la Belgique et le moteur retomberait EN SILENCE sur les
# scalaires deprecies — exactement le second chemin normatif que ce travail
# supprime. L'import est donc fonctionnel, pas cosmetique.
from . import rules_be_ec2 as _rules_be_ec2  # noqa: F401
from .canonical import (
    CANONICALIZATION_VERSION,
    Digest,
    EvidenceItem,
    UnresolvableDependency,
    evidence_digest,
    implementation_digest,
    normative_spec_digest,
)
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
    "CANONICALIZATION_VERSION",
    "BlockingParameter",
    "CountryRegistry",
    "Digest",
    "EvidenceItem",
    "NationalAnnex",
    "NationalParameter",
    "ParameterSet",
    "PreflightReport",
    "RegulatoryFramework",
    "SourceType",
    "UnresolvableDependency",
    "ValidationStatus",
    "ValueProvenance",
    "available_countries",
    "evidence_digest",
    "implementation_digest",
    "load_country_registry",
    "load_parameter_set",
    "normative_spec_digest",
]
