"""Versioning of the deterministic calculation engine.

The engine version is stamped into every calculation result and into every
generated deliverable (EN 1990 based notes de calcul, DXF drawings).

Versioning contract (see docs/VALIDATION.md):

* PATCH  -- changes that cannot alter any numeric result (docs, typing,
            refactors covered by the golden tests).
* MINOR  -- new verification modules, new National Annex data sets. Existing
            numeric results must remain bit-for-bit identical.
* MAJOR  -- any change that alters a previously produced numeric result, even
            by one ULP. Requires a release note listing every changed value.

The golden-test suite (tests/test_determinism.py) is what enforces this: a
result that changes without a MAJOR bump fails CI.
"""

from __future__ import annotations

from typing import Final

__all__ = ["ENGINE_NAME", "ENGINE_VERSION", "engine_stamp"]

ENGINE_NAME: Final[str] = "eurostruct-engine"

#: Semantic version of the deterministic engine.
ENGINE_VERSION: Final[str] = "0.1.0"


def engine_stamp() -> str:
    """Return the identifier written into results and deliverables."""
    return f"{ENGINE_NAME} {ENGINE_VERSION}"
