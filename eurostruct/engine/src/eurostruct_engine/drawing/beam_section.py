"""Deterministic DXF generation of a reinforced concrete beam cross-section.

Cahier des charges section 5.2 and interdiction 1: drawings are produced by a
deterministic library (``ezdxf``), never by a language model. Nothing in this
module reads or writes anything other than its arguments.

The section is drawn in model space at 1:1 in millimetres. ``plot_scale`` only
governs the size of annotation (text, arrows, dimension offsets), so that the
sheet reads correctly once plotted at that scale, while the geometry keeps true
coordinates — cahier des charges section 7.2, "echelle vraie".

Coordinate system: origin at the bottom-left corner of the concrete outline,
X to the right, Y upwards.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Final, Sequence

import ezdxf
from ezdxf.document import Drawing
from ezdxf.enums import TextEntityAlignment

from ..exceptions import InconsistentInput
from ..legal import DRAFT_WATERMARK, MANDATORY_NOTICE, Language
from ..version import ENGINE_VERSION
from .layers import (
    L_CARTOUCHE,
    L_COFFRAGE,
    L_COTATION,
    L_FERR_PRINCIPAL,
    L_FERR_TRANSVERSAL,
    L_TEXTE,
    LAYERS,
)

__all__ = [
    "BarRow",
    "BeamSectionSpec",
    "RebarScheduleRow",
    "build_beam_section",
    "DIMSTYLE",
    "LEGAL_NOTICE",
]

#: DEUX DESSINS DU MEME CALCUL DOIVENT DONNER LES MEMES OCTETS.
#:
#: L'adressage par contenu l'exige, et rien d'autre ne le garantit : le chemin
#: de stockage d'un livrable derive de son SHA-256, si bien qu'un fichier dont
#: les octets bougent d'une execution a l'autre se depose deux fois, sous deux
#: chemins, et aucune relecture ne peut plus prouver qu'il s'agit du meme
#: dessin. C'est la meme lecon que la compression zlib du PDF.
#:
#: Sans ce reglage, ``ezdxf`` estampille a l'ecriture quatre valeurs volatiles.
#: Mesure faite sur deux rendus successifs d'une meme section (tailles egales,
#: 63 994 octets, huit lignes differentes) :
#:
#:     -{519CC0F6-828B-4982-9AC4-6C13FD7FBCE4}   $FINGERPRINTGUID
#:     +{FDA97C7E-8F29-489D-8FBA-885ECF5F7232}
#:     -{7E13FDF5-4415-4F9A-83B7-EAAC59418340}   $VERSIONGUID
#:     +{DB5681C2-676A-4857-B418-D9EF7CD0E489}
#:     -1.4.4 @ 2026-09-01T07:14:25.870408+00:00 marqueur ezdxf
#:     +1.4.4 @ 2026-09-01T07:14:25.895330+00:00
#:
#: plus les dates julienne ``$TDCREATE`` / ``$TDUPDATE``.
#:
#: Le nom de l'option dit « for testing » parce que c'est l'usage qu'en fait
#: ``ezdxf`` ; son effet, lui, est exactement celui qu'il nous faut : des
#: metadonnees fixes. Elle est posee au chargement du module et **jamais
#: remise a False**, de sorte qu'aucune execution concurrente ne puisse
#: tomber dans une fenetre ou elle serait desactivee. Elle vaut pour la
#: creation du document autant que pour son ecriture — la date de creation
#: est gravee des ``ezdxf.new()``.
#:
#: CE QUE CELA NE FAIT PAS PERDRE : la date reelle de production et l'identite
#: du moteur ne vivent pas dans l'en-tete DXF mais dans la ligne de livrable
#: (``created_at``, ``engine_build``), qui est la seule source opposable.
ezdxf.options.write_fixed_meta_data_for_testing = True

DIMSTYLE: Final = "EUROSTRUCT"

#: Mandatory notice — cahier des charges §9, on every page of every deliverable.
#: Sourced from :mod:`eurostruct_engine.legal` so the five language versions
#: cannot drift apart between document types.
LEGAL_NOTICE: Final = MANDATORY_NOTICE[Language.FR]

#: Bulge value of a 90-degree arc segment in an LWPOLYLINE: tan(90/4).
_BULGE_90: Final = math.tan(math.radians(90.0) / 4.0)

#: Nominal steel density used for the schedule — EN 1992-1-1 §3.2.7(3).
_STEEL_DENSITY_KG_PER_M3: Final = 7850.0


@dataclass(frozen=True, slots=True)
class BarRow:
    """A row of identical longitudinal bars.

    :param count: number of bars in the row.
    :param diameter: nominal bar diameter, mm.
    :param mark: bar mark shown on the drawing and in the schedule.
    :param length: developed length of one bar, mm, for the schedule. Optional
        because a cross-section alone does not determine it; the beam
        elevation generator supplies it.
    """

    count: int
    diameter: float
    mark: str
    length: float | None = None

    def area(self) -> float:
        """Total area of the row, mm²."""
        return self.count * math.pi * self.diameter**2 / 4.0


@dataclass(frozen=True, slots=True)
class BeamSectionSpec:
    """Everything needed to draw one cross-section.

    :param b: width, mm.
    :param h: overall depth, mm.
    :param cover: nominal cover to the outer face of the links, mm
        (``c_nom`` of EN 1992-1-1 §4.4.1).
    :param link_diameter: diameter of the transverse reinforcement, mm.
    :param bottom: rows of bottom (tension) reinforcement.
    :param top: rows of top reinforcement.
    :param link_spacing: link spacing, mm, shown in the label.
    :param plot_scale: denominator of the plotting scale, e.g. 20 for 1:20.
    """

    b: float
    h: float
    cover: float
    link_diameter: float
    bottom: tuple[BarRow, ...] = ()
    top: tuple[BarRow, ...] = ()
    link_spacing: float | None = None
    link_mark: str = "C1"
    plot_scale: float = 20.0
    title: str = "COUPE POUTRE"
    project: str = ""
    element: str = ""
    concrete_grade: str = ""
    steel_grade: str = ""
    exposure_class: str = ""
    index: str = "A"
    date: str = ""
    #: Additional notice carried by the title block — for instance
    #: « PROJET — NON SIGNABLE » when unconfirmed national parameters may have
    #: been used. DISTINCT from the draft watermark: that one says nobody has
    #: validated the sheet, this one says the numbers themselves rest on
    #: parameters no official source has confirmed. A drawing that carried only
    #: the first would read as « just needs a signature », which would be false.
    mention: str = ""
    #: Language of the notices printed on the sheet (§11: FR/NL/EN/ES/DE).
    language: Language = Language.FR
    #: False until an authorised engineer has validated the calculation. An
    #: unvalidated sheet carries the draft watermark — §9: a deliverable that
    #: nobody has signed must not look like one that someone has.
    validated: bool = False

    def __post_init__(self) -> None:
        if self.b <= 0 or self.h <= 0:
            raise InconsistentInput("b et h doivent etre strictement positifs")
        if self.cover < 0:
            raise InconsistentInput("l'enrobage ne peut pas etre negatif")
        free = self.b - 2.0 * (self.cover + self.link_diameter)
        if free <= 0:
            raise InconsistentInput(
                f"largeur insuffisante: b = {self.b} mm ne laisse aucune place "
                f"entre les cadres pour un enrobage de {self.cover} mm et des "
                f"cadres de {self.link_diameter} mm."
            )
        for row in (*self.bottom, *self.top):
            if row.count < 1:
                raise InconsistentInput(f"le lit '{row.mark}' doit compter au moins une barre")
            if row.count > 1 and row.count * row.diameter >= free:
                raise InconsistentInput(
                    f"le lit '{row.mark}' ({row.count} HA{row.diameter:g}) ne tient pas "
                    f"dans la largeur libre de {free:.0f} mm entre cadres."
                )


@dataclass(frozen=True, slots=True)
class RebarScheduleRow:
    """One line of the nomenclature — cahier des charges section 7.2."""

    mark: str
    diameter: float
    count: int
    unit_length_mm: float | None
    total_length_mm: float | None
    mass_kg: float | None
    shape_code: str
    comment: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "mark": self.mark,
            "diameter_mm": self.diameter,
            "count": self.count,
            "unit_length_mm": self.unit_length_mm,
            "total_length_mm": self.total_length_mm,
            "mass_kg": self.mass_kg,
            "shape_code": self.shape_code,
            "comment": self.comment,
        }


# ---------------------------------------------------------------------------
def _setup_document(scale: float) -> Drawing:
    doc = ezdxf.new(dxfversion="R2018", setup=True)
    doc.header["$INSUNITS"] = 4  # millimetres
    doc.header["$MEASUREMENT"] = 1  # metric

    for spec in LAYERS:
        layer = doc.layers.add(name=spec.name, color=spec.color)
        layer.dxf.lineweight = spec.lineweight
        if spec.linetype in doc.linetypes:
            layer.dxf.linetype = spec.linetype
        layer.description = spec.description

    # A dimension style bound to the STANDARD text style, so the file opens
    # identically in AutoCAD, BricsCAD and LibreCAD without a font substitution.
    ds = doc.dimstyles.add(DIMSTYLE)
    ds.dxf.dimtxsty = "Standard"
    ds.dxf.dimscale = scale
    ds.dxf.dimtxt = 2.5
    ds.dxf.dimasz = 2.5
    ds.dxf.dimexe = 1.25
    ds.dxf.dimexo = 2.0
    ds.dxf.dimgap = 0.8
    ds.dxf.dimdec = 0
    ds.dxf.dimlunit = 2
    ds.dxf.dimtih = 0
    ds.dxf.dimtoh = 0
    return doc


def _rounded_rect_points(
    x0: float, y0: float, x1: float, y1: float, r: float
) -> list[tuple[float, float, float]]:
    """Vertices of a rounded rectangle as (x, y, bulge), counter-clockwise.

    Used for the centreline of a closed link, whose corners follow the mandrel
    bend radius of EN 1992-1-1 §8.3.
    """
    b = _BULGE_90
    return [
        (x0 + r, y0, 0.0),
        (x1 - r, y0, b),
        (x1, y0 + r, 0.0),
        (x1, y1 - r, b),
        (x1 - r, y1, 0.0),
        (x0 + r, y1, b),
        (x0, y1 - r, 0.0),
        (x0, y0 + r, b),
    ]


def _bar_x_positions(spec: BeamSectionSpec, row: BarRow) -> list[float]:
    """X coordinates of the bar centres of a row, evenly distributed.

    The outermost bars sit against the inside face of the links, offset by half
    a bar diameter.
    """
    inset = spec.cover + spec.link_diameter + row.diameter / 2.0
    left, right = inset, spec.b - inset
    if row.count == 1:
        return [spec.b / 2.0]
    step = (right - left) / (row.count - 1)
    return [left + i * step for i in range(row.count)]


def _draw_bar(msp: Any, x: float, y: float, diameter: float) -> None:
    """A longitudinal bar seen in section: filled circle."""
    r = diameter / 2.0
    msp.add_circle(center=(x, y), radius=r, dxfattribs={"layer": L_FERR_PRINCIPAL})
    hatch = msp.add_hatch(dxfattribs={"layer": L_FERR_PRINCIPAL, "color": 1})
    edge = hatch.paths.add_edge_path()
    edge.add_arc(center=(x, y), radius=r, start_angle=0.0, end_angle=360.0)


def _text(
    msp: Any, s: str, x: float, y: float, height: float, layer: str = L_TEXTE
) -> None:
    msp.add_text(s, height=height, dxfattribs={"layer": layer}).set_placement(
        (x, y), align=TextEntityAlignment.LEFT
    )


def build_beam_section(spec: BeamSectionSpec) -> tuple[Drawing, list[RebarScheduleRow]]:
    """Build the DXF document of one beam cross-section and its schedule.

    :returns: the ``ezdxf`` document and the rebar schedule rows.
    """
    s = spec.plot_scale
    txt_h = 2.5 * s  # 2,5 mm on the plotted sheet
    doc = _setup_document(s)
    msp = doc.modelspace()

    # --- concrete outline --------------------------------------------------
    msp.add_lwpolyline(
        [(0.0, 0.0), (spec.b, 0.0), (spec.b, spec.h), (0.0, spec.h)],
        close=True,
        dxfattribs={"layer": L_COFFRAGE},
    )

    # --- link (closed stirrup) --------------------------------------------
    # Centreline of the link, inset by the cover plus half its own diameter.
    off = spec.cover + spec.link_diameter / 2.0
    # Minimum mandrel diameter, EN 1992-1-1 Tab. 8.1N: 4*phi for phi <= 16 mm,
    # 7*phi beyond. Radius to the link centreline adds half a diameter.
    mandrel = 4.0 if spec.link_diameter <= 16.0 else 7.0
    r_centre = mandrel * spec.link_diameter / 2.0 + spec.link_diameter / 2.0
    r_centre = min(r_centre, (min(spec.b, spec.h) - 2.0 * off) / 2.0)
    msp.add_lwpolyline(
        _rounded_rect_points(off, off, spec.b - off, spec.h - off, r_centre),
        format="xyb",
        close=True,
        dxfattribs={"layer": L_FERR_TRANSVERSAL},
    )

    # --- longitudinal bars -------------------------------------------------
    schedule: list[RebarScheduleRow] = []
    for row in spec.bottom:
        y = spec.cover + spec.link_diameter + row.diameter / 2.0
        for x in _bar_x_positions(spec, row):
            _draw_bar(msp, x, y, row.diameter)
        schedule.append(_schedule_row(row, "00", "lit inferieur"))
    for row in spec.top:
        y = spec.h - (spec.cover + spec.link_diameter + row.diameter / 2.0)
        for x in _bar_x_positions(spec, row):
            _draw_bar(msp, x, y, row.diameter)
        schedule.append(_schedule_row(row, "00", "lit superieur"))

    if spec.link_diameter > 0:
        # Developed length of the centreline actually drawn: the sharp-corner
        # perimeter less what each 90-degree bend cuts off. Keeping this
        # consistent with the geometry matters — the schedule and the drawing
        # must describe the same bar.
        sharp = 2.0 * ((spec.b - 2.0 * off) + (spec.h - 2.0 * off))
        bend_saving = 4.0 * r_centre * (2.0 - math.pi / 2.0)
        developed = sharp - bend_saving
        schedule.append(
            RebarScheduleRow(
                mark=spec.link_mark,
                diameter=spec.link_diameter,
                count=1,
                unit_length_mm=developed,
                total_length_mm=developed,
                mass_kg=_mass_kg(spec.link_diameter, developed),
                shape_code="51",
                comment=(
                    (
                        f"cadre ferme, espacement {spec.link_spacing:g} mm. "
                        if spec.link_spacing
                        else "cadre ferme. "
                    )
                    + "Longueur developpee du trace: retours d'ancrage NON compris "
                    "(EN 1992-1-1 §8.5) — a completer par le module de faconnage."
                ),
            )
        )

    # --- dimensions --------------------------------------------------------
    off_dim = 18.0 * s
    msp.add_linear_dim(
        base=(spec.b / 2.0, -off_dim),
        p1=(0.0, 0.0),
        p2=(spec.b, 0.0),
        dimstyle=DIMSTYLE,
        dxfattribs={"layer": L_COTATION},
    ).render()
    msp.add_linear_dim(
        base=(-off_dim, spec.h / 2.0),
        p1=(0.0, 0.0),
        p2=(0.0, spec.h),
        angle=90.0,
        dimstyle=DIMSTYLE,
        dxfattribs={"layer": L_COTATION},
    ).render()

    # --- annotation --------------------------------------------------------
    _text(msp, f"{spec.title} {spec.element}".strip(), 0.0, spec.h + 6.0 * s, txt_h * 1.4)
    _text(
        msp,
        f"{spec.b:g} x {spec.h:g} mm — enrobage {spec.cover:g} mm",
        0.0,
        spec.h + 2.5 * s,
        txt_h,
    )

    label_x = spec.b + 8.0 * s
    line = 0
    for row in spec.bottom:
        _text(msp, f"{row.mark}: {row.count} HA{row.diameter:g} (inf.)",
              label_x, spec.h * 0.25 - line * 4.0 * s, txt_h)
        line += 1
    for row in spec.top:
        _text(msp, f"{row.mark}: {row.count} HA{row.diameter:g} (sup.)",
              label_x, spec.h * 0.75 + line * 4.0 * s, txt_h)
        line += 1
    if spec.link_diameter > 0:
        sp = f" e = {spec.link_spacing:g} mm" if spec.link_spacing else ""
        _text(msp, f"{spec.link_mark}: cadre HA{spec.link_diameter:g}{sp}",
              label_x, spec.h * 0.5, txt_h)

    _draw_cartouche(msp, spec, txt_h)
    if not spec.validated:
        _draw_draft_watermark(msp, spec, txt_h)
    return doc, schedule


def _draw_draft_watermark(msp: Any, spec: BeamSectionSpec, txt_h: float) -> None:
    """Stamp an unvalidated sheet, across the section itself."""
    msp.add_text(
        DRAFT_WATERMARK[spec.language],
        height=txt_h * 2.2,
        rotation=45.0,
        dxfattribs={"layer": L_TEXTE, "color": 8},
    ).set_placement(
        (spec.b / 2.0, spec.h / 2.0), align=TextEntityAlignment.MIDDLE_CENTER
    )


def _schedule_row(row: BarRow, shape_code: str, comment: str) -> RebarScheduleRow:
    total = row.length * row.count if row.length is not None else None
    return RebarScheduleRow(
        mark=row.mark,
        diameter=row.diameter,
        count=row.count,
        unit_length_mm=row.length,
        total_length_mm=total,
        mass_kg=_mass_kg(row.diameter, total) if total is not None else None,
        shape_code=shape_code,
        comment=comment,
    )


def _mass_kg(diameter_mm: float, length_mm: float) -> float:
    """Mass of a bar, kg, from its nominal diameter and developed length."""
    area_m2 = math.pi * (diameter_mm / 1000.0) ** 2 / 4.0
    return area_m2 * (length_mm / 1000.0) * _STEEL_DENSITY_KG_PER_M3


def _draw_cartouche(msp: Any, spec: BeamSectionSpec, txt_h: float) -> None:
    """Title block, including the mandatory notice of cahier des charges §9."""
    s = spec.plot_scale
    w, h = 180.0 * s, 46.0 * s
    x0 = spec.b + 8.0 * s
    y0 = -h - 26.0 * s

    msp.add_lwpolyline(
        [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)],
        close=True,
        dxfattribs={"layer": L_CARTOUCHE},
    )

    pad = 2.0 * s
    rows: Sequence[str] = (
        spec.project or "—",
        f"Element: {spec.element or '—'}    Indice: {spec.index}    Date: {spec.date or '—'}",
        f"Beton: {spec.concrete_grade or '—'}    Acier: {spec.steel_grade or '—'}"
        f"    Exposition: {spec.exposure_class or '—'}",
        f"Echelle 1:{spec.plot_scale:g}    Cotes en mm    Moteur: eurostruct-engine {ENGINE_VERSION}",
    )
    y = y0 + h - pad - txt_h
    for i, text in enumerate(rows):
        _text(msp, text, x0 + pad, y, txt_h * (1.3 if i == 0 else 1.0), layer=L_CARTOUCHE)
        y -= txt_h * 2.0

    # Wrapped here rather than by a text engine: a DXF has no reflow, and the
    # notice must be legible whatever opens the file.
    # LA MENTION AVANT LA NOTICE, ET EN PLUS GRAS. Elle dit que les nombres
    # eux-memes reposent sur des parametres non confirmes; la notice dit qu'un
    # ingenieur doit relire. Un lecteur qui ne lirait qu'une ligne doit lire
    # celle-la.
    if spec.mention:
        y -= txt_h * 0.4
        for chunk in _wrap(spec.mention, 64):
            _text(msp, chunk, x0 + pad, y, txt_h * 1.1, layer=L_CARTOUCHE)
            y -= txt_h * 1.5

    y -= txt_h * 0.4
    for chunk in _wrap(MANDATORY_NOTICE[spec.language], 78):
        _text(msp, chunk, x0 + pad, y, txt_h * 0.85, layer=L_CARTOUCHE)
        y -= txt_h * 1.2


def _wrap(text: str, width: int) -> list[str]:
    """Greedy wrap, deterministic for a given input."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if len(candidate) > width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines
