"""DXF generation — cahier des charges sections 7.2 and 11.

    "Un DXF genere s'ouvre sans erreur dans AutoCAD, BricsCAD et LibreCAD, avec
     les calques et cotations corrects."

Opening in those three applications is a manual acceptance step that cannot run
in CI. What CI *can* enforce, and does here, is everything that would make them
fail: a valid R2018 file that survives a save/reload round trip, passes
``ezdxf``'s auditor with zero errors, carries the normalised layers, keeps the
geometry at true scale, and references only text styles present in the file.
"""

from __future__ import annotations

import math

import ezdxf
import pytest
from ezdxf.document import Drawing

from eurostruct_engine.drawing import BarRow, BeamSectionSpec, build_beam_section
from eurostruct_engine.drawing.beam_section import LEGAL_NOTICE
from eurostruct_engine.drawing.layers import LAYERS
from eurostruct_engine.exceptions import InconsistentInput
from eurostruct_engine.version import ENGINE_VERSION

B, H, COVER, LINK = 300.0, 600.0, 30.0, 8.0


@pytest.fixture
def spec() -> BeamSectionSpec:
    return BeamSectionSpec(
        b=B, h=H, cover=COVER, link_diameter=LINK,
        bottom=(BarRow(count=4, diameter=20, mark="A1", length=6200),),
        top=(BarRow(count=2, diameter=12, mark="A2", length=6200),),
        link_spacing=200, plot_scale=20,
        title="COUPE", element="P1", project="EUROSTRUCT — cas de reference",
        concrete_grade="C30/37", steel_grade="B500B", exposure_class="XC1",
        date="2026-07-26",
    )


@pytest.fixture
def built(spec, tmp_path):
    """Build, save and reload — the round trip is the interop check."""
    doc, schedule = build_beam_section(spec)
    path = tmp_path / "section.dxf"
    doc.saveas(path)
    return ezdxf.readfile(path), schedule, path


def test_file_is_r2018_and_metric(built) -> None:
    doc, _, _ = built
    assert doc.dxfversion == "AC1032"          # R2018
    assert doc.header["$INSUNITS"] == 4        # millimetres
    assert doc.header["$MEASUREMENT"] == 1     # metric


def test_auditor_reports_no_error(built) -> None:
    doc, _, _ = built
    auditor = doc.audit()
    assert not auditor.errors, [str(e) for e in auditor.errors]


def test_normalised_layers_are_present(built) -> None:
    doc, _, _ = built
    names = {layer.dxf.name for layer in doc.layers}
    assert {s.name for s in LAYERS} <= names
    for s in LAYERS:
        layer = doc.layers.get(s.name)
        assert layer.dxf.color == s.color
        assert layer.dxf.lineweight == s.lineweight


def test_entities_are_on_the_expected_layers(built) -> None:
    doc, _, _ = built
    msp = doc.modelspace()
    by_layer: dict[str, set[str]] = {}
    for e in msp:
        by_layer.setdefault(e.dxf.layer, set()).add(e.dxftype())
    assert "LWPOLYLINE" in by_layer["COFFRAGE"]
    assert by_layer["FERR-PRINCIPAL"] >= {"CIRCLE", "HATCH"}
    assert "LWPOLYLINE" in by_layer["FERR-TRANSVERSAL"]
    assert "TEXT" in by_layer["TEXTE"]
    assert "LWPOLYLINE" in by_layer["CARTOUCHE"]


def test_concrete_outline_is_true_scale(built) -> None:
    """Geometry is in millimetres at 1:1 — section 7.2, 'echelle vraie'."""
    doc, _, _ = built
    outline = next(
        e for e in doc.modelspace()
        if e.dxftype() == "LWPOLYLINE" and e.dxf.layer == "COFFRAGE"
    )
    pts = [(p[0], p[1]) for p in outline.get_points()]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    assert max(xs) - min(xs) == pytest.approx(B)
    assert max(ys) - min(ys) == pytest.approx(H)


