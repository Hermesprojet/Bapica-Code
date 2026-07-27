"""EN 1992-1-1 §7.4.2 — span/depth exemption from the deflection calculation.

The property this file exists to defend above the arithmetic: **a failed
exemption is not a failed beam**. §7.4.2 says when the deflection need not be
computed; it never says a member deflects too much. A module that reported the
two the same way would tell an engineer their beam is inadequate on the
strength of a criterion that establishes nothing of the sort, and
:func:`test_a_failed_exemption_does_not_claim_the_beam_is_inadequate` is the
guard on that.

The second property is the National Annex reaching the result: K runs from 0,4
for a cantilever to 1,5 for an interior span. Between those two the limit moves
by a factor of nearly four, and nothing in the section geometry says which one
applies.
"""

from __future__ import annotations

import math

import pytest

from eurostruct_engine.ec2 import (
    RectangularSection,
    StructuralSystem,
    check_span_depth,
)
from eurostruct_engine.exceptions import (
    ConditionalParameterNeedsContext,
    InconsistentInput,
    OutOfValidationDomain,
)
from eurostruct_engine.materials import concrete, reinforcement
from eurostruct_engine.materials.reinforcement import bars_area
from eurostruct_engine.units import Q_

SECTION = RectangularSection(b=Q_(300, "mm"), h=Q_(600, "mm"), d=Q_(550, "mm"))


def _check(params, **kw):
    base = dict(
        section=SECTION,
        concrete=concrete("C30/37"),
        steel=reinforcement("B500B"),
        l_eff=Q_(6000, "mm"),
        system=StructuralSystem.SIMPLY_SUPPORTED,
        A_s_required=bars_area(4, 20),
        A_s_provided=bars_area(4, 20),
        params=params,
        element="P1",
    )
    base.update(kw)
    return check_span_depth(**base)


# ---------------------------------------------------------------------------
# Hand calculation of (7.16a) and (7.16b)
# ---------------------------------------------------------------------------
@pytest.mark.reference
def test_hand_calculation_of_the_heavily_reinforced_branch(params_be) -> None:
    """300 × 550 utile, 4 HA20, C30/37, isostatique (K = 1,0).

        rho_0 = 1e-3 sqrt(30)                       = 0,005477226
        rho   = 1256,637061 / (300 x 550)           = 0,007615982
        rho > rho_0  ->  formule (7.16b), rho' = 0

        l/d = 1,0 [11 + 1,5 sqrt(30) x 0,005477226/0,007615982 + 0]
            = 11 + 8,215838 x 0,719174              = 16,908627262
    """
    c = _check(params_be)
    assert c.heavily_reinforced
    assert c.rho_0 == pytest.approx(0.005477226, abs=5e-10)
    assert c.rho == pytest.approx(0.007615982, abs=5e-10)
    assert c.basic_ratio == pytest.approx(16.908627262, abs=5e-9)


@pytest.mark.reference
def test_hand_calculation_of_the_lightly_reinforced_branch(params_be) -> None:
    """Same section with 4 HA16, which brings rho below rho_0.

        rho   = 804,247719 / 165 000                = 0,004874229
        rho_0/rho                                   = 1,123711
        l/d = 1,0 [11 + 1,5 sqrt(30) x 1,123711
                      + 3,2 sqrt(30) (0,123711)^1,5]
            = 11 + 9,232152 + 0,762727              = 20,994878672
    """
    c = _check(params_be, A_s_required=bars_area(4, 16), A_s_provided=bars_area(4, 16))
    assert not c.heavily_reinforced
    assert c.rho == pytest.approx(0.004874229, abs=5e-10)
    assert c.basic_ratio == pytest.approx(20.994878672, abs=5e-9)


@pytest.mark.reference
def test_compression_reinforcement_raises_the_limit(params_be) -> None:
    """(7.16b) with rho': 2 HA12 in compression.

        rho'  = 226,194671 / 165 000                = 0,001370877
        l/d = 1,0 [11 + 1,5 sqrt(30) x rho_0/(rho − rho')
                      + sqrt(30) sqrt(rho'/rho_0)/12]        = 18,433991564
    """
    c = _check(params_be, A_s_comp=bars_area(2, 12))
    assert c.rho_comp == pytest.approx(0.001370877, abs=5e-10)
    assert c.basic_ratio == pytest.approx(18.433991564, abs=5e-9)
    # Et c'est bien une amelioration par rapport a la meme poutre sans.
    assert c.basic_ratio > _check(params_be).basic_ratio


