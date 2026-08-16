"""Normative rules that are not scalars.

Why this module exists
----------------------
Reading the Belgian EC2 annex clause by clause produced a result that the
scalar model could not hold: **not one** of the six parameters left "to read"
was a constant. One is a formula in ``f_ck``, one a four-branch conditional in
``sigma_cp/f_cd``, one a formula whose *variable* the annex substitutes, one a
formula with a cap in millimetres, and one a function of the reinforcement
itself. Storing ``0,6`` or ``0,75`` for those was storing a fragment.

Two provenances, not one
------------------------
A national rule normally has **two different documents behind it**, and
collapsing them loses the part that matters:

``expression_sources``
    Where the mathematics comes from. For 6.6N that is
    ``EN 1992-1-1:2004`` p. 102, plus the corrigenda and the amendment that
    were checked and found *not* to touch it. Several documents, in order,
    each with what it did or did not change.

``normative_authority``
    What makes that expression applicable **in this country**. For Belgium
    that is ``NBN EN 1992-1-1 ANB:2010 §6.2.2(6)``, folio 15: *« La valeur
    recommandée (formule 6.6N) est normative. »*

The Eurocode supplies the content; the National Annex supplies the authority.
A rule citing only the first would be applying a European recommendation; a
rule citing only the second could not show its own formula. ``9.5N`` is the
case that proves they must both be kept: the authority *modifies* the
expression — « lire f_ywk à la place de f_yk » — so the applicable rule exists
in neither document alone.

No ``eval``, ever
-----------------
Rule *metadata* is data: identity, units, domain, provenance, clause, page.
Rule *mathematics* is Python, written in this file, registered against a
``rule_id``. Nothing is executed from JSON or from the database, and there is
no expression string anywhere in the pipeline.

The two halves are tied by :func:`check_registry`, which fails if a rule
declares an implementation nobody wrote or an implementation exists for a rule
nobody declared. A test calls it.

Units are checked, not assumed
------------------------------
Every input carries a Pint dimensionality, verified on every call by
``require_dimension``. Passing ``d`` in MPa, or a bare float where a stress is
expected, raises rather than computing something plausible and wrong.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

from ..exceptions import EurostructEngineError, OutOfValidationDomain
from ..units import Q_, Quantity, require_dimension
from .model import ValidationStatus, ValueProvenance

__all__ = [
    "Branch",
    "ConditionalRule",
    "DomainBound",
    "ExpressionSource",
    "FormulaRule",
    "InputSpec",
    "NormativeAuthority",
    "NormativeFunction",
    "NormativeRule",
    "OutsideValidityDomain",
    "RuleImplementationMissing",
    "RuleKind",
    "ScalarRule",
    "all_rules",
    "check_registry",
    "find_rule",
    "get_rule",
    "implementation",
    "register",
]


class RuleKind(str, Enum):
    """What shape the annex gives this parameter."""

    #: A single number. ``gamma_C = 1,5``.
    SCALAR = "scalar"
    #: A closed-form expression of declared inputs. ``nu = 0,6[1 - f_ck/250]``.
    FORMULA = "formula"
    #: Branches selected by a declared selector. ``alpha_cw``.
    CONDITIONAL_RULE = "conditional_rule"
    #: Depends on calculation variables, possibly including results of the
    #: design itself. ``cot_theta_max``. Evaluation order is the caller's
    #: problem and must be stated — see :class:`NormativeFunction`.
    FUNCTION = "function"


#: Le moteur avait deja son exception pour ce cas, avec son code machine et sa
#: clause: en creer une jumelle aurait donne deux facons de refuser la meme
#: chose, et un appelant n'en aurait rattrape qu'une.
OutsideValidityDomain = OutOfValidationDomain


class RuleImplementationMissing(EurostructEngineError):
    """A declared rule has no registered implementation, or the reverse."""


@dataclass(frozen=True, slots=True)
class InputSpec:
    """One input of a rule, with the dimension it must have."""

    name: str
    #: Pint dimensionality string: ``"[length]"``, ``"[pressure]"``, ``""``.
    dimension: str
    description: str
    #: Unit the note de calcul prints this input in.
    display_unit: str = ""


@dataclass(frozen=True, slots=True)
class DomainBound:
    """An explicit bound of the validity domain.

    Bounds come from the text, never from what happens to work. Belgium's
    ``cot_theta_max`` prints « où σ_cp ≤ 0,2 f_cd » — that is a bound, and
    outside it the annex says nothing at all.
    """

    variable: str
    minimum: Quantity | float | None = None
    maximum: Quantity | float | None = None
    minimum_inclusive: bool = True
    maximum_inclusive: bool = True
    #: Bound expressed against ANOTHER variable rather than a constant:
    #: Belgium's ``cot_theta_max`` prints « où sigma_cp <= 0,2 f_cd », a bound
    #: that moves with the concrete class. Declaring it as data keeps it
    #: visible in the rule sheet instead of hiding inside an implementation.
    maximum_of: str | None = None
    maximum_factor: float = 1.0
    #: Quoted or paraphrased from the source, so a refusal can explain itself.
    reason: str = ""

    def check(
        self, value: Quantity, rule_id: str, others: dict[str, Quantity] | None = None
    ) -> None:
        mag = value.magnitude if isinstance(value, Quantity) else float(value)
        if self.maximum_of is not None:
            ref = (others or {}).get(self.maximum_of)
            if ref is None:
                raise RuleImplementationMissing(
                    f"{rule_id}: borne relative a '{self.maximum_of}', qui n'est "
                    "pas une variable declaree de cette regle."
                )
            limit = self.maximum_factor * ref.to(value.units).magnitude
            if mag > limit:
                raise OutsideValidityDomain(
                    "borne_relative",
                    f"{rule_id}: {self.variable} = {mag:g} depasse "
                    f"{self.maximum_factor:g}·{self.maximum_of} = {limit:g}. "
                    f"{self.reason} Aucune valeur n'est produite: hors domaine, "
                    "le texte ne dit rien et l'extrapoler serait l'inventer.",
                )
        for bound, is_min, inclusive in (
            (self.minimum, True, self.minimum_inclusive),
            (self.maximum, False, self.maximum_inclusive),
        ):
            if bound is None:
                continue
            # Une borne nue et une grandeur portant une unite ne se comparent
            # pas telles quelles. Le cas qui l'a montre: alpha = 90 degre
            # confronte a une borne ecrite en radians, ou 90 > 1,5708 et la
            # regle refusait des cadres droits — le cas le plus courant qui
            # soit. Une borne SANS unite est donc lue dans l'unite de BASE de
            # la grandeur (radian pour un angle), une borne AVEC unite est
            # convertie vers celle de la grandeur.
            if isinstance(bound, Quantity):
                b = bound.to(value.units).magnitude
                m = mag
            else:
                b = float(bound)
                m = value.to_base_units().magnitude
            bad = (m < b or (m == b and not inclusive)) if is_min else (
                m > b or (m == b and not inclusive)
            )
            if bad:
                sense = "inferieur a" if is_min else "superieur a"
                op = "<" if is_min else ">"
                raise OutsideValidityDomain(
                    "hors_bornes",
                    f"{rule_id}: {self.variable} = {m:g} est {sense} la borne "
                    f"{'' if inclusive else 'stricte '}{b:g} du domaine de "
                    f"validite ({self.variable} {op}{'=' if inclusive else ''} "
                    f"{b:g}). {self.reason} "
                    "Aucune valeur n'est produite: hors domaine, le texte ne "
                    "dit rien et l'extrapoler serait l'inventer.",
                )


@dataclass(frozen=True, slots=True)
class NormativeAuthority:
    """What makes an expression applicable in a country.

    The National Annex clause, quoted. Not the Eurocode: the Eurocode
    *recommends*, the annex *adopts*.
    """

    country_code: str
    reference: str              # "NBN EN 1992-1-1 ANB"
    edition: str                # "2010"
    clause: str                 # "§6.2.2(6)"
    #: Verbatim, so a reviewer can compare with the page in front of them.
    quote: str
    #: Folio printed on the page — what an engineer cites.
    page_printed: int | None = None
    #: Index of the page in the PDF — what a script opens. The two differ by
    #: the covers, and confusing them has already produced one wrong reference.
    page_pdf: int | None = None
    doc_id_sha256: str | None = None
    #: What the annex does to the expression: adopts it, or modifies it.
    effect: str = "adopte l'expression recommandee"


@dataclass(frozen=True, slots=True)
class ExpressionSource:
    """One layer of the documentary stack behind the mathematics.

    A layer that changed nothing is recorded too. « AC:2010 ne modifie pas
    9.5N » is a verified fact that cost work to establish, and dropping it
    would leave the next reader unable to tell a checked layer from an
    unchecked one.
    """

    reference: str              # "EN 1992-1-1:2004 (F)"
    layer: str                  # "base" | "corrigendum" | "amendement"
    clause: str                 # "§6.2.2(6)"
    expression_label: str       # "(6.6N)"
    #: What this layer did to the expression.
    effect: str                 # "texte d'origine" | "non modifiee" | "modifiee: ..."
    page_pdf: int | None = None
    doc_id_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class Branch:
    """One branch of a :class:`ConditionalRule`, over the selector value.

    The interval is **data**, so the note de calcul can print the condition and
    a test can check the boundaries against what the standard prints. The value
    is either a constant or another registered rule taking the selector.
    """

    lower: float | None
    upper: float | None
    lower_inclusive: bool = True
    upper_inclusive: bool = True
    value_scalar: float | None = None
    value_rule_id: str | None = None
    description: str = ""

    def __post_init__(self) -> None:
        if (self.value_scalar is None) == (self.value_rule_id is None):
            raise ValueError(
                f"branche '{self.description}': exactement une source de valeur "
                "est requise, un scalaire OU une regle."
            )

    def contains(self, x: float) -> bool:
        if self.lower is not None:
            if x < self.lower or (x == self.lower and not self.lower_inclusive):
                return False
        if self.upper is not None:
            if x > self.upper or (x == self.upper and not self.upper_inclusive):
                return False
        return True

    @property
    def condition_text(self) -> str:
        lo = "" if self.lower is None else (
            f"{self.lower:g} {'≤' if self.lower_inclusive else '<'} "
        )
        hi = "" if self.upper is None else (
            f" {'≤' if self.upper_inclusive else '<'} {self.upper:g}"
        )
        return f"{lo}x{hi}".strip()


# ---------------------------------------------------------------------------
# Implementations: Python, in this file, never data
# ---------------------------------------------------------------------------
_IMPLEMENTATIONS: dict[str, Callable[..., Any]] = {}
_RULES: dict[str, "NormativeRule"] = {}


def implementation(rule_id: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Register the mathematics of *rule_id*.

    The decorated function receives the validated inputs as keyword arguments,
    already unit-checked and domain-checked, and returns a Quantity.
    """

    def decorate(fn: Callable[..., Any]) -> Callable[..., Any]:
        if rule_id in _IMPLEMENTATIONS:
            raise RuleImplementationMissing(
                f"{rule_id}: deux implementations enregistrees. Une regle a une "
                "mathematique et une seule."
            )
        _IMPLEMENTATIONS[rule_id] = fn
        return fn

    return decorate


