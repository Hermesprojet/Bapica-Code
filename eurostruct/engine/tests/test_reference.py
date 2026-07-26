"""Reference-case library and runner — EPIC 2.

The library is the mechanism by which the engine is proven right against
something other than itself. These tests check the mechanism: that cases load,
replay, compare within their own tolerance, journalise every difference, and
fail CI when — and only when — a case that could run actually drifted.
"""

from __future__ import annotations

import dataclasses
import json

import pytest

from eurostruct_engine.reference import (
    LIBRARY_DIR,
    ReferenceSourceType,
    ReferenceStatus,
    ToleranceRule,
    available_harnesses,
    load_library,
    run_case,
    run_library,
)

LIBRARY = load_library()
RUNNABLE = [c for c in LIBRARY if c.has_expectations]


# ---------------------------------------------------------------------------
# TICKET 2.1 — the model
# ---------------------------------------------------------------------------
def test_library_loads() -> None:
    assert LIBRARY, "bibliotheque de cas de reference vide"


def test_identifiers_are_unique() -> None:
    """Acceptance criterion: each case has a unique identifier."""
    ids = [c.reference_id for c in LIBRARY]
    assert len(ids) == len(set(ids))


def test_every_case_declares_source_scope_and_tolerance() -> None:
    """Acceptance criterion: each case has a source and a tolerance."""
    for c in LIBRARY:
        assert c.reference_id and c.title
        assert c.normative_scope, f"{c.reference_id}: perimetre normatif manquant"
        assert c.country_scope, f"{c.reference_id}: perimetre pays manquant"
        assert c.source_document.title, f"{c.reference_id}: source sans titre"
        assert isinstance(c.source_type, ReferenceSourceType)
        if c.expected_outputs:
            assert c.tolerance_rules, f"{c.reference_id}: aucune tolerance definie"
            for name in c.expected_outputs:
                assert c.tolerance_for(name) is not None, (
                    f"{c.reference_id}: pas de regle de tolerance pour '{name}'"
                )


def test_tolerance_ceiling_is_enforced() -> None:
    """§8.2 caps a reference case at 1 %; the model refuses anything looser."""
    with pytest.raises(ValueError, match="plafond de 1 %"):
        ToleranceRule(output="As", rel=0.05)
    with pytest.raises(ValueError, match="doit fixer rel ou abs"):
        ToleranceRule(output="As")


def test_expected_and_computed_are_stored_separately() -> None:
    """A case must not be able to absorb the engine's own answer."""
    result = run_case(RUNNABLE[0])
    assert result.case.expected_outputs
    assert result.computed_outputs
    # Distinct mappings, and the case object is frozen.
    assert result.case.expected_outputs is not result.computed_outputs
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.case.expected_outputs = {}  # type: ignore[misc]


# ---------------------------------------------------------------------------
# TICKET 2.2 — the runner
# ---------------------------------------------------------------------------
@pytest.mark.reference
def test_every_runnable_case_passes() -> None:
    """The blocking gate: a case that can run and drifts fails CI."""
    report = run_library()
    assert report.ok, "\n" + report.render()


@pytest.mark.reference
def test_numeric_cases_agree_with_an_independent_method() -> None:
    """Expected values come from bisection on equilibrium, not from the engine.

    The engine inverts the moment equation in closed form. The library's
    expectations were produced by solving the same equilibrium numerically. The
    two methods agreeing to 1e-9 is what these cases attest.
    """
    numeric = [c for c in RUNNABLE if c.expect_refusal is None]
    assert len(numeric) >= 5
    for case in numeric:
        result = run_case(case)
        assert result.status is ReferenceStatus.PASSED, result.render()
        assert result.delta_report
        for d in result.delta_report:
            assert d.rel_diff < 1e-9, d.render()


def test_refusal_cases_are_verified_as_refusals() -> None:
    """Interdiction 6: outside the domain the engine must refuse, not approximate."""
    refusals = [c for c in LIBRARY if c.expect_refusal]
    assert refusals
    for case in refusals:
        result = run_case(case)
        assert result.status is ReferenceStatus.REFUSED, result.render()


def test_a_drifting_case_fails() -> None:
    """The runner must actually catch a wrong answer."""
    good = next(c for c in RUNNABLE if c.expect_refusal is None)
    tampered = dataclasses.replace(
        good,
        reference_id=good.reference_id + "-TAMPERED",
        expected_outputs={**good.expected_outputs, "As_strength_mm2": 1.0},
    )
    result = run_case(tampered)
    assert result.status is ReferenceStatus.FAILED
    assert result.blocking
    assert result.failures()
    assert "As_strength_mm2" in result.message
    # The difference is journalised, not just the verdict.
    delta = next(d for d in result.delta_report if d.output == "As_strength_mm2")
    assert delta.expected == 1.0
    assert delta.computed > 100.0
    assert delta.rel_diff > 100.0


