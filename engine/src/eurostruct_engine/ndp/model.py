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
    "ParameterVariant",
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

    ``NOT_REPRESENTABLE``
        The National Annex fixes this parameter, but not as a number this model
        can hold — typically because it prescribes a formula depending on other
        quantities. Refused in *every* mode, like ``DEPRECATED``, and for the
        same reason: any scalar stored here would be a value the annex does not
        state. See ``EN 1992-1-1:cot_theta_max`` for Belgium, where the annex
        replaces the 2,5 bound with an expression in sigma_cp and the shear
        reinforcement.

        This is not a lesser form of ``PENDING_VERIFICATION``: no amount of
        human verification unblocks it. The calculation module has to learn to
        evaluate the expression first.
    """

    CONFIRMED = "confirmed"
    PENDING_VERIFICATION = "pending_verification"
    DEPRECATED = "deprecated"
    NOT_REPRESENTABLE = "not_representable"


class SourceType(str, Enum):
    """Nature of the document a value was taken from."""

    NATIONAL_ANNEX = "national_annex"
    #: Value printed in the Note of the Eurocode clause itself.
    EN_RECOMMENDED = "en_recommended"
    #: National regulation outside the Eurocode system (CTE, Código
    #: Estructural, NCSE-02, MVV TB, DTU...).
    NATIONAL_REGULATION = "national_regulation"


@dataclass(frozen=True, slots=True)
class ParameterVariant:
    """One branch of a parameter whose value depends on what is being checked.

    NBN EN 1992-1-1 ANB §3.1.6(1)P is the reason this exists:

        « Pour les verifications a l'ELU de la resistance a l'effort normal, la
        flexion simple ou composee, la valeur de alpha_cc vaut 0,85. Pour les
        autres cas, alpha_cc vaut 1,0. »

    Two values, and which one applies depends on the verification. Storing the
    bending value alone was defensible while bending was the only module; it
    stops being defensible the moment a shear module exists, because shear is
    "les autres cas" and would silently inherit 0,85 — a 15 % error on f_cd, in
    the unsafe direction for strut crushing.
    """

    #: Free-form key, defined by the parameter, matched exactly. Not an enum:
    #: each annex slices its conditions its own way, and inventing a shared
    #: vocabulary would force a mapping nobody wrote down.
    condition: str
    value: float
    #: What the annex says about this branch, verbatim where possible.
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "condition": self.condition,
            "value": self.value,
            "description": self.description,
        }


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
    #: ``None`` when the annex prescribes something this model cannot hold as a
    #: scalar (``validation_status`` is then ``NOT_REPRESENTABLE``). Storing a
    #: placeholder number instead would be inventing a value the annex does not
    #: state, which is precisely what this registry exists to prevent.
    parameter_value: float | None
    unit: str
    source_official: str            # issuing body
    source_url_or_doc_id: str | None
    #: sha256 of the deposited document the value was read from, set by the
    #: import pipeline. A confirmed value without it cannot be traced back to
    #: the file that was actually on the reviewer's screen.
    source_doc_id: str | None
    #: Page of that document, as printed. Supplied by the reviewer, not by the
    #: extractor's guess.
    source_page: int | None
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
    #: Branches, when the annex gives different values for different checks.
    #: A parameter with variants has NO ``parameter_value``: a default would be
    #: read by every caller that forgot to say which check it is doing, which
    #: is exactly the mistake the variants exist to prevent.
    variants: tuple[ParameterVariant, ...] = ()

    def __post_init__(self) -> None:
        """A missing value and a non-scalar parameter must be the same thing.

        Without this, a typo or a dropped key in the JSON would quietly produce
        a parameter with no value, and the refusal path would fire for a reason
        nobody stated. The absence of a number is only ever legitimate when the
        record says why.
        """
        if self.variants:
            if self.parameter_value is not None:
                raise ValueError(
                    f"{self.country_code}/{self.standard}:{self.parameter_name}: "
                    "un parametre a variantes ne doit pas porter aussi une valeur "
                    "unique. Elle servirait de valeur par defaut au premier "
                    "appelant qui oublie de preciser le cas, ce que les variantes "
                    "existent precisement pour empecher."
                )
            if self.validation_status is ValidationStatus.NOT_REPRESENTABLE:
                raise ValueError(
                    f"{self.country_code}/{self.standard}:{self.parameter_name}: "
                    "un parametre a variantes EST representable, par cas. Le "
                    "statut 'not_representable' est reserve a ce qu'aucun jeu "
                    "de valeurs ne peut porter."
                )
            conditions = [v.condition for v in self.variants]
            if len(set(conditions)) != len(conditions):
                raise ValueError(
                    f"{self.country_code}/{self.standard}:{self.parameter_name}: "
                    f"conditions en double dans les variantes: {conditions}"
                )
            return

        if (self.parameter_value is None) != (
            self.validation_status is ValidationStatus.NOT_REPRESENTABLE
        ):
            raise ValueError(
                f"{self.country_code}/{self.standard}:{self.parameter_name}: "
                "parameter_value est absent sans le statut 'not_representable', "
                "ou porte le statut sans etre absent. Les deux vont ensemble: "
                "un parametre sans valeur doit dire pourquoi il n'en a pas."
            )

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

    @property
    def is_conditional(self) -> bool:
        """Whether reading this parameter requires naming the check."""
        return bool(self.variants)

    def value_for(self, condition: str) -> float | None:
        """The branch matching *condition*, or ``None`` if there is none."""
        for v in self.variants:
            if v.condition == condition:
                return v.value
        return None

    @property
    def conditions(self) -> tuple[str, ...]:
        return tuple(v.condition for v in self.variants)

    @property
    def is_refused_in_every_mode(self) -> bool:
        """Statuses no mode, however permissive, may read a number through."""
        return self.validation_status in (
            ValidationStatus.DEPRECATED,
            ValidationStatus.NOT_REPRESENTABLE,
        )

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
            "source_doc_id": self.source_doc_id,
            "source_page": self.source_page,
            "source_type": self.source_type.value,
            "validation_status": self.validation_status.value,
            "verified_at": self.verified_at,
            "verified_by": self.verified_by,
            "notes": self.notes,
            "clause": self.clause,
            "description": self.description,
            "en_recommended": self.en_recommended,
            "variants": [v.to_dict() for v in self.variants],
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
