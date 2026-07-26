"""Nationally Determined Parameters (NDP) registry.

Cahier des charges section 4.2, and interdictions 2 and 3:

    "Les Eurocodes sont un tronc commun ; les parametres determines
     nationalement changent les resultats. Ils doivent etre stockes en base de
     donnees parametrable, jamais codes en dur."

    "Ne jamais inventer une valeur non tracee a une source."
    "Ne jamais appliquer un Eurocode sans son Annexe Nationale, ou supposer une
     AN par defaut."

Honesty model
-------------
Each parameter carries a :class:`NdpStatus` that says how much the value can be
trusted:

``EN_RECOMMENDED``
    The value printed in the Note of the Eurocode clause itself. Verifiable by
    anyone holding EN 1992-1-1. Safe to use for study work, but it is *not*
    necessarily what the country adopted.

``NA_CONFIRMED``
    The value has been read in the published National Annex by a named engineer
    and recorded with the document reference and the date. Only this status is
    acceptable for a signed deliverable.

``NA_PENDING_VERIFICATION``
    A value believed to apply in the country but not yet checked against the
    published National Annex.

The engine refuses to run in ``strict`` mode on anything other than
``NA_CONFIRMED``. That refusal is the mechanism which prevents the product from
shipping a note de calcul built on an assumed National Annex.

The JSON files in ``data/`` are the source of truth for the seed of the
``national_annex_parameters`` table; the database is authoritative at runtime,
and these files are what is loaded into it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Final

from ..exceptions import UnverifiedNationalParameter
from ..traceability import Clause, Journal, Provenance
from ..units import Q_, Quantity

__all__ = ["NdpStatus", "NdpValue", "ParameterSet", "load_parameter_set", "available_countries"]

_DATA_DIR: Final[Path] = Path(__file__).parent / "data"


class NdpStatus(str, Enum):
    EN_RECOMMENDED = "en_recommended"
    NA_CONFIRMED = "na_confirmed"
    NA_PENDING_VERIFICATION = "na_pending_verification"


@dataclass(frozen=True, slots=True)
class NdpValue:
    """One nationally determined parameter."""

    key: str
    value: float
    unit: str
    status: NdpStatus
    standard: str
    clause: str
    description: str
    source: str
    #: EN recommended value, kept alongside so the note de calcul can show the
    #: national value *and* what it departs from.
    en_recommended: float | None = None
    confirmed_by: str | None = None
    confirmed_at: str | None = None

    def as_quantity(self) -> Quantity:
        return Q_(self.value, self.unit)

    def to_clause(self) -> Clause:
        note = f"{self.source} [{self.status.value}]"
        if self.en_recommended is not None and self.en_recommended != self.value:
            note += f" (valeur recommandee EN: {self.en_recommended})"
        return Clause(
            standard=self.standard,
            clause=self.clause,
            equation=None,
            national_note=note,
        )


@dataclass(frozen=True)
class ParameterSet:
    """The set of NDPs applicable to one country/region, at one version.

    Frozen into the calculation and printed in the note de calcul together with
    its version and date, per cahier des charges section 4.2.
    """

    country: str
    region: str | None
    version: str
    published_at: str
    description: str
    values: dict[str, NdpValue]
    strict: bool = True

    def with_strict(self, strict: bool) -> "ParameterSet":
        """Return the same set with a different strictness.

        ``strict=False`` is for exploratory / pre-design work and must never be
        used to produce a signed deliverable.
        """
        return ParameterSet(
            country=self.country,
            region=self.region,
            version=self.version,
            published_at=self.published_at,
            description=self.description,
            values=self.values,
            strict=strict,
        )

    def get(self, key: str, journal: Journal | None = None) -> Quantity:
        """Fetch a parameter, recording its provenance in *journal*.

        :raises KeyError: if the parameter is not defined for this country. The
            engine never falls back to the EN recommended value silently: a
            missing NDP is a data gap that must be filled, not guessed.
        :raises UnverifiedNationalParameter: in strict mode, if the value has
            not been confirmed against the published National Annex.
        """
        try:
            ndp = self.values[key]
        except KeyError:
            raise KeyError(
                f"NDP '{key}' non defini pour le pays '{self.country}'"
                f"{f'/{self.region}' if self.region else ''}. "
                "Aucune valeur par defaut n'est substituee: renseigner ce "
                "parametre dans le jeu de NDP avant de calculer."
            ) from None

        if self.strict and ndp.status is not NdpStatus.NA_CONFIRMED:
            raise UnverifiedNationalParameter(key, self.country, ndp.status.value)

        q = ndp.as_quantity()
        if journal is not None and key not in journal._index:  # noqa: SLF001
            journal.input(
                symbol=key,
                description=ndp.description,
                value=q,
                provenance=Provenance.national_annex(key, ndp.source),
                clause=ndp.to_clause(),
            )
        return q

    def unverified_keys(self) -> list[str]:
        """Keys not yet confirmed against the published National Annex."""
        return sorted(
            k for k, v in self.values.items() if v.status is not NdpStatus.NA_CONFIRMED
        )

    def summary(self) -> dict[str, Any]:
        """What the note de calcul prints in its 'referentiel applique' section."""
        return {
            "country": self.country,
            "region": self.region,
            "version": self.version,
            "published_at": self.published_at,
            "description": self.description,
            "strict": self.strict,
            "unverified": self.unverified_keys(),
            "parameters": {
                k: {
                    "value": v.value,
                    "unit": v.unit,
                    "status": v.status.value,
                    "clause": f"{v.standard} {v.clause}",
                    "source": v.source,
                    "en_recommended": v.en_recommended,
                }
                for k, v in sorted(self.values.items())
            },
        }


def available_countries() -> list[str]:
    return sorted(p.stem.upper() for p in _DATA_DIR.glob("*.json"))


@lru_cache(maxsize=None)
def _load_raw(country: str) -> dict[str, Any]:
    path = _DATA_DIR / f"{country.lower()}.json"
    if not path.exists():
        raise KeyError(
            f"aucun jeu de NDP pour le pays '{country}'. "
            f"Pays disponibles: {', '.join(available_countries()) or 'aucun'}."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def load_parameter_set(
    country: str,
    region: str | None = None,
    strict: bool = True,
) -> ParameterSet:
    """Load the NDP set for *country*.

    :param country: ISO 3166-1 alpha-2, e.g. ``"BE"``, ``"FR"``.
    :param region: sub-national region where it changes the parameters
        (Wallonie / Vlaanderen / Bruxelles, Land, Comunidad autonoma).
    :param strict: when True (the default), reading a parameter that has not
        been confirmed against the published National Annex raises.
    """
    raw = _load_raw(country.upper())
    values = {
        key: NdpValue(
            key=key,
            value=float(item["value"]),
            unit=item.get("unit", "dimensionless"),
            status=NdpStatus(item["status"]),
            standard=item["standard"],
            clause=item["clause"],
            description=item["description"],
            source=item["source"],
            en_recommended=item.get("en_recommended"),
            confirmed_by=item.get("confirmed_by"),
            confirmed_at=item.get("confirmed_at"),
        )
        for key, item in raw["parameters"].items()
    }
    return ParameterSet(
        country=raw["country"],
        region=region,
        version=raw["version"],
        published_at=raw["published_at"],
        description=raw["description"],
        values=values,
        strict=strict,
    )
