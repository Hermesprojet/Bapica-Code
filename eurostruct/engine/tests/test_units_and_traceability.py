"""Unit typing and the traceability journal.

Cahier des charges section 8.2: "Aucune tolerance sur les unites : le typage
Pint interdit d'additionner des kN et des kN.m."
And section 8.1: every number must be traceable to its clause and its inputs.
"""

from __future__ import annotations

import json

import pytest

from eurostruct_engine.ec2 import RectangularSection, design_flexure
from eurostruct_engine.exceptions import UnitError
from eurostruct_engine.materials import concrete, reinforcement
from eurostruct_engine.traceability import EC2, Journal, Provenance, ProvenanceKind
from eurostruct_engine.units import Q_, fmt, magnitude, require_dimension


# ---------------------------------------------------------------------------
# Units
# ---------------------------------------------------------------------------
def test_adding_incompatible_dimensions_raises() -> None:
    """A force and a moment cannot be added."""
    import pint

    with pytest.raises(pint.DimensionalityError):
        _ = Q_(10, "kN") + Q_(5, "kN*m")


def test_bare_number_refused_where_a_dimension_is_expected() -> None:
    with pytest.raises(UnitError, match="nombre nu"):
        require_dimension(25.0, "[length]", "d")


def test_wrong_dimension_refused() -> None:
    with pytest.raises(UnitError):
        require_dimension(Q_(25, "kN"), "[length]", "d")


def test_dimensionless_accepts_a_plain_float() -> None:
    q = require_dimension(0.85, "", "alpha")
    assert q.magnitude == 0.85


def test_unit_conversion_is_exact_for_the_units_in_use() -> None:
    assert magnitude(Q_(1, "m"), "mm") == 1000.0
    assert magnitude(Q_(1, "kN*m"), "N*mm") == 1e6
    assert magnitude(Q_(1, "MPa"), "N/mm**2") == pytest.approx(1.0, rel=1e-15)


def test_input_unit_does_not_change_the_result(params_be) -> None:
    """Dimensional homogeneity: the same moment in different units, same answer."""
    common = dict(
        section=RectangularSection(b=Q_(0.3, "m"), h=Q_(0.6, "m"), d=Q_(550, "mm")),
        concrete=concrete("C30/37"),
        steel=reinforcement("B500B"),
        params=params_be,
    )
    a = design_flexure(**common, M_Ed=Q_(250, "kN*m"))
    b = design_flexure(**common, M_Ed=Q_(250e6, "N*mm"))
    assert a.As_strength.to("mm**2").magnitude == pytest.approx(
        b.As_strength.to("mm**2").magnitude, rel=1e-12
    )


def test_fmt_is_stable_and_locale_independent() -> None:
    assert fmt(Q_(25.0, "MPa")) == "25 MPa"
    assert fmt(Q_(1234.5678, "mm**2"), "mm**2", digits=1) == "1234.6 mm²"
    assert fmt(0.44) == "0.44"


# ---------------------------------------------------------------------------
# Journal
# ---------------------------------------------------------------------------
def test_duplicate_symbol_is_refused() -> None:
    j = Journal("t")
    j.input("x", "d", Q_(1, "mm"), Provenance.user("saisie"))
    with pytest.raises(KeyError, match="deja utilise"):
        j.input("x", "d", Q_(2, "mm"), Provenance.user("saisie"))


def test_dependency_must_exist_before_it_is_referenced() -> None:
    """A broken trace graph is a bug, not something to tolerate silently."""
    j = Journal("t")
    with pytest.raises(KeyError, match="n'a pas ete enregistre"):
        j.step(
            "y", "derived", Q_(1, "mm"), EC2("§6.1"),
            latex="y = x", numeric="1", depends_on=("x",),
        )