def test_bars_are_correctly_placed_and_covered(built) -> None:
    """Every bar sits inside the links, with the nominal cover respected."""
    doc, _, _ = built
    bars = [e for e in doc.modelspace() if e.dxftype() == "CIRCLE"]
    assert len(bars) == 6  # 4 bottom + 2 top

    bottom = sorted(
        (b for b in bars if b.dxf.center.y < H / 2), key=lambda c: c.dxf.center.x
    )
    top = sorted(
        (b for b in bars if b.dxf.center.y > H / 2), key=lambda c: c.dxf.center.x
    )
    assert len(bottom) == 4
    assert len(top) == 2

    for bar in bars:
        r = bar.dxf.radius
        c = bar.dxf.center
        clear = COVER + LINK          # cover plus the link the bar sits inside
        assert c.x - r >= clear - 1e-9
        assert B - (c.x + r) >= clear - 1e-9
        assert min(c.y - r, H - (c.y + r)) >= clear - 1e-9

    # Bottom bars: radius 10, centre at 30 + 8 + 10 = 48 mm above the soffit.
    assert all(b.dxf.radius == pytest.approx(10.0) for b in bottom)
    assert all(b.dxf.center.y == pytest.approx(48.0) for b in bottom)
    # Evenly distributed between the inside faces of the links.
    spacings = [
        bottom[i + 1].dxf.center.x - bottom[i].dxf.center.x for i in range(3)
    ]
    assert spacings == pytest.approx([spacings[0]] * 3)
    assert bottom[0].dxf.center.x == pytest.approx(48.0)
    assert bottom[-1].dxf.center.x == pytest.approx(B - 48.0)

    # Top bars: radius 6, centre at 600 - (30 + 8 + 6) = 556 mm.
    assert all(b.dxf.radius == pytest.approx(6.0) for b in top)
    assert all(b.dxf.center.y == pytest.approx(556.0) for b in top)


def test_link_follows_the_cover_line(built) -> None:
    doc, _, _ = built
    link = next(
        e for e in doc.modelspace()
        if e.dxftype() == "LWPOLYLINE" and e.dxf.layer == "FERR-TRANSVERSAL"
    )
    pts = [(p[0], p[1]) for p in link.get_points()]
    off = COVER + LINK / 2.0  # centreline of the link
    assert min(p[0] for p in pts) == pytest.approx(off)
    assert max(p[0] for p in pts) == pytest.approx(B - off)
    assert min(p[1] for p in pts) == pytest.approx(off)
    assert max(p[1] for p in pts) == pytest.approx(H - off)
    assert link.closed


def test_both_dimensions_are_present(built) -> None:
    doc, _, _ = built
    dims = [e for e in doc.modelspace() if e.dxftype() == "DIMENSION"]
    assert len(dims) == 2
    assert all(d.dxf.layer == "COTATION" for d in dims)


def test_dimension_style_uses_a_font_present_in_the_file(built) -> None:
    """A missing text style is what makes a DXF render wrongly elsewhere."""
    doc, _, _ = built
    ds = doc.dimstyles.get("EUROSTRUCT")
    assert ds.dxf.dimtxsty in {s.dxf.name for s in doc.styles}
    assert ds.dxf.dimscale == 20.0


def test_mandatory_legal_notice_is_on_the_drawing(built) -> None:
    """Section 9: the notice appears on every deliverable."""
    doc, _, _ = built
    texts = " ".join(
        e.dxf.text for e in doc.modelspace() if e.dxftype() == "TEXT"
    )
    for fragment in (
        "Document genere par assistance logicielle",
        "verifie",
        "signe par un ingenieur habilite",
    ):
        assert fragment in texts
    # The wrapped lines must reconstruct the canonical notice.
    normalised = " ".join(texts.split())
    assert "complete et signe par un ingenieur habilite" in normalised
    assert LEGAL_NOTICE.split(".")[0] in normalised.replace(",", "")


