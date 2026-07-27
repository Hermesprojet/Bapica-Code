"""Engine exception hierarchy.

Design rule (cahier des charges section 8.3): the engine never returns an
approximate answer when it is asked something outside the domain it has been
validated for. It raises, and the application surfaces
"hors domaine de validation -- etude specifique requise".

Never catch :class:`OutOfValidationDomain` to substitute a fallback value.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from .ndp.registry import PreflightReport

__all__ = [
    "EurostructEngineError",
    "OutOfValidationDomain",
    "UnverifiedNationalParameter",
    "DeprecatedNationalParameter",
    "UnrepresentableNationalParameter",
    "ConditionalParameterNeedsContext",
    "NationalAnnexIncomplete",
    "InconsistentInput",
    "UnitError",
]


class EurostructEngineError(Exception):
    """Base class for every error raised by the calculation engine."""


class OutOfValidationDomain(EurostructEngineError):
    """The requested configuration lies outside the validated domain.

    Raised instead of returning a result the engine cannot stand behind.

    :param what: short machine-readable reason code.
    :param detail: human readable explanation shown to the engineer.
    :param clause: the normative clause that bounds the domain, if any.
    """

    def __init__(self, what: str, detail: str, clause: str | None = None) -> None:
        self.what = what
        self.detail = detail
        self.clause = clause
        suffix = f" [{clause}]" if clause else ""
        super().__init__(f"hors domaine de validation ({what}): {detail}{suffix}")


class UnverifiedNationalParameter(EurostructEngineError):
    """A nationally determined parameter has not been verified against the
    published National Annex, and the engine is running in strict mode.

    See :mod:`eurostruct_engine.ndp.registry`.
    """

    def __init__(self, key: str, country: str, status: str) -> None:
        self.key = key
        self.country = country
        self.status = status
        super().__init__(
            f"NDP '{key}' pour le pays '{country}' a le statut '{status}'. "
            "Un calcul destine a un livrable signe exige le statut 'confirmed' "
            "(valeur relevee dans l'Annexe Nationale publiee, page citee). "
            "C'est la validation NORMATIVE, niveau 1: elle porte sur le "
            "referentiel du pays et se fait une fois. Un ingenieur du bureau "
            "d'etudes la realise; aucun tiers exterieur n'est requis."
        )


class DeprecatedNationalParameter(EurostructEngineError):
    """A national value marked superseded was requested.

    Refused in every mode, strict or not: unlike an unverified value, a
    deprecated one is known to be wrong.
    """

    def __init__(self, key: str, notes: str | None = None) -> None:
        self.key = key
        self.notes = notes
        detail = f" {notes}" if notes else ""
        super().__init__(
            f"le parametre national '{key}' est marque obsolete et ne peut pas "
            f"etre utilise.{detail} Charger l'edition en vigueur de l'Annexe "
            "Nationale."
        )


class UnrepresentableNationalParameter(EurostructEngineError):
    """The National Annex fixes this parameter as something other than a number.

    Refused in every mode. Unlike :class:`UnverifiedNationalParameter`, no
    engineer's signature can unblock it: there is no scalar to confirm. The
    calculation module must be extended to evaluate the annex's expression.
    """

    def __init__(self, key: str, notes: str | None = None) -> None:
        self.key = key
        self.notes = notes
        detail = f" {notes}" if notes else ""
        super().__init__(
            f"le parametre national '{key}' n'a pas de valeur scalaire: "
            f"l'Annexe Nationale le fixe sous une forme que le moteur ne sait "
            f"pas encore evaluer.{detail} Aucune valeur de substitution n'est "
            "utilisee: etendre le module de calcul avant de traiter ce cas."
        )


class ConditionalParameterNeedsContext(EurostructEngineError):
    """A parameter with per-check branches was read without naming the check.

    Refusing is the whole point. NBN EN 1992-1-1 ANB gives alpha_cc = 0,85 for
    axial force and bending and 1,0 otherwise; a caller that does not say which
    it is doing cannot be served a value, because either answer is wrong half
    the time and neither would announce itself.
    """

    def __init__(self, key: str, conditions: tuple[str, ...], given: str | None) -> None:
        self.key = key
        self.conditions = conditions
        self.given = given
        known = ", ".join(conditions)
        if given is None:
            detail = (
                "aucun cas n'a ete precise. Le module de calcul doit dire "
                "laquelle des verifications il effectue."
            )
        else:
            detail = f"le cas '{given}' n'est pas prevu par cette Annexe Nationale."
        super().__init__(
            f"le parametre national '{key}' prend une valeur differente selon "
            f"la verification effectuee: {detail} Cas definis: {known}."
        )


class NationalAnnexIncomplete(EurostructEngineError):
    """Preflight found national parameters that block the calculation.

    TICKET 1.3: carries **every** blocker, not just the first, so one pass
    tells the user the whole list. ``report`` is the machine-readable form used
    by the API and by CI; ``str(exc)`` is the human one.
    """

    def __init__(self, report: "PreflightReport") -> None:
        self.report = report
        self.blocking = report.blocking
        super().__init__(report.render())

    def to_dict(self) -> dict[str, Any]:
        return self.report.to_dict()


class InconsistentInput(EurostructEngineError):
    """Input data is self-contradictory (e.g. effective depth exceeding depth)."""


class UnitError(EurostructEngineError):
    """A quantity was supplied in a physically wrong dimension."""
