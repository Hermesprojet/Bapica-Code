"""Basis of design concepts — EN 1990.

Only the parts needed by the P0 vertical are implemented here. Combinations
(§6.4.3, expressions 6.10 / 6.10a / 6.10b) belong to a dedicated module and are
not part of this release.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["DesignSituation", "ConsequenceClass", "LimitState"]


class DesignSituation(str, Enum):
    """Design situations — EN 1990 §3.2.

    The situation selects which partial factors apply, e.g. ``gamma_C`` = 1,5
    for persistent/transient versus 1,2 for accidental in the EN recommended
    set (EN 1992-1-1 Tab. 2.1N).
    """

    PERSISTENT = "persistent"
    TRANSIENT = "transient"
    ACCIDENTAL = "accidental"
    SEISMIC = "seismic"

    @property
    def partial_factor_suffix(self) -> str:
        """The NDP key suffix used for this situation.

        Persistent and transient share the same partial factors; accidental and
        seismic share the accidental set.
        """
        if self in (DesignSituation.PERSISTENT, DesignSituation.TRANSIENT):
            return "persistent"
        return "accidental"


class ConsequenceClass(str, Enum):
    """Consequence classes — EN 1990 Annex B, Table B1."""

    CC1 = "CC1"
    CC2 = "CC2"
    CC3 = "CC3"


class LimitState(str, Enum):
    """Limit states — EN 1990 §3.3 and §3.4."""

    ULS = "ULS"
    SLS = "SLS"
