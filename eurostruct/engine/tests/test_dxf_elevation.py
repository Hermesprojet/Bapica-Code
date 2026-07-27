"""Beam elevation and the complete rebar schedule.

Two properties matter here and neither is about drawing:

* **The schedule and the drawing describe the same steel.** A length printed
  beside a bar that differs from the one ordered is how a beam gets built
  wrong, and it is a mistake nobody catches on site.
* **The module refuses to decide what it cannot know.** Curtailment comes from
  a moment envelope; link zoning is an arbitration between steel and labour.
  Both are supplied, and a supplied value that breaks a normative limit is
  refused rather than quietly clamped.
"""

from __future__ import annotations

import math

import pytest

from eurostruct_engine.drawing import (
    BarRow,
    BeamElevationSpec,
    LinkZone,
    LongitudinalBar,
    build_beam_elevation,
)
from eurostruct_engine.exceptions import InconsistentInput
from eurostruct_engine.legal import DRAFT_WATERMARK, Language

SPAN, H, B = 6000.0, 600.0, 300.0


def _spec(**kw) -> BeamElevationSpec:
    base = dict(
        span=SPAN, h=H, cover=30.0, link_diameter=10.0,
        bars=(
            LongitudinalBar(BarRow(4, 20.0, "A1"), "bottom",
                            anchorage_each_end=715.0, hook_each_end=True),
            LongitudinalBar(BarRow(2, 12.0, "A2"), "top", anchorage_each_end=430.0),
        ),
        link_zones=(LinkZone(0, 1500, 150), LinkZone(1500, 4500, 250),
                    LinkZone(4500, 6000, 150)),
        s_l_max=412.5,
    )
    base.update(kw)
    return BeamElevationSpec(**base)


def _schedule(**kw):
    spec = _spec(**kw)
    _, rows = build_beam_elevation(spec, width=B)
    return spec, {r.mark: r for r in rows}


# ---------------------------------------------------------------------------
# Developed lengths — hand calculation
# ---------------------------------------------------------------------------
@pytest.mark.reference
def test_hand_calculation_of_developed_lengths() -> None:
    """4 HA20 with 715 mm anchorage and 90° hooks at both ends.

        droit    = 6000 + 2 × 715                     = 7430 mm
        phi = 20 > 16  ->  mandrin 7 phi              = 140 mm  (Tab. 8.1N)
        rayon    = 140/2 + 20/2                       = 80 mm   (fibre moyenne)
        crochet  = pi × 80 / 2 + 5 × 20               = 225,66 mm
        total    = 7430 + 2 × 225,66                  = 7881,33 mm

    The 2 HA12 top bars are straight: 6000 + 2 × 430 = 6860 mm.
    """
    _, rows = _schedule()
    assert rows["A1"].unit_length_mm == pytest.approx(7881.33, abs=5e-3)
    assert rows["A2"].unit_length_mm == pytest.approx(6860.0, abs=1e-9)


@pytest.mark.reference
def test_hand_calculation_of_the_link_perimeter() -> None:
    """HA10 closed link in a 300 × 600 beam, 30 mm cover.

        offset   = 30 + 10/2                          = 35 mm
        w        = 300 − 70                           = 230 mm
        d        = 600 − 70                           = 530 mm
        vif      = 2 (230 + 530)                      = 1520 mm
        phi = 10 <= 16  ->  mandrin 4 phi = 40, r = 25 mm
        cintrages= 4 × 25 × (2 − pi/2)                = 42,92 mm  (a RETRANCHER)
        crochets = 2 (pi × 25/2 + 10 × 10)            = 278,54 mm
        total    = 1520 − 42,92 + 278,54              = 1755,62 mm
    """
    _, rows = _schedule()
    assert rows["C1"].unit_length_mm == pytest.approx(1755.62, abs=5e-3)


def test_a_larger_bar_gets_a_larger_mandrel() -> None:
    """Tab. 8.1N steps at 16 mm; the hook allowance must step with it."""
    small = LongitudinalBar(BarRow(1, 16.0, "X"), hook_each_end=True)
    large = LongitudinalBar(BarRow(1, 20.0, "Y"), hook_each_end=True)
    # Par millimetre de diametre, le crochet coute plus cher au-dela de 16 mm.
    per_mm_small = (small.developed_length(1000.0) - 1000.0) / 16.0
    per_mm_large = (large.developed_length(1000.0) - 1000.0) / 20.0
    assert per_mm_large > per_mm_small


# ---------------------------------------------------------------------------
# The schedule and the drawing must agree
# ---------------------------------------------------------------------------
def test_the_schedule_covers_every_bar_and_the_links() -> None:
    spec, rows = _schedule()
    assert set(rows) == {"A1", "A2", "C1"}
    assert rows["A1"].count == 4
    assert rows["C1"].count == spec.total_links()


def test_total_length_is_the_unit_length_times_the_count() -> None:
    _, rows = _schedule()
    for r in rows.values():
        assert r.total_length_mm == pytest.approx(r.unit_length_mm * r.count)


def test_the_printed_length_matches_the_schedule() -> None:
    """A label beside a bar that disagrees with the order is how it goes wrong."""
    spec = _spec()
    doc, rows = build_beam_elevation(spec, width=B)
    texts = [e.dxf.text for e in doc.modelspace() if e.dxftype() == "TEXT"]
    printed = " ".join(texts)
    for mark in ("A1", "A2"):
        assert f"L={rows_by_mark(rows)[mark].unit_length_mm:.0f}" in printed


def rows_by_mark(rows):
    return {r.mark: r for r in rows}