def register(rule: "NormativeRule") -> "NormativeRule":
    """Declare *rule*. Returns it, so declarations can be module constants."""
    if rule.rule_id in _RULES:
        raise RuleImplementationMissing(
            f"{rule.rule_id}: deja declaree."
        )
    _RULES[rule.rule_id] = rule
    return rule


def get_rule(rule_id: str) -> "NormativeRule":
    try:
        return _RULES[rule_id]
    except KeyError:
        raise RuleImplementationMissing(
            f"{rule_id}: regle inconnue. Regles declarees: "
            f"{', '.join(sorted(_RULES))}"
        ) from None


def find_rule(country_code: str, name: str) -> "NormativeRule | None":
    """The typed rule a jurisdiction uses for *name*, or ``None``.

    ``None`` means this country has no transcribed rule yet and still runs on
    scalars. It does NOT mean "fall back to the Eurocode": the scalar path is
    itself national data, and a country either has its rule or has its scalar.

    One normative path per jurisdiction is the invariant. It is enforced from
    the other side too: once a rule is branched in, the scalar it replaces is
    marked DEPRECATED for that country, and DEPRECATED is refused in every
    mode. A second path cannot survive silently.
    """
    return _RULES.get(f"{country_code.lower()}.ec2.{name}")


def all_rules() -> tuple["NormativeRule", ...]:
    return tuple(_RULES[k] for k in sorted(_RULES))