def test_the_actual_ratio_is_the_span_over_the_effective_depth(params_be) -> None:
    c = _check(params_be)
    assert c.actual_ratio == pytest.approx(6000.0 / 550.0, rel=1e-12)


# ---------------------------------------------------------------------------
# The National Annex must change the answer
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "system, K",
    [
        (StructuralSystem.SIMPLY_SUPPORTED, 1.0),
        (StructuralSystem.END_SPAN_CONTINUOUS, 1.3),
        (StructuralSystem.INTERIOR_SPAN_CONTINUOUS, 1.5),
        (StructuralSystem.FLAT_SLAB, 1.2),
        (StructuralSystem.CANTILEVER, 0.4),
    ],
)
def test_K_follows_the_row_of_table_7_4N(params_be, system, K) -> None:
    c = _check(params_be, system=system)
    assert c.K == pytest.approx(K)
    assert c.basic_ratio == pytest.approx(16.908627262 * K, abs=5e-9)


def test_a_cantilever_and_an_interior_span_differ_by_a_factor_of_nearly_four(
    params_be,
) -> None:
    """Which is why K is asked for by case and never as a single scalar."""
    cantilever = _check(params_be, system=StructuralSystem.CANTILEVER)
    interior = _check(params_be, system=StructuralSystem.INTERIOR_SPAN_CONTINUOUS)
    assert interior.limit_ratio / cantilever.limit_ratio == pytest.approx(1.5 / 0.4)
    # Le meme element: dispense d'un cote, pas de l'autre.
    assert interior.exempt
    assert not cantilever.exempt


def test_the_system_reaches_the_journal_as_a_declared_case(params_be) -> None:
    c = _check(params_be, system=StructuralSystem.CANTILEVER)
    assert "cantilever" in c.journal.to_json()
    assert "console" in c.journal.title


def test_an_undeclared_system_is_refused(params_be) -> None:
    with pytest.raises(ConditionalParameterNeedsContext, match="poutre_speciale"):
        params_be.get("EN 1992-1-1:K_span_depth", condition="poutre_speciale")


# ---------------------------------------------------------------------------
# The §7.4.2(2) modifying factors
# ---------------------------------------------------------------------------
def test_overprovided_steel_raises_the_limit(params_be) -> None:
    """500/(f_yk A_req/A_prov): more steel than required means lower stress."""
    exact = _check(params_be)
    generous = _check(params_be, A_s_required=bars_area(4, 20) * 0.8)
    assert exact.stress_factor == pytest.approx(1.0)
    assert generous.stress_factor == pytest.approx(1.25)
    assert generous.limit_ratio > exact.limit_ratio


def test_the_stress_factor_is_capped_at_one_and_a_half(params_be) -> None:
    """§7.4.2(2). Without the cap, a grossly overprovided section would earn an
    unbounded exemption."""
    c = _check(params_be, A_s_required=bars_area(4, 20) * 0.1)
    assert c.stress_factor == pytest.approx(1.5)


def test_a_flanged_section_takes_the_zero_point_eight_factor(params_be) -> None:
    rect = _check(params_be)
    flanged = _check(params_be, b_eff_over_b_w=4.0)
    assert flanged.flange_factor == pytest.approx(0.8)
    assert flanged.limit_ratio == pytest.approx(0.8 * rect.limit_ratio)


def test_a_flange_ratio_of_three_or_less_does_not(params_be) -> None:
    """§7.4.2(2) says *greater than* 3, and the boundary belongs to 1,0."""
    assert _check(params_be, b_eff_over_b_w=3.0).flange_factor == pytest.approx(1.0)


def test_a_rectangular_section_is_declared_not_assumed(params_be) -> None:
    c = _check(params_be)
    assert c.flange_factor == pytest.approx(1.0)
    assert "rectangulaire declaree" in c.journal.get("facteur_table").numeric


def test_a_long_span_with_brittle_partitions_is_penalised(params_be) -> None:
    """§7.4.2(2): 7/l_eff beyond 7 m for a beam."""
    c = _check(
        params_be, l_eff=Q_(10000, "mm"), supports_brittle_partitions=True
    )
    assert c.long_span_factor == pytest.approx(7.0 / 10.0)