def test_cartouche_records_the_engine_version(built) -> None:
    """Section 8.1: a drawing must say which engine produced it."""
    doc, _, _ = built
    texts = " ".join(
        e.dxf.text for e in doc.modelspace() if e.dxftype() == "TEXT"
    )
    assert f"eurostruct-engine {ENGINE_VERSION}" in texts
    assert "C30/37" in texts and "B500B" in texts and "XC1" in texts


# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------
def test_schedule_matches_the_drawn_bars(built) -> None:
    _, schedule, _ = built
    by_mark = {r.mark: r for r in schedule}
    assert set(by_mark) == {"A1", "A2", "C1"}
    assert by_mark["A1"].count == 4 and by_mark["A1"].diameter == 20
    assert by_mark["A2"].count == 2 and by_mark["A2"].diameter == 12


def test_schedule_masses(built) -> None:
    """Mass = area x length x 7850 kg/m3."""
    _, schedule, _ = built
    a1 = next(r for r in schedule if r.mark == "A1")
    expected = math.pi * 0.020**2 / 4 * 6.2 * 7850 * 4
    assert a1.mass_kg == pytest.approx(expected, rel=1e-12)
    assert a1.total_length_mm == pytest.approx(4 * 6200)


def test_link_length_matches_the_geometry_drawn(built) -> None:
    """The schedule and the drawing must describe the same bar.

    The link is drawn with bent corners, so its developed length is shorter
    than the sharp-corner perimeter.
    """
    doc, schedule, _ = built
    c1 = next(r for r in schedule if r.mark == "C1")
    off = COVER + LINK / 2.0
    sharp = 2.0 * ((B - 2 * off) + (H - 2 * off))
    r_c = 4.0 * LINK / 2.0 + LINK / 2.0
    expected = sharp - 4.0 * r_c * (2.0 - math.pi / 2.0)
    assert c1.unit_length_mm == pytest.approx(expected, rel=1e-12)
    assert c1.unit_length_mm < sharp
    # Anchorage hooks are explicitly excluded, and the schedule says so.
    assert "NON compris" in c1.comment


# ---------------------------------------------------------------------------
# Refusals
# ---------------------------------------------------------------------------
def test_bars_that_do_not_fit_are_refused() -> None:
    """Better a refusal than a drawing showing overlapping bars."""
    with pytest.raises(InconsistentInput, match="ne tient pas"):
        BeamSectionSpec(
            b=200, h=400, cover=30, link_diameter=8,
            bottom=(BarRow(count=6, diameter=25, mark="A1"),),
        )


def test_section_too_narrow_for_the_cover_is_refused() -> None:
    with pytest.raises(InconsistentInput, match="largeur insuffisante"):
        BeamSectionSpec(b=70, h=400, cover=30, link_diameter=8)


def test_empty_row_is_refused() -> None:
    with pytest.raises(InconsistentInput, match="au moins une barre"):
        BeamSectionSpec(
            b=300, h=600, cover=30, link_diameter=8,
            bottom=(BarRow(count=0, diameter=20, mark="A1"),),
        )


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------
def test_generation_is_geometrically_deterministic(spec) -> None:
    """Two builds place every entity identically.

    Byte equality is not the right assertion: a DXF carries handles and a
    timestamp. Geometry is what must be reproducible.
    """

    def geometry(doc: Drawing) -> list[tuple]:
        out = []
        for e in doc.modelspace():
            if e.dxftype() == "CIRCLE":
                out.append(("C", e.dxf.center.x, e.dxf.center.y, e.dxf.radius))
            elif e.dxftype() == "LWPOLYLINE":
                out.append(("P", e.dxf.layer, tuple(tuple(p) for p in e.get_points())))
            elif e.dxftype() == "TEXT":
                out.append(("T", e.dxf.text, e.dxf.insert.x, e.dxf.insert.y))
        return out

    d1, s1 = build_beam_section(spec)
    d2, s2 = build_beam_section(spec)
    assert geometry(d1) == geometry(d2)
    assert [r.to_dict() for r in s1] == [r.to_dict() for r in s2]