def check_registry() -> None:
    """Fail if declarations and implementations have drifted apart.

    The whole no-``eval`` design rests on data and code being two halves of one
    thing. Nothing but this check keeps them from separating silently.
    """
    needs_impl = {
        r.rule_id for r in _RULES.values()
        if r.rule_type in (RuleKind.FORMULA, RuleKind.FUNCTION)
    }
    missing = needs_impl - set(_IMPLEMENTATIONS)
    orphan = set(_IMPLEMENTATIONS) - {r.rule_id for r in _RULES.values()}
    if missing:
        raise RuleImplementationMissing(
            f"regles declarees sans mathematique: {sorted(missing)}"
        )
    if orphan:
        raise RuleImplementationMissing(
            f"mathematique enregistree sans regle declaree: {sorted(orphan)}"
        )


# ---------------------------------------------------------------------------
# The rule types
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class NormativeRule:
    """Common declaration of a normative rule, whatever its shape."""

    rule_id: str
    rule_type: RuleKind
    description: str
    #: Unit of the result, as a Pint string. ``"dimensionless"`` where it has none.
    output_unit: str
    normative_authority: NormativeAuthority
    expression_sources: tuple[ExpressionSource, ...]
    validation_status: ValidationStatus
    value_provenance: ValueProvenance
    inputs: tuple[InputSpec, ...] = ()
    domain: tuple[DomainBound, ...] = ()
    #: Names of the tests that exercise this rule. Not decoration: a rule whose
    #: list is empty is a rule nobody checked, and the report says so.
    tests: tuple[str, ...] = ()
    notes: str = ""

    @property
    def usable_in_strict_mode(self) -> bool:
        return (
            self.validation_status is ValidationStatus.CONFIRMED
            and self.value_provenance.is_national
        )

    @property
    def provenance_chain(self) -> tuple[str, ...]:
        """The chain, in reading order, for the note de calcul and the audit."""
        chain = [
            f"{s.reference} {s.clause} {s.expression_label} — {s.effect}"
            for s in self.expression_sources
        ]
        a = self.normative_authority
        page = (f", folio {a.page_printed}" if a.page_printed else "")
        chain.append(
            f"{a.reference}:{a.edition} {a.clause}{page} — {a.effect}"
        )
        chain.append(f"regle moteur: {self.rule_id}")
        chain.append(
            "tests: " + (", ".join(self.tests) if self.tests else "AUCUN")
        )
        return tuple(chain)

    def _validate_inputs(self, kwargs: dict[str, Any]) -> dict[str, Quantity]:
        expected = {i.name for i in self.inputs}
        missing = expected - set(kwargs)
        extra = set(kwargs) - expected
        if missing:
            raise TypeError(
                f"{self.rule_id}: variable(s) manquante(s): {sorted(missing)}. "
                f"Attendues: {sorted(expected)}"
            )
        if extra:
            raise TypeError(
                f"{self.rule_id}: variable(s) inconnue(s): {sorted(extra)}. "
                "Une variable non declaree ne peut pas etre utilisee sans que "
                "la regle le dise."
            )
        checked = {
            spec.name: require_dimension(kwargs[spec.name], spec.dimension, spec.name)
            for spec in self.inputs
        }
        by_name = {d.variable: d for d in self.domain}
        for name, value in checked.items():
            if name in by_name:
                by_name[name].check(value, self.rule_id, checked)
        return checked

    def evaluate(self, **kwargs: Any) -> Quantity:  # pragma: no cover - override
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class ScalarRule(NormativeRule):
    """A single number. Kept in the same family so a caller can treat all
    four uniformly, and so a scalar carries the same provenance chain."""

    value: float = 0.0

    def evaluate(self, **kwargs: Any) -> Quantity:
        self._validate_inputs(kwargs)
        return Q_(self.value, self.output_unit)