def test_a_flat_slab_uses_the_eight_and_a_half_metre_threshold(params_be) -> None:
    """The same clause gives flat slabs a different threshold."""
    slab = _check(
        params_be, l_eff=Q_(10000, "mm"), system=StructuralSystem.FLAT_SLAB,
        supports_brittle_partitions=True,
    )
    assert slab.long_span_factor == pytest.approx(8.5 / 10.0)
    # Et en dessous du seuil, aucune penalite.
    short = _check(
        params_be, l_eff=Q_(8000, "mm"), system=StructuralSystem.FLAT_SLAB,
        supports_brittle_partitions=True,
    )
    assert short.long_span_factor == pytest.approx(1.0)


def test_a_long_span_without_brittle_partitions_is_not_penalised(params_be) -> None:
    """The penalty is about what the member carries, not its length alone."""
    c = _check(params_be, l_eff=Q_(10000, "mm"))
    assert c.long_span_factor == pytest.approx(1.0)
    assert "NON declarees" in c.journal.get("facteur_portee").numeric


# ---------------------------------------------------------------------------
# What the outcome means
# ---------------------------------------------------------------------------
def test_a_passing_check_says_the_deflection_was_never_computed(params_be) -> None:
    c = _check(params_be)
    assert c.exempt
    assert "N'EST PAS REQUIS" in c.verdict
    assert "n'avait pas a l'etre" in c.verdict


def test_a_failed_exemption_does_not_claim_the_beam_is_inadequate(params_be) -> None:
    """The property this file exists for.

    §7.4.2 establishes when a deflection calculation may be skipped. It never
    establishes that a member deflects too much, and the wording must not let
    anyone read it that way.
    """
    c = _check(params_be, l_eff=Q_(14000, "mm"))
    assert not c.exempt
    assert "N'ETABLIT PAS" in c.verdict.upper()
    assert "§7.4.3" in c.verdict
    check = c.report.checks[0]
    assert "PAS une insuffisance demontree" in check.detail
    assert "§7.4.3" in check.remedy


def test_the_module_does_not_pretend_to_compute_a_deflection(params_be) -> None:
    """No output of this module is a deflection, and none is named like one."""
    data = _check(params_be).to_dict()
    for key in data:
        assert "fleche" not in key.lower()
        assert "deflection" not in key.lower()


# ---------------------------------------------------------------------------
# What the module refuses
# ---------------------------------------------------------------------------
def test_less_steel_than_the_ULS_requires_is_refused(params_be) -> None:
    with pytest.raises(InconsistentInput, match="ne couvre pas l'ELU"):
        _check(params_be, A_s_provided=bars_area(2, 16))


def test_more_compression_steel_than_tension_steel_is_refused(params_be) -> None:
    """(7.16b) divides by (rho − rho')."""
    with pytest.raises(InconsistentInput, match=r"7\.16b"):
        _check(params_be, A_s_comp=bars_area(6, 20))


def test_high_strength_concrete_is_outside_the_domain(params_be) -> None:
    with pytest.raises(OutOfValidationDomain, match="C50/60"):
        _check(params_be, concrete=concrete("C55/67"))


def test_a_non_positive_span_is_refused(params_be) -> None:
    with pytest.raises(InconsistentInput, match="portee"):
        _check(params_be, l_eff=Q_(0, "mm"))


def test_a_flange_ratio_below_one_is_refused(params_be) -> None:
    with pytest.raises(InconsistentInput, match="b_eff"):
        _check(params_be, b_eff_over_b_w=0.5)


# ---------------------------------------------------------------------------
# Traceability
# ---------------------------------------------------------------------------
def test_the_national_parameter_is_recorded(params_be) -> None:
    assert "K_span_depth" in _check(params_be).journal.to_json()


def test_the_clauses_actually_applied_are_cited(params_be) -> None:
    clauses = " ".join(_check(params_be).journal.clauses())
    for clause in ("§7.4.2(1)", "§7.4.2(2)", "§5.3.2.2"):
        assert clause in clauses, f"{clause} non cite"


def test_generation_is_deterministic(params_be) -> None:
    assert _check(params_be).to_dict() == _check(params_be).to_dict()


def test_the_check_serialises_whole(params_be) -> None:
    import json

    data = _check(params_be).to_dict()
    assert json.dumps(data, sort_keys=True)
    assert data["system"] == "simply_supported"
    assert data["exempt"] is True
    assert not math.isnan(data["limit_ratio"])
