"""The engine is deterministic and offline — EPIC 3.1 and TICKET 6.2.

    "Aucune valeur de calcul ne peut provenir d'un LLM.
     Le moteur est executable hors ligne.
     La CI echoue si une dependance IA est introduite dans le noyau calcul."

The first two are proven here by construction rather than asserted: the network
is switched off at the socket layer, and a complete calculation plus a complete
DXF are produced with it off. Any attempt to reach a model API — ours or a
dependency's — would raise instead of quietly succeeding.
"""

from __future__ import annotations

import socket
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest
from audit_helper import load_audit

from eurostruct_engine.drawing import BarRow, BeamSectionSpec, build_beam_section
from eurostruct_engine.ec2 import RectangularSection, design_flexure
from eurostruct_engine.materials import concrete, reinforcement
from eurostruct_engine.materials.reinforcement import bars_area
from eurostruct_engine.ndp import load_parameter_set
from eurostruct_engine.reference import run_library
from eurostruct_engine.units import Q_

ENGINE = Path(__file__).resolve().parents[1]
AUDIT = ENGINE / "scripts" / "audit_engine_dependencies.py"


@pytest.fixture
def network_disabled(monkeypatch):
    """Make any outbound connection impossible for the duration of a test."""

    def refuse(*args, **kwargs):
        raise AssertionError(
            "le moteur de calcul a tente d'ouvrir une connexion reseau. "
            "Interdiction 1: le noyau numerique est hors ligne par construction."
        )

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)
    return None


def test_full_calculation_runs_with_the_network_off(network_disabled) -> None:
    """A complete verification, offline."""
    params = load_parameter_set("BE", strict=False, as_of=date(2026, 7, 26))
    r = design_flexure(
        section=RectangularSection(b=Q_(300, "mm"), h=Q_(600, "mm"), d=Q_(550, "mm")),
        concrete=concrete("C30/37"),
        steel=reinforcement("B500B"),
        M_Ed=Q_(250, "kN*m"),
        params=params,
        element="P1",
        A_s_provided=bars_area(4, 20),
    )
    assert r.As_required.to("mm**2").magnitude == pytest.approx(1147.506009618789)
    assert r.report.passed
    assert r.journal.steps


def test_drawing_generation_runs_with_the_network_off(network_disabled) -> None:
    doc, schedule = build_beam_section(
        BeamSectionSpec(
            b=300, h=600, cover=30, link_diameter=8,
            bottom=(BarRow(count=4, diameter=20, mark="A1", length=6200),),
            link_spacing=200,
        )
    )
    assert not doc.audit().errors
    assert schedule


def test_reference_suite_runs_with_the_network_off(network_disabled) -> None:
    """Even the validation harness is offline."""
    report = run_library()
    assert report.ok


def test_serialisation_runs_with_the_network_off(network_disabled) -> None:
    from eurostruct_engine.schemas import Ec2BeamFlexureRequest
    from eurostruct_engine.service import run_ec2_beam_flexure

    resp = run_ec2_beam_flexure(
        Ec2BeamFlexureRequest.model_validate(
            {
                "project_id": "p", "country": "BE", "strict_ndp": False,
                "as_of": "2026-07-26",
                "section": {
                    "b": {"value": 300, "unit": "mm"},
                    "h": {"value": 600, "unit": "mm"},
                    "d": {"value": 550, "unit": "mm"},
                },
                "materials": {"concrete_grade": "C30/37", "steel_grade": "B500B"},
                "M_Ed": {"value": 250, "unit": "kN*m"},
            }
        )
    )
    assert resp.model_dump_json()


# ---------------------------------------------------------------------------
# The audit itself
# ---------------------------------------------------------------------------
def _run_audit(env_extra: dict[str, str] | None = None):
    import os

    env = dict(os.environ)
    env.update(env_extra or {})
    return subprocess.run(
        [sys.executable, str(AUDIT)], capture_output=True, text=True, env=env
    )


def test_dependency_audit_passes() -> None:
    out = _run_audit()
    assert out.returncode == 0, out.stdout + out.stderr
    assert "aucun import reseau ni IA" in out.stdout


def test_audit_lists_every_transitive_dependency() -> None:
    """The audit walks installed metadata, not just the declared direct deps."""
    audit = load_audit()
    tree = audit.walk_tree()
    # Direct dependencies.
    assert {"pint", "pydantic", "ezdxf", "numpy"} <= set(tree)
    # And at least one package nobody declared, reached transitively.
    assert "pydantic-core" in tree
    assert set(tree) <= set(audit.ALLOWED)


def test_audit_would_reject_an_ai_dependency() -> None:
    """The denylist is what makes an accidental allowlist entry harmless."""
    audit = load_audit()
    assert "openai" in audit.DENIED_PACKAGES
    assert "anthropic" in audit.DENIED_PACKAGES
    assert "langchain" in audit.DENIED_PACKAGES
    # And an HTTP stack is refused too: that is how a model API would be reached.
    assert {"requests", "httpx", "aiohttp"} <= audit.DENIED_PACKAGES


def test_audit_scans_imports_inside_function_bodies(tmp_path) -> None:
    """A deferred import must not slip past the scan."""
    audit = load_audit()
    (tmp_path / "sneaky.py").write_text(
        "def fetch():\n"
        "    import requests  # deliberately hidden inside a function body\n"
        "    return requests\n",
        encoding="utf-8",
    )
    (tmp_path / "clean.py").write_text("import math\n", encoding="utf-8")

    offenders = audit.scan_imports(tmp_path)
    assert [(p.name, name) for p, _, name in offenders] == [("sneaky.py", "requests")]


def test_no_engine_module_imports_a_network_module() -> None:
    audit = load_audit()
    assert audit.scan_imports() == []