@dataclass(frozen=True, slots=True)
class FormulaRule(NormativeRule):
    """A closed-form expression of its declared inputs."""

    def evaluate(self, **kwargs: Any) -> Quantity:
        checked = self._validate_inputs(kwargs)
        try:
            fn = _IMPLEMENTATIONS[self.rule_id]
        except KeyError:
            raise RuleImplementationMissing(
                f"{self.rule_id}: declaree sans mathematique."
            ) from None
        out = fn(**checked)
        return require_dimension(out, _dim_of(self.output_unit), f"{self.rule_id}()")


@dataclass(frozen=True, slots=True)
class ConditionalRule(NormativeRule):
    """Branches over a selector, both declared as data.

    ``alpha_cw`` is the shape: four branches on ``sigma_cp/f_cd``, three of
    which the EN prints as intervals and one as "non-prestressed structures".
    Keeping the intervals as data means the note can print the condition that
    was actually used, and a test can check the boundaries against the printed
    text rather than against the code that implements them.
    """

    #: Rule producing the (dimensionless) selector from the inputs.
    selector_rule_id: str = ""
    branches: tuple[Branch, ...] = ()

    def evaluate(self, **kwargs: Any) -> Quantity:
        checked = self._validate_inputs(kwargs)
        selector = get_rule(self.selector_rule_id).evaluate(**checked)
        x = float(selector.to("dimensionless").magnitude)
        for branch in self.branches:
            if branch.contains(x):
                if branch.value_scalar is not None:
                    return Q_(branch.value_scalar, self.output_unit)
                return get_rule(branch.value_rule_id).evaluate(x=selector)
        raise OutsideValidityDomain(
            "aucune_branche",
            f"{self.rule_id}: le selecteur vaut {x:g}, qui ne tombe dans aucune "
            "branche declaree: "
            + " ; ".join(f"[{b.condition_text}]" for b in self.branches)
            + ". Le texte ne couvre pas ce cas et rien n'est produit.",
        )

    def branch_for(self, x: float) -> Branch | None:
        return next((b for b in self.branches if b.contains(x)), None)