def test_mass_follows_from_diameter_and_length() -> None:
    """7850 kg/m³ on the nominal section — no bar-list catalogue involved."""
    _, rows = _schedule()
    r = rows["A1"]
    area_mm2 = math.pi * r.diameter**2 / 4.0
    expected = area_mm2 * r.total_length_mm * 7850e-9
    assert r.mass_kg == pytest.approx(expected, rel=1e-9)


# ---------------------------------------------------------------------------
# Link counting
# ---------------------------------------------------------------------------
def test_a_zone_rounds_its_link_count_up() -> None:
    """1 000 mm at 150 mm takes 8 links, not 7,67.

    Rounding down would leave a gap wider than the spacing the shear
    calculation assumed.
    """
    assert LinkZone(0, 1000, 150).link_count() == 8


def test_junction_links_are_counted_once() -> None:
    """Three zones share two boundary links; ordering them twice is waste."""
    spec = _spec()
    naive = sum(z.link_count() for z in spec.link_zones)
    assert spec.total_links() == naive - 2
    assert spec.total_links() == 33


# ---------------------------------------------------------------------------
# What the module refuses
# ---------------------------------------------------------------------------
def test_a_gap_between_link_zones_is_refused() -> None:
    with pytest.raises(InconsistentInput, match="discontinuite"):
        _spec(link_zones=(LinkZone(0, 1500, 150), LinkZone(2000, 6000, 250)))


def test_zones_that_do_not_reach_the_end_are_refused() -> None:
    with pytest.raises(InconsistentInput, match="s'arretent"):
        _spec(link_zones=(LinkZone(0, 4000, 150),))


def test_zones_that_do_not_start_at_the_origin_are_refused() -> None:
    with pytest.raises(InconsistentInput, match="resterait sans cadres"):
        _spec(link_zones=(LinkZone(200, 6000, 150),))


def test_a_spacing_above_the_normative_maximum_is_refused() -> None:
    """§9.2.2(6): supplied is not the same as permitted."""
    with pytest.raises(InconsistentInput, match="§9.2.2\\(6\\)"):
        _spec(link_zones=(LinkZone(0, 6000, 500),), s_l_max=412.5)


def test_an_unchecked_maximum_is_announced_on_the_sheet() -> None:
    """Skipping the check is allowed; hiding that it was skipped is not."""
    spec = _spec(s_l_max=None, link_zones=(LinkZone(0, 6000, 500),))
    doc, _ = build_beam_elevation(spec, width=B)
    texts = " ".join(e.dxf.text for e in doc.modelspace() if e.dxftype() == "TEXT")
    assert "NON VERIFIE" in texts


def test_an_elevation_without_bars_is_refused() -> None:
    with pytest.raises(InconsistentInput, match="ne represente"):
        _spec(bars=())


def test_a_bar_ending_before_it_starts_is_refused() -> None:
    bar = LongitudinalBar(BarRow(2, 16.0, "A3"), start=4000.0, end=1000.0)
    with pytest.raises(InconsistentInput, match="se termine"):
        bar.extent(SPAN)


def test_an_unknown_position_is_refused() -> None:
    with pytest.raises(InconsistentInput, match="position"):
        LongitudinalBar(BarRow(2, 16.0, "A3"), position="milieu")


# ---------------------------------------------------------------------------
# Curtailment is declared, never guessed
# ---------------------------------------------------------------------------
def test_a_bar_without_declared_extent_runs_the_full_span() -> None:
    """The conservative choice, and one the reader can see."""
    bar = LongitudinalBar(BarRow(2, 16.0, "A3"))
    assert bar.extent(SPAN) == (0.0, SPAN)


def test_a_declared_curtailment_is_carried_into_the_schedule() -> None:
    curtailed = LongitudinalBar(
        BarRow(2, 16.0, "A3"), "top", start=0.0, end=1800.0, anchorage_each_end=500.0
    )
    _, rows = _schedule(bars=(curtailed,))
    assert rows["A3"].unit_length_mm == pytest.approx(1800.0 + 2 * 500.0)
    assert "arret declare" in rows["A3"].comment


# ---------------------------------------------------------------------------
# The sheet says what it is
# ---------------------------------------------------------------------------
def test_an_unvalidated_sheet_carries_the_draft_watermark() -> None:
    """§9: a sheet nobody signed must not look like one somebody did.

    Compared against the constant rather than a guessed wording — a test that
    invents the label passes while the sheet says something else.
    """
    doc, _ = build_beam_elevation(_spec(validated=False), width=B)
    texts = " ".join(e.dxf.text for e in doc.modelspace() if e.dxftype() == "TEXT")
    assert DRAFT_WATERMARK[Language.FR] in texts


def test_a_validated_sheet_does_not() -> None:
    doc, _ = build_beam_elevation(_spec(validated=True), width=B)
    texts = " ".join(e.dxf.text for e in doc.modelspace() if e.dxftype() == "TEXT")
    assert DRAFT_WATERMARK[Language.FR] not in texts


def test_the_link_comment_states_how_the_count_was_reached() -> None:
    """A quantity nobody can re-derive is a quantity nobody can check."""
    _, rows = _schedule()
    comment = rows["C1"].comment
    assert "Tab. 8.1N" in comment
    assert "§8.5" in comment
    assert "total 33" in comment
    for zone in ("0–1500", "1500–4500", "4500–6000"):
        assert zone in comment


def test_generation_is_deterministic() -> None:
    a, rows_a = build_beam_elevation(_spec(), width=B)
    b, rows_b = build_beam_elevation(_spec(), width=B)
    assert [r.to_dict() for r in rows_a] == [r.to_dict() for r in rows_b]
    assert len(list(a.modelspace())) == len(list(b.modelspace()))
