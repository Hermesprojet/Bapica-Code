"""Beam elevation and complete rebar schedule.

The cross-section in :mod:`beam_section` shows what is in the beam; the
elevation shows *how long* each bar is, which is what a steel fixer and a
quantity surveyor actually need. It is also what turns the schedule from
partial — the section generator cannot know a bar's length — into complete,
with masses.

What this module refuses to decide
----------------------------------
**Curtailment.** Where a bar may stop depends on the moment envelope along the
span, shifted by the shift rule of §9.2.1.3. That is a design decision on a
diagram this module has never seen. So bar extents are *supplied*, and a bar
whose extent is not given is drawn over the full span — the conservative
choice, and one the reader can see rather than one hidden in a default.

**Link zones.** EN 1992-1-1 fixes a maximum spacing (§9.2.2(6)), never a
zoning. Splitting a span into a dense end zone and a sparse middle is the
engineer's arbitration between steel and labour. Zones are supplied; the module
checks each against ``s_l,max`` and refuses one that exceeds it.

What it does compute
--------------------
Developed lengths, from geometry the caller gave and anchorage lengths the
anchorage module produced. That is arithmetic on stated inputs, not a choice.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Final

import ezdxf
from ezdxf.document import Drawing

from ..exceptions import InconsistentInput
from ..legal import DRAFT_WATERMARK, Language
from .beam_section import _setup_document, _text
from .modele import BarRow, RebarScheduleRow, masse_kg
from .layers import (
    L_AXES,
    L_COFFRAGE,
    L_COTATION,
    L_FERR_PRINCIPAL,
    L_FERR_TRANSVERSAL,
    L_TEXTE,
)

__all__ = [
    "LinkZone",
    "LongitudinalBar",
    "BeamElevationSpec",
    "build_beam_elevation",
]

#: EN 1992-1-1 Tab. 8.1N: minimum mandrel diameter, as a multiple of phi.
_MANDREL_SMALL: Final = 4.0
_MANDREL_LARGE: Final = 7.0
_MANDREL_THRESHOLD_MM: Final = 16.0


@dataclass(frozen=True, slots=True)
class LinkZone:
    """A stretch of the span with one link spacing.

    :param start: distance from the left face of the beam, mm.
    :param end: idem, mm.
    :param spacing: link spacing in this zone, mm.
    """

    start: float
    end: float
    spacing: float

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise InconsistentInput(
                f"zone de cadres vide ou inversee: {self.start} → {self.end} mm"
            )
        if self.spacing <= 0:
            raise InconsistentInput("l'espacement des cadres doit etre positif")

    @property
    def length(self) -> float:
        return self.end - self.start

    def link_count(self) -> int:
        """Links in this zone, ends included.

        Rounded UP: a zone of 1 000 mm at 150 mm takes seven links, not six and
        two thirds. Rounding down would leave a gap wider than the spacing the
        calculation assumed.
        """
        return int(math.ceil(self.length / self.spacing)) + 1


@dataclass(frozen=True, slots=True)
class LongitudinalBar:
    """One row of longitudinal bars, seen in elevation.

    :param row: the row as the cross-section knows it.
    :param position: ``"bottom"`` or ``"top"``.
    :param start: where the bar starts, mm from the left face. ``None`` means
        the left end of the beam.
    :param end: where it stops. ``None`` means the right end.
    :param anchorage_each_end: straight anchorage length added at EACH end,
        mm — normally ``l_bd`` from :mod:`eurostruct_engine.ec2.anchorage`.
    :param hook_each_end: ``True`` when the bar ends in a 90° hook, which adds
        the bend to the developed length.
    """

    row: BarRow
    position: str = "bottom"
    start: float | None = None
    end: float | None = None
    anchorage_each_end: float = 0.0
    hook_each_end: bool = False

    def __post_init__(self) -> None:
        if self.position not in ("bottom", "top"):
            raise InconsistentInput(
                f"position '{self.position}' inconnue: 'bottom' ou 'top'."
            )
        if self.anchorage_each_end < 0:
            raise InconsistentInput("la longueur d'ancrage ne peut pas etre negative")

    def extent(self, span: float) -> tuple[float, float]:
        """Where the bar runs, resolving ``None`` to the beam ends."""
        a = 0.0 if self.start is None else self.start
        b = span if self.end is None else self.end
        if b <= a:
            raise InconsistentInput(
                f"la barre '{self.row.mark}' se termine ({b} mm) avant de "
                f"commencer ({a} mm)."
            )
        return a, b

    def developed_length(self, span: float) -> float:
        """Length of steel to cut, mm.

        Straight run, plus the anchorage at each end, plus the hooks when
        present. The hook allowance is the *bend*, computed from the mandrel of
        Tab. 8.1N and a leg of 5 phi — not a habit, a geometry.
        """
        a, b = self.extent(span)
        length = (b - a) + 2.0 * self.anchorage_each_end
        if self.hook_each_end:
            phi = self.row.diameter
            mandrel = _MANDREL_SMALL if phi <= _MANDREL_THRESHOLD_MM else _MANDREL_LARGE
            # Quarter of a circle on the bar centreline, plus the straight leg.
            radius = mandrel * phi / 2.0 + phi / 2.0
            length += 2.0 * (math.pi * radius / 2.0 + 5.0 * phi)
        return length


@dataclass(frozen=True, slots=True)
class BeamElevationSpec:
    """Everything needed to draw the elevation.

    :param span: clear span between support faces, mm.
    :param h: overall depth, mm.
    :param support_width: bearing width at each end, mm, drawn for context.
    :param link_zones: must tile the span without gap or overlap.
    :param s_l_max: maximum longitudinal link spacing from §9.2.2(6). Every
        zone is checked against it; ``None`` skips the check and says so on the
        sheet rather than passing silently.
    """

    span: float
    h: float
    cover: float
    link_diameter: float
    bars: tuple[LongitudinalBar, ...]
    link_zones: tuple[LinkZone, ...]
    link_mark: str = "C1"
    support_width: float = 200.0
    s_l_max: float | None = None
    plot_scale: float = 50.0
    title: str = "ELEVATION POUTRE"
    project: str = ""
    element: str = ""
    concrete_grade: str = ""
    steel_grade: str = ""
    index: str = "A"
    date: str = ""
    language: Language = Language.FR
    validated: bool = False

    def __post_init__(self) -> None:
        if self.span <= 0 or self.h <= 0:
            raise InconsistentInput("la portee et la hauteur doivent etre positives")
        if not self.bars:
            raise InconsistentInput(
                "une elevation sans aucune barre longitudinale ne represente "
                "rien: fournir au moins un lit."
            )
        if not self.link_zones:
            raise InconsistentInput("aucune zone de cadres fournie")

        zones = sorted(self.link_zones, key=lambda z: z.start)
        if abs(zones[0].start) > 1e-9:
            raise InconsistentInput(
                f"les zones de cadres commencent a {zones[0].start} mm et non a "
                "l'origine: une portion de poutre resterait sans cadres."
            )
        for a, b in zip(zones, zones[1:]):
            if abs(a.end - b.start) > 1e-9:
                raise InconsistentInput(
                    f"discontinuite entre les zones de cadres: {a.end} mm puis "
                    f"{b.start} mm. Une poutre n'a pas de portion sans cadres."
                )
        if abs(zones[-1].end - self.span) > 1e-9:
            raise InconsistentInput(
                f"les zones de cadres s'arretent a {zones[-1].end} mm pour une "
                f"portee de {self.span} mm."
            )
        if self.s_l_max is not None:
            for z in zones:
                if z.spacing > self.s_l_max + 1e-9:
                    raise InconsistentInput(
                        f"la zone {z.start:.0f}–{z.end:.0f} mm a un espacement de "
                        f"{z.spacing:.0f} mm, superieur au maximum "
                        f"§9.2.2(6) de {self.s_l_max:.0f} mm."
                    )

    def total_links(self) -> int:
        """Links over the whole beam.

        Zones share their boundary link, so the shared ones are subtracted:
        counting each zone's own ends would order one extra link per junction.
        """
        return sum(z.link_count() for z in self.link_zones) - (len(self.link_zones) - 1)


def _link_perimeter(spec: BeamElevationSpec, width: float) -> float:
    """Developed length of one closed link, mm.

    Perimeter of the centreline, minus what the four bends save against sharp
    corners, plus the two anchorage hooks §8.5 requires on a closed stirrup.
    Same convention as the cross-section generator, so the two schedules agree.
    """
    off = spec.cover + spec.link_diameter / 2.0
    w = width - 2.0 * off
    d = spec.h - 2.0 * off
    phi = spec.link_diameter
    mandrel = _MANDREL_SMALL if phi <= _MANDREL_THRESHOLD_MM else _MANDREL_LARGE
    r = mandrel * phi / 2.0 + phi / 2.0
    sharp = 2.0 * (w + d)
    # Each 90° bend replaces two straight legs of r by a quarter circle.
    bends = 4.0 * r * (2.0 - math.pi / 2.0)
    hooks = 2.0 * (math.pi * r / 2.0 + 10.0 * phi)
    return sharp - bends + hooks


def build_beam_elevation(
    spec: BeamElevationSpec, *, width: float
) -> tuple[Drawing, list[RebarScheduleRow]]:
    """Build the elevation DXF and the complete schedule.

    :param width: beam width, mm — needed for the link perimeter, and not part
        of an elevation otherwise.
    :returns: the ``ezdxf`` document and the schedule, longitudinal bars first
        then links, in the order they appear on the sheet.
    """
    s = spec.plot_scale
    txt_h = 2.5 * s
    doc = _setup_document(s)
    msp = doc.modelspace()

    # --- concrete outline and supports -------------------------------------
    msp.add_lwpolyline(
        [(0.0, 0.0), (spec.span, 0.0), (spec.span, spec.h), (0.0, spec.h)],
        close=True, dxfattribs={"layer": L_COFFRAGE},
    )
    for x in (0.0, spec.span):
        sign = 1.0 if x == 0.0 else -1.0
        msp.add_lwpolyline(
            [
                (x, 0.0),
                (x - sign * spec.support_width, 0.0),
                (x - sign * spec.support_width, -spec.h * 0.25),
                (x, -spec.h * 0.25),
            ],
            close=True, dxfattribs={"layer": L_AXES},
        )

    # --- longitudinal bars -------------------------------------------------
    inner = spec.cover + spec.link_diameter
    schedule: list[RebarScheduleRow] = []
    for i, bar in enumerate(spec.bars):
        a, b = bar.extent(spec.span)
        # Stack the rows so several bottom rows do not draw on top of each
        # other; the elevation shows the layering, the section shows the truth.
        offset = inner + bar.row.diameter / 2.0 + i * bar.row.diameter * 1.6
        y = offset if bar.position == "bottom" else spec.h - offset
        msp.add_line((a, y), (b, y), dxfattribs={"layer": L_FERR_PRINCIPAL})
        if bar.hook_each_end:
            hook = 5.0 * bar.row.diameter
            direction = 1.0 if bar.position == "bottom" else -1.0
            msp.add_line((a, y), (a, y + direction * hook),
                         dxfattribs={"layer": L_FERR_PRINCIPAL})
            msp.add_line((b, y), (b, y + direction * hook),
                         dxfattribs={"layer": L_FERR_PRINCIPAL})

        length = bar.developed_length(spec.span)
        label = f"{bar.row.mark}: {bar.row.count} HA{bar.row.diameter:g} L={length:.0f}"
        _text(msp, label, (a + b) / 2.0, y + txt_h * 0.4, txt_h, L_TEXTE)

        comment = []
        if bar.anchorage_each_end:
            comment.append(f"ancrage {bar.anchorage_each_end:.0f} mm par about")
        if bar.hook_each_end:
            comment.append("crochets 90 degres aux deux abouts")
        if bar.start is not None or bar.end is not None:
            comment.append(f"arret declare: {a:.0f}–{b:.0f} mm")
        schedule.append(
            RebarScheduleRow(
                mark=bar.row.mark,
                diameter=bar.row.diameter,
                count=bar.row.count,
                unit_length_mm=length,
                total_length_mm=length * bar.row.count,
                mass_kg=masse_kg(bar.row.diameter, length * bar.row.count),
                shape_code="droite avec crochets" if bar.hook_each_end else "droite",
                comment="; ".join(comment),
            )
        )

    # --- links --------------------------------------------------------------
    for zone in spec.link_zones:
        n = zone.link_count()
        step = zone.length / max(n - 1, 1)
        for k in range(n):
            x = zone.start + k * step
            msp.add_line((x, inner), (x, spec.h - inner),
                         dxfattribs={"layer": L_FERR_TRANSVERSAL})
        _text(
            msp, f"{spec.link_mark} HA{spec.link_diameter:g} e={zone.spacing:.0f}",
            (zone.start + zone.end) / 2.0, spec.h + txt_h * 1.2, txt_h, L_TEXTE,
        )
        msp.add_line((zone.start, spec.h + txt_h * 0.6),
                     (zone.end, spec.h + txt_h * 0.6),
                     dxfattribs={"layer": L_COTATION})

    n_links = spec.total_links()
    link_len = _link_perimeter(spec, width)
    schedule.append(
        RebarScheduleRow(
            mark=spec.link_mark,
            diameter=spec.link_diameter,
            count=n_links,
            unit_length_mm=link_len,
            total_length_mm=link_len * n_links,
            mass_kg=masse_kg(spec.link_diameter, link_len * n_links),
            shape_code="cadre ferme",
            comment=(
                "longueur developpee sur l'axe, rayons de cintrage Tab. 8.1N, "
                "crochets d'ancrage §8.5 compris; "
                + ", ".join(
                    f"{z.link_count()} a e={z.spacing:.0f} sur "
                    f"{z.start:.0f}–{z.end:.0f}" for z in spec.link_zones
                )
                + f" (cadres de jonction comptes une fois: total {n_links})"
            ),
        )
    )

    # --- span dimension -----------------------------------------------------
    msp.add_line((0.0, -spec.h * 0.45), (spec.span, -spec.h * 0.45),
                 dxfattribs={"layer": L_COTATION})
    _text(msp, f"{spec.span:.0f}", spec.span / 2.0, -spec.h * 0.45 + txt_h * 0.3,
          txt_h, L_COTATION)

    if spec.s_l_max is None:
        _text(
            msp, "ESPACEMENT MAXIMAL §9.2.2(6) NON VERIFIE: s_l,max non fourni",
            0.0, -spec.h * 0.75, txt_h, L_TEXTE,
        )

    if not spec.validated:
        _text(msp, DRAFT_WATERMARK[spec.language],
              spec.span / 2.0, spec.h / 2.0, txt_h * 2.5, L_TEXTE)

    return doc, schedule
