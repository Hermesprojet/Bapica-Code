"""The wire contract, exercised end to end.

A contract that is only declared drifts. These tests run real payloads through
:mod:`eurostruct_engine.service`, so the DTOs, the adapter and the engine are
checked together, and they pin the behaviours the API layer depends on.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from eurostruct_engine.exceptions import (
    NationalAnnexIncomplete,
    OutOfValidationDomain,
)
from eurostruct_engine.schemas import (
    BeamSectionDrawingRequest,
    Ec2BeamFlexureRequest,
)
from eurostruct_engine.service import error_of, render_beam_section, run_ec2_beam_flexure

REPO = Path(__file__).resolve().parents[2]

BASE_PAYLOAD = {
    "project_id": "proj_001",
    "element": "P1",
    "country": "BE",
    "strict_ndp": False,
    "as_of": "2026-07-26",
    "section": {
        "b": {"value": 300, "unit": "mm"},
        "h": {"value": 600, "unit": "mm"},
        "d": {"value": 550, "unit": "mm"},
    },
    "materials": {"concrete_grade": "C30/37", "steel_grade": "B500B"},
    "M_Ed": {"value": 250, "unit": "kN*m"},
}


def test_request_round_trips_through_json() -> None:
    req = Ec2BeamFlexureRequest.model_validate(BASE_PAYLOAD)
    again = Ec2BeamFlexureRequest.model_validate_json(req.model_dump_json())
    assert again == req


def test_full_calculation_over_the_contract() -> None:
    resp = run_ec2_beam_flexure(Ec2BeamFlexureRequest.model_validate(BASE_PAYLOAD))
    assert resp.element == "P1"
    assert resp.result.As_required.unit == "mm**2"
    assert resp.result.As_required.value == pytest.approx(1147.506009618789)
    assert resp.result.M_Rd.unit == "kN*m"
    assert resp.verification.max_utilisation == pytest.approx(1.0, abs=1e-9)
    assert resp.ndp.country == "BE"
    # The response is serialisable as-is: this is what the API returns.
    assert json.loads(resp.model_dump_json())["result"]["mu"] == pytest.approx(0.162048, abs=1e-6)


def test_unknown_field_is_rejected() -> None:
    """A typo in a payload key must fail loudly, not be dropped."""
    with pytest.raises(ValidationError, match="extra_forbidden"):
        Ec2BeamFlexureRequest.model_validate({**BASE_PAYLOAD, "M_ed": {"value": 1, "unit": "kN*m"}})


def test_negative_moment_rejected_at_the_boundary() -> None:
    payload = {**BASE_PAYLOAD, "M_Ed": {"value": -250, "unit": "kN*m"}}
    with pytest.raises(ValidationError, match="positif"):
        Ec2BeamFlexureRequest.model_validate(payload)


def test_unconfirmed_extraction_is_rejected_at_the_boundary() -> None:
    """Interdiction 5: no dimension from a drawing without human confirmation."""
    payload = {
        **BASE_PAYLOAD,
        "provenance": {
            "d": {
                "kind": "document_extraction",
                "detail": "coupe A-A, plan de coffrage",
                "document_id": "doc_42",
                "page": 3,
            }
        },
    }
    with pytest.raises(ValidationError, match="non confirmee"):
        Ec2BeamFlexureRequest.model_validate(payload)


def test_confirmed_extraction_is_accepted_and_recorded() -> None:
    payload = {
        **BASE_PAYLOAD,
        "provenance": {
            "d": {
                "kind": "document_extraction",
                "detail": "coupe A-A, plan de coffrage",
                "document_id": "doc_42",
                "page": 3,
                "bbox": [120.0, 340.0, 210.0, 358.0],
                "confirmed_by": "ing. A. Dupont",
                "confirmed_at": "2026-07-26T10:15:00Z",
            }
        },
    }
    resp = run_ec2_beam_flexure(Ec2BeamFlexureRequest.model_validate(payload))
    d_step = next(s for s in resp.journal.steps if s.symbol == "d")
    assert d_step.provenance is not None
    assert d_step.provenance.kind.value == "document_extraction"
    assert d_step.provenance.document_id == "doc_42"
    assert d_step.provenance.page == 3
    assert d_step.provenance.confirmed_by == "ing. A. Dupont"


def test_strict_mode_refusal_carries_the_whole_blocker_list() -> None:
    """TICKET 1.3: one refusal, every parameter to fix, ready for the UI."""
    payload = {**BASE_PAYLOAD, "strict_ndp": True}
    with pytest.raises(NationalAnnexIncomplete) as e:
        run_ec2_beam_flexure(Ec2BeamFlexureRequest.model_validate(payload))
    dto = error_of(e.value)
    assert dto.error == "national_annex_incomplete"
    assert dto.preflight is not None
    assert dto.preflight.ok is False
    assert len(dto.preflight.blocking) == 8
    assert {b.reason for b in dto.preflight.blocking} == {"pending_verification"}
    assert all(b.key.startswith("EN 1992-1-1:") for b in dto.preflight.blocking)


def test_out_of_domain_refusal_maps_to_a_typed_error() -> None:
    payload = {**BASE_PAYLOAD, "M_Ed": {"value": 900, "unit": "kN*m"}}
    with pytest.raises(OutOfValidationDomain) as e:
        run_ec2_beam_flexure(Ec2BeamFlexureRequest.model_validate(payload))
    dto = error_of(e.value)
    assert dto.error == "out_of_validation_domain"
    assert dto.what == "compression_reinforcement_required"
    assert dto.clause == "EN 1992-1-1 §5.5(4)"


def test_journal_crosses_the_boundary_intact() -> None:
    """Section 8.1 survives serialisation: clause, formula and trace all present."""
    resp = run_ec2_beam_flexure(Ec2BeamFlexureRequest.model_validate(BASE_PAYLOAD))
    fcd = next(s for s in resp.journal.steps if s.symbol == "f_cd")
    assert fcd.clause is not None
    assert fcd.clause.cite == "EN 1992-1-1 §3.1.6(1)P, eq. (3.15)"
    assert fcd.latex and fcd.numeric
    assert set(fcd.depends_on) == {
        "f_ck", "EN 1992-1-1:alpha_cc", "EN 1992-1-1:gamma_C_persistent",
    }


def test_drawing_contract() -> None:
    req = BeamSectionDrawingRequest.model_validate(
        {
            "project": "EUROSTRUCT",
            "element": "P1",
            "b": 300, "h": 600, "cover": 30, "link_diameter": 8,
            "bottom": [{"count": 4, "diameter": 20, "mark": "A1", "length": 6200}],
            "top": [{"count": 2, "diameter": 12, "mark": "A2", "length": 6200}],
            "link_spacing": 200,
            "concrete_grade": "C30/37", "steel_grade": "B500B",
        }
    )
    doc, schedule = render_beam_section(req)
    assert not doc.audit().errors
    marks = {r.mark for r in schedule}
    assert marks == {"A1", "A2", "C1"}
    a1 = next(r for r in schedule if r.mark == "A1")
    assert a1.mass_kg == pytest.approx(61.16, abs=0.01)


def test_generated_typescript_is_up_to_date() -> None:
    """CI guard: the checked-in contract must match the Pydantic models."""
    ts = REPO / "packages" / "contracts" / "src" / "generated" / "engine.ts"
    before = ts.read_text(encoding="utf-8")
    subprocess.run(
        [sys.executable, str(REPO / "engine" / "scripts" / "export_contracts.py")],
        cwd=REPO / "engine", check=True, capture_output=True,
    )
    assert ts.read_text(encoding="utf-8") == before, (
        "packages/contracts/src/generated/engine.ts est desynchronise des modeles "
        "Pydantic. Executer: cd engine && python scripts/export_contracts.py"
    )
