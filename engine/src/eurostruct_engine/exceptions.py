"""Engine exception hierarchy.

Design rule (cahier des charges section 8.3): the engine never returns an
approximate answer when it is asked something outside the domain it has been
validated for. It raises, and the application surfaces
"hors domaine de validation -- etude specifique requise".

Never catch :class:`OutOfValidationDomain` to substitute a fallback value.
"""

from __future__ import annotations

__all__ = [
    "EurostructEngineError",
    "OutOfValidationDomain",
    "UnverifiedNationalParameter",
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
            "Un calcul destine a un livrable signe exige le statut "
            "'na_confirmed' (valeur relevee dans l'Annexe Nationale publiee). "
            "Faire verifier et confirmer ce parametre par un ingenieur habilite."
        )


class InconsistentInput(EurostructEngineError):
    """Input data is self-contradictory (e.g. effective depth exceeding depth)."""


class UnitError(EurostructEngineError):
    """A quantity was supplied in a physically wrong dimension."""