@dataclass(frozen=True, slots=True)
class NormativeFunction(NormativeRule):
    """Depends on calculation variables, including design results.

    Different from :class:`FormulaRule` in one respect that is not
    mathematical: **when** it can be evaluated. ``cot_theta_max`` depends on
    ``A_sw`` and ``s``, which are outputs of the very design it constrains.

    :attr:`evaluation_order` states how the caller must handle that. It is
    declared, not left to whoever writes the calling module, because an
    implicit circular dependency is exactly the failure this field exists to
    prevent.
    """

    #: How the caller must sequence this. Free text, but it must be filled:
    #: see ``__post_init__``.
    evaluation_order: str = ""

    def __post_init__(self) -> None:
        if not self.evaluation_order.strip():
            raise ValueError(
                f"{self.rule_id}: une NormativeFunction doit declarer son ordre "
                "d'evaluation. Elle depend de variables de calcul, parfois du "
                "resultat qu'elle contraint; ne pas le dire laisserait une "
                "dependance circulaire implicite dans le module appelant."
            )

    def evaluate(self, **kwargs: Any) -> Quantity:
        checked = self._validate_inputs(kwargs)
        try:
            fn = _IMPLEMENTATIONS[self.rule_id]
        except KeyError:
            raise RuleImplementationMissing(
                f"{self.rule_id}: declaree sans mathematique."
            ) from None
        out = fn(**checked)
        return require_dimension(out, _dim_of(self.output_unit), f"{self.rule_id}()")


def _dim_of(unit: str) -> str:
    """Pint dimensionality string for a unit name, for output checking."""
    if unit in ("", "dimensionless"):
        return ""
    return str(Q_(1.0, unit).dimensionality)