def test_every_calculated_number_carries_a_clause(params_be) -> None:
    """No derived step may exist without a normative citation."""
    r = design_flexure(
        section=RectangularSection(b=Q_(300, "mm"), h=Q_(600, "mm"), d=Q_(550, "mm")),
        concrete=concrete("C30/37"), steel=reinforcement("B500B"),
        M_Ed=Q_(250, "kN*m"), params=params_be,
    )
    for step in r.journal.steps:
        is_input = step.provenance is not None
        if not is_input:
            assert step.clause is not None, f"etape sans clause: {step.symbol}"
            assert step.latex, f"etape sans formule symbolique: {step.symbol}"
            assert step.numeric, f"etape sans application numerique: {step.symbol}"


def test_every_input_carries_a_provenance(params_be) -> None:
    r = design_flexure(
        section=RectangularSection(b=Q_(300, "mm"), h=Q_(600, "mm"), d=Q_(550, "mm")),
        concrete=concrete("C30/37"), steel=reinforcement("B500B"),
        M_Ed=Q_(250, "kN*m"), params=params_be,
    )
    inputs = [s for s in r.journal.steps if s.provenance is not None]
    assert {"b", "h", "d", "f_ck", "f_yk", "M_Ed"} <= {s.symbol for s in inputs}
    for s in inputs:
        assert s.provenance.detail


def test_national_annex_values_are_recorded_as_such(params_be) -> None:
    """Every NDP consumed must appear in the journal, tagged NATIONAL_ANNEX."""
    r = design_flexure(
        section=RectangularSection(b=Q_(300, "mm"), h=Q_(600, "mm"), d=Q_(550, "mm")),
        concrete=concrete("C30/37"), steel=reinforcement("B500B"),
        M_Ed=Q_(250, "kN*m"), params=params_be,
    )
    ndp_steps = [
        s for s in r.journal.steps
        if s.provenance and s.provenance.kind is ProvenanceKind.NATIONAL_ANNEX
    ]
    keys = {s.symbol for s in ndp_steps}
    assert {
        "EC2.gamma_C.persistent", "EC2.gamma_S.persistent", "EC2.alpha_cc",
        "EC2.k1_redistribution", "EC2.k2_redistribution",
    } <= keys
    for s in ndp_steps:
        assert s.provenance.ndp_key == s.symbol
        assert s.clause is not None and s.clause.national_note


def test_trace_graph_is_closed_and_acyclic(params_be) -> None:
    """Following depends_on from any number must terminate at declared inputs."""
    r = design_flexure(
        section=RectangularSection(b=Q_(300, "mm"), h=Q_(600, "mm"), d=Q_(550, "mm")),
        concrete=concrete("C30/37"), steel=reinforcement("B500B"),
        M_Ed=Q_(250, "kN*m"), params=params_be,
    )
    seen: set[str] = set()
    for step in r.journal.steps:          # journal order is topological by construction
        for dep in step.depends_on:
            assert dep in seen, f"{step.symbol} depend de {dep}, non encore defini"
        seen.add(step.symbol)

    # And the key result is reachable back to the inputs.
    def ancestors(sym: str) -> set[str]:
        out: set[str] = set()
        stack = [sym]
        while stack:
            cur = stack.pop()
            for d in r.journal.get(cur).depends_on:
                if d not in out:
                    out.add(d)
                    stack.append(d)
        return out

    anc = ancestors("A_s_req")
    assert {"M_Ed", "f_ck", "f_yk", "b", "d"} <= anc


def test_journal_serializes_deterministically(params_be) -> None:
    r = design_flexure(
        section=RectangularSection(b=Q_(300, "mm"), h=Q_(600, "mm"), d=Q_(550, "mm")),
        concrete=concrete("C30/37"), steel=reinforcement("B500B"),
        M_Ed=Q_(250, "kN*m"), params=params_be,
    )
    a, b = r.journal.to_json(), r.journal.to_json()
    assert a == b
    parsed = json.loads(a)
    assert parsed["steps"][0]["symbol"] == "b"
    assert any("EN 1992-1-1" in c for c in parsed["clauses"])
