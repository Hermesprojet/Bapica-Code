"""Load the dependency-audit script as a module, for testing it.

The audit is a standalone script (it must run in CI without the package
installed), so importing it needs a little machinery. Keeping that here rather
than in the test file keeps the tests readable.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

AUDIT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "audit_engine_dependencies.py"


def load_audit() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_audit", AUDIT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