def test_a_case_expecting_a_refusal_that_computes_fails() -> None:
    good = next(c for c in RUNNABLE if c.expect_refusal is None)
    tampered = dataclasses.replace(
        good,
        reference_id=good.reference_id + "-NOREFUSAL",
        expect_refusal="compression_reinforcement_required",
    )
    result = run_case(tampered)
    assert result.status is ReferenceStatus.FAILED
    assert "produit un resultat" in result.message


def test_a_case_expecting_the_wrong_refusal_fails() -> None:
    refusal = next(c for c in LIBRARY if c.expect_refusal)
    tampered = dataclasses.replace(
        refusal,
        reference_id=refusal.reference_id + "-WRONG",
        expect_refusal="some_other_reason",
    )
    result = run_case(tampered)
    assert result.status is ReferenceStatus.FAILED
    assert "refus attendu 'some_other_reason'" in result.message


def test_missing_output_is_a_failure_not_a_pass() -> None:
    """An expectation the engine does not produce must never read as green."""
    good = next(c for c in RUNNABLE if c.expect_refusal is None)
    tampered = dataclasses.replace(
        good,
        reference_id=good.reference_id + "-MISSING",
        expected_outputs={**good.expected_outputs, "sortie_inexistante": 1.0},
    )
    result = run_case(tampered)
    assert result.status is ReferenceStatus.FAILED
    assert "sortie_inexistante" in result.message


def test_duplicate_identifier_is_refused(tmp_path) -> None:
    payload = {"cases": [LIBRARY[0].to_dict(), LIBRARY[0].to_dict()]}
    (tmp_path / "dup.json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="duplique"):
        load_library(tmp_path)


# ---------------------------------------------------------------------------
# TICKET 2.3 — coverage of the initial library
# ---------------------------------------------------------------------------
def test_gaps_are_reported_but_do_not_fail_the_build() -> None:
    """A missing published source is a gap, not a regression.

    Deliberate: if an absent source failed the build, the pressure would be to
    invent one.
    """
    report = run_library()
    gaps = report.coverage_gaps()
    assert gaps, "aucune lacune declaree — la couverture planifiee a disparu"
    assert report.ok
    for g in gaps:
        assert g.status in (
            ReferenceStatus.AWAITING_SOURCE, ReferenceStatus.AWAITING_MODULE
        )
        assert not g.blocking
        assert g.message


def test_awaiting_source_cases_cite_no_invented_reference() -> None:
    """A placeholder must not name a document nobody has opened."""
    for case in LIBRARY:
        if case.expected_outputs or case.expect_refusal:
            continue
        notes = (case.source_document.notes or "").lower()
        assert (
            "reserve" in notes or "a identifier" in notes or "declare" in notes
        ), (
            f"{case.reference_id}: un cas sans valeurs attendues doit dire "
            "explicitement qu'il est en attente, pas citer une source."
        )


def test_planned_coverage_spans_the_priority_modules() -> None:
    """TICKET 2.3 scope: concrete, steel, composite, timber, geotechnics, seismic."""
    families = {c.harness.split(".")[0] for c in LIBRARY}
    assert {"ec2", "ec3", "ec4", "ec5", "ec7", "ec8"} <= families

    scopes = " ".join(s for c in LIBRARY for s in c.normative_scope)
    for standard in (
        "EN 1992-1-1", "EN 1993-1-1", "EN 1993-1-8", "EN 1994-1-1",
        "EN 1995-1-1", "EN 1997-1", "EN 1998-1",
    ):
        assert standard in scopes, f"{standard} absent de la couverture declaree"


def test_concrete_scope_covers_the_priority_verifications() -> None:
    scopes = " ".join(s for c in LIBRARY for s in c.normative_scope)
    for clause in ("§6.1", "§6.2.2", "§6.2.3", "§8.4", "§9.2.1.1(1)"):
        assert clause in scopes, f"{clause} absent de la couverture beton arme"


def test_registered_harness_matches_the_implemented_modules() -> None:
    assert "ec2.beam_flexure" in available_harnesses()
    # Modules not yet written must not be registered, or the gap would hide.
    assert "ec2.beam_shear" not in available_harnesses()


def test_report_serialises_for_ci() -> None:
    data = run_library().to_dict()
    assert data["ok"] is True
    assert data["total"] == len(LIBRARY)
    assert set(data["by_status"]) <= {
        "passed", "failed", "refused", "awaiting_source", "awaiting_module", "not_run"
    }
    assert data["gaps"]
    json.dumps(data)  # must be serialisable as-is


def test_library_files_are_where_the_runner_looks() -> None:
    assert LIBRARY_DIR.is_dir()
    assert list(LIBRARY_DIR.glob("*.json"))
