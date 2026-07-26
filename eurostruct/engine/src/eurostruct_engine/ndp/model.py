"""Data model of the normative parameter layer.

TICKET 1.1 — the storage layer keeps three things strictly apart:

1. **Generic Eurocode formulas** — they live in the calculation modules
   (:mod:`eurostruct_engine.ec2` and siblings) and contain no national value.
2. **National parameters** — this module. They are data, versioned, dated and
   sourced. A formula never embeds one.
3. **Reference cases** — :mod:`eurostruct_engine.reference`.

Nothing here computes. The separation is what makes it impossible for a
national value to be silently baked into an equation: a calculation module has
no way to obtain a number except by asking a
:class:`~eurostruct_engine.ndp.registry.ParameterSet` for it by name, and every
such request is recorded.

Versioning
----------
A national parameter is identified by
``(country_code, standard_family, part, parameter_name)`` and *versioned* by
``(edition, effective_from)``. Records are append-only: correcting a value means
closing the current record with an ``effective_to`` date and adding a new one.
There is no in-place edit — see ``db/migrations/0004_ndp_versioning.sql`` for
the database-side enforcement, and :class:`NationalAnnex` for the in-process
side (every dataclass here is frozen).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Any

__all__ = [
    "ValidationStatus",
    "SourceType",
    "NationalParameter",
    "NationalAnnex",
    "RegulatoryFramework",
    "CountryRegistry",
]


class ValidationStatus(str, Enum):
    """How much a stored national value can be trusted.

    ``CONFIRMED``
        A named engineer opened the published National Annex and recorded the
        value, with the date. The only status usable in strict mode.

    ``PENDING_VERIFICATION``
        A value believed to apply, not yet checked against the published annex.
        Blocked in strict mode.

    ``DEPRECATED``
        Superseded or known wrong. Refused in *every* mode: a deprecated value
        must never reach a calculation, strict or not.
    """

    CONFIRMED = "confirmed"
    PENDING_VERIFICATION = "pending_verification"
    DEPRECATED = "deprecated"


class SourceType(str, Enum):
    """Nature of the document a value was taken from."""

    NATIONAL_ANNEX = "national_annex"
    #: Value printed in the Note of the Eurocode clause itself.
    EN_RECOMMENDED = "en_recommended"
    #: National regulation outside the Eurocode system (CTE, Código
    #: Estructural, NCSE-02, MVV TB, DTU...).
    NATIONAL_REGULATION = "national_regulation"


@dataclass(frozen=True, slots=True)
class NationalParameter:
    """One nationally determined parameter, at one version.

    Frozen by construction: a correction is a new record, never a mutation.
    """

    country_code: str
    standard_family: str            # "EN 1992"
    part: str                       # "1-1"
    national_annex_reference: str   # "NBN EN 1992-1-1 ANB"
    edition: str                    # "2010" / "2005+A1:2014"
    effective_from: date
    effective_to: date | None
    parameter_name: str             # "alpha_cc"
    parameter_value: float
    unit: str
    source_official: str            # issuing body
    source_url_or_doc_id: str | None
    source_type: SourceType
    validation_status: ValidationStatus
    verified_at: str | None
    verified_by: str | None
    notes: str | None

    # --- kept alongside the ticket's minimum field set --------------------
    #: Clause of the base Eurocode the parameter belongs to, so the note de
    #: calcul can cite it: "§3.1.6(1)P".
    clause: str
    description: str
    #: The value recommended by the Eurocode, when it differs. Lets the note
    #: state both the national value and what it departs from.
    en_recommended: float | None = None

    @property
    def standard(self) -> str:
        """Full standard designation, e.g. ``"EN 1992-1-1"``."""
        return f"{self.standard_family}-{self.part}"

    @property
    def key(self) -> str:
        """Lookup key used by the calculation modules and the journal.

        e.g. ``"EN 1992-1-1:alpha_cc"``. Carrying the part in the key means a
        parameter of EN 1992-1-2 can never be mistaken for one of EN 1992-1-1.
        """
        return f"{self.standard}:{self.parameter_name}"

    def is_in_force(self, at: date) -> bool:
        """Whether this version applies on *at*."""
        if at < self.effective_from:
            return False
        return self.effective_to is None or at < self.effective_to

    @property
    def usable_in_strict_mode(self) -> bool:
        return self.validation_status is ValidationStatus.CONFIRMED

    def to_dict(self) -> dict[str, Any]:
        return {
            "country_code": self.country_code,
            "standard_family": self.standard_family,
            "part": self.part,
            "standard": self.standard,
            "key": self.key,
            "national_annex_reference": self.national_annex_reference,
            "edition": self.edition,
            "effective_from": self.effective_from.isoformat(),
            "effective_to": self.effective_to.isoformat() if self.effective_to else None,
            "parameter_name": self.parameter_name,
            "parameter_value": self.parameter_value,
            "unit": self.unit,
            "source_official": self.source_official,
            "source_url_or_doc_id": self.source_url_or_doc_id,
            "source_type": self.source_type.value,
            "validation_status": self.validation_status.value,
            "verified_at": self.verified_at,
            "verified_by": self.verified_by,
            "notes": self.notes,
            "clause": self.clause,
            "description": self.description,
            "en_recommended": self.en_recommended,
        }


@dataclass(frozen=True, slots=True)
class NationalAnnex:
    """One published National Annex document, at one edition.

    Groups the parameters that come from the same physical document, so the
    note de calcul can cite the document once with its edition and date rather
    than repeating it per value.
    """

    country_code: str
    standard_family: str
    part: str
    reference: str
    edition: str
    effective_from: date
    effective_to: date | None
    source_official: str
    source_url_or_doc_id: str | None
    parameters: tuple[NationalParameter, ...]

    @property
    def standard(self) -> str:
        return f"{self.standard_family}-{self.part}"

    def is_in_force(self, at: date) -> bool:
        if at < self.effective_from:
            return False
        return self.effective_to is None or at < self.effective_to

    def to_dict(self) -> dict[str, Any]:
        return {
            "country_code": self.country_code,
            "standard": self.standard,
            "reference": self.reference,
            "edition": self.edition,
            "effective_from": self.effective_from.isoformat(),
            "effective_to": self.effective_to.isoformat() if self.effective_to else None,
            "source_official": self.source_official,
            "source_url_or_doc_id": self.source_url_or_doc_id,
        }


@dataclass(frozen=True, slots=True)
class RegulatoryFramework:
    """What is *legally binding* in a country, which is not always the Eurocode.

    Interdiction 4 of the cahier des charges: Spain must not be treated as a
    pure-Eurocode country. The Código Estructural (RD 470/2021), the CTE and
    NCSE-02 are the enforceable reference there; the UNE-EN versions of the
    Eurocodes are usable but are not, on their own, what a project is checked
    against.

    This is carried on the parameter set and printed in the note de calcul, so
    a Spanish or German project states plainly which framework it was verified
    under.
    """

    #: What the authorities check the project against.
    binding_reference: str
    #: Standing of the Eurocodes in that country.
    eurocode_status: str
    #: Independent-check or filing obligations (Prüfstatiker, visado colegial,
    #: contrôle technique, ingénieur en stabilité).
    verification_regime: str
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "binding_reference": self.binding_reference,
            "eurocode_status": self.eurocode_status,
            "verification_regime": self.verification_regime,
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class CountryRegistry:
    """Every National Annex known for one country, across editions.

    TICKET 1.2: the container is per country / standard / part / version, and
    the engine resolves which edition applies from the project's reference date.
    """

    country_code: str
    country_name: str
    regulatory_framework: RegulatoryFramework
    annexes: tuple[NationalAnnex, ...]
    regions: tuple[str, ...] = ()

    def annex_for(self, standard: str, at: date) -> NationalAnnex | None:
        """The annex in force for *standard* on *at*, if any.

        Returns ``None`` rather than falling back to another edition: the
        engine must refuse to guess (TICKET 1.2, acceptance criterion 2).
        """
        candidates = [
            a for a in self.annexes if a.standard == standard and a.is_in_force(at)
        ]
        if not candidates:
            return None
        # Deterministic when editions overlap: the most recently effective one.
        return max(candidates, key=lambda a: (a.effective_from, a.edition))

    def standards(self) -> tuple[str, ...]:
        return tuple(sorted({a.standard for a in self.annexes}))
