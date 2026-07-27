"""The note de calcul — assembly and rendering.

The property this file exists to defend: **no number reaches the page except
through a journal entry**. Interdiction 1 forbids a language model producing a
calculation result; the note makes that structural by having no arithmetic of
its own, and :func:`test_every_printed_value_comes_from_a_journal_entry` checks
it on a real four-section note — bending, shear, anchorage and serviceability —
rather than trusting the design.
"""

from __future__ import annotations

import re
from datetime import date
from html import escape

import pytest

from eurostruct_engine.ec2 import (
    CrackControlDetail,
    ExposureClass,
    RectangularSection,
    ShearLinks,
    ShearSection,
    design_anchorage,
    design_flexure,
    design_serviceability,
    design_shear,
)
from eurostruct_engine.legal import Language
from eurostruct_engine.materials import concrete, reinforcement
from eurostruct_engine.materials.reinforcement import bars_area
from eurostruct_engine.note import (
    CalculationNote,
    NoteSection,
    render_html,
    render_text,
    section_from_design,
)
from eurostruct_engine.units import Q_, fmt
from eurostruct_engine.version import ENGINE_VERSION

ISSUED = date(2026, 7, 27)


@pytest.fixture
def designs(params_fr):
    c, s = concrete("C30/37"), reinforcement("B500B")
    flexure = design_flexure(
        section=RectangularSection(b=Q_(300, "mm"), h=Q_(600, "mm"), d=Q_(550, "mm")),
        concrete=c, steel=s, M_Ed=Q_(250, "kN*m"), params=params_fr,
        element="P1", A_s_provided=bars_area(4, 20),
    )
    shear = design_shear(
        section=ShearSection(b_w=Q_(300, "mm"), d=Q_(550, "mm"), A_sl=bars_area(4, 20)),
        concrete=c, steel=s, V_Ed=Q_(300, "kN"), params=params_fr, cot_theta=2.5,
        links=ShearLinks(A_sw=Q_(157, "mm**2"), s=Q_(150, "mm")), element="P1",
    )
    anchorage = design_anchorage(
        concrete=c, steel=s, phi=Q_(20, "mm"), params=params_fr, element="P1",
    )
    sls = design_serviceability(
        section=RectangularSection(b=Q_(300, "mm"), h=Q_(600, "mm"), d=Q_(550, "mm")),
        concrete=c, steel=s, A_s=bars_area(4, 20),
        M_qp=Q_(120, "kN*m"), M_char=Q_(180, "kN*m"), phi_creep=2.0,
        detail=CrackControlDetail(
            phi=Q_(20, "mm"), cover=Q_(40, "mm"), bar_spacing=Q_(60, "mm")
        ),
        exposure_class=ExposureClass.XC3, params=params_fr, element="P1",
    )
    return flexure, shear, anchorage, sls


@pytest.fixture
def note(designs, params_fr):
    flexure, shear, anchorage, sls = designs
    return CalculationNote(
        project="Immeuble R+4",
        element="Poutre P1",
        sections=(
            section_from_design(
                flexure, title="Flexion simple a l'ELU", basis="EN 1992-1-1 §6.1",
                assumptions=("Diagramme rectangulaire §3.1.7(3)",),
            ),
            section_from_design(
                shear, title="Effort tranchant a l'ELU", basis="EN 1992-1-1 §6.2",
                assumptions=("z = 0,9 d", "cot(theta) = 2,5 retenu par l'ingenieur"),
            ),
            section_from_design(
                anchorage, title="Ancrages", basis="EN 1992-1-1 §8.4 et §8.7",
            ),
            section_from_design(
                sls, title="Etats limites de service",
                basis="EN 1992-1-1 §7.2 et §7.3",
                assumptions=(
                    sls.cracking_statement,
                    "Coefficient de fluage phi = 2,0 fourni par l'ingenieur",
                    f"Classe d'exposition {sls.exposure_class.value}",
                ),
            ),
        ),
        ndp_summary=params_fr.summary(),
        issued_on=ISSUED,
    )


# ---------------------------------------------------------------------------
# The property that matters
# ---------------------------------------------------------------------------
def test_every_printed_value_comes_from_a_journal_entry(note) -> None:
    """Interdiction 1, made checkable.

    Collects every value the note could legitimately print — each journal step
    and each check's acting/resisting — and asserts that the HTML contains
    exactly those, formatted by the engine. A renderer that computed anything
    of its own would produce a string not in this set.
    """
    html = render_html(note)

    legitimate = set()
    for section in note.sections:
        for step in section.steps:
            legitimate.add(fmt(step.value))
        for check in section.checks:
            legitimate.add(fmt(check.acting))
            legitimate.add(fmt(check.resisting))

    # Chaque valeur du journal est bien imprimee...
    for value in legitimate:
        assert value in html, f"valeur du journal absente de la note: {value}"

    # ...et les cellules numeriques n'en contiennent aucune autre.
    printed = set(re.findall(r"<td class='num'>([^<]+)</td>", html))
    ratios = {f"{c.utilisation:.3f}"
              for s in note.sections for c in s.checks}
    unexplained = printed - legitimate - ratios
    assert not unexplained, (
        "la note imprime des valeurs qu'aucune etape de journal ne porte: "
        f"{sorted(unexplained)}"
    )


def test_the_note_owns_no_arithmetic(note) -> None:
    """The rendered figures are byte-identical to what the modules produced."""
    flexure_section = note.sections[0]
    step = flexure_section.journal.get("f_cd")
    assert fmt(step.value) in render_html(note)
    assert fmt(step.value) in render_text(note)


# ---------------------------------------------------------------------------
# What a note must carry
# ---------------------------------------------------------------------------
def test_the_mandatory_notice_precedes_every_result(note) -> None:
    """Interdiction 8: a reader who stops at page one must still have read it."""
    html = render_html(note)
    assert note.notice in html
    first_section = html.index("Flexion simple")
    assert html.index(note.notice) < first_section


def test_the_notice_follows_the_language_of_the_note(designs, params_fr) -> None:
    flexure, _, _, _ = designs
    section = section_from_design(flexure, title="Flexion", basis="§6.1")
    fr = CalculationNote(
        project="P", element="P1", sections=(section,),
        ndp_summary=params_fr.summary(), issued_on=ISSUED, language=Language.FR,
    )
    nl = CalculationNote(
        project="P", element="P1", sections=(section,),
        ndp_summary=params_fr.summary(), issued_on=ISSUED, language=Language.NL,
    )
    assert fr.notice != nl.notice
    assert nl.notice in render_html(nl)


def test_unverified_parameters_are_printed_in_the_note(note) -> None:
    """Interdiction 2: an unread value must be visible to whoever signs.

    Not in a log, not in a status field — in the document itself.
    """
    assert note.unverified_parameters
    html = render_html(note)
    assert "Parametres nationaux non releves" in html
    assert "ne peut pas etre emise en l'etat" in html
    for key in note.unverified_parameters:
        assert key in html


def test_the_regulatory_framework_is_printed(note) -> None:
    """Interdiction 4: a country is not always a "pure Eurocode" country."""
    html = render_html(note)
    fw = note.ndp_summary["regulatory_framework"]
    # Comparaison sur la forme ECHAPPEE: « l'AFNOR » sort « l&#x27;AFNOR ».
    # L'echappement est correct et voulu; c'est au test de s'y conformer.
    assert escape(fw["binding_reference"]) in html
    assert escape(fw["verification_regime"]) in html
    assert escape(fw["eurocode_status"]) in html


def test_the_engine_version_and_annex_editions_reach_the_page(note) -> None:
    """Section 8.2: a result nobody can reproduce is not defensible."""
    html = render_html(note)
    assert ENGINE_VERSION in html
    for annex in note.ndp_summary["annexes"]:
        assert annex["reference"] in html
        assert annex["edition"] in html


def test_every_cited_clause_is_listed(note) -> None:
    html = render_html(note)
    assert len(note.clauses()) > 20
    for clause in note.clauses():
        assert clause in html


# ---------------------------------------------------------------------------
# Refusals and honest silence
# ---------------------------------------------------------------------------
def test_an_empty_note_is_refused(params_fr) -> None:
    with pytest.raises(ValueError, match="ne verifie rien"):
        CalculationNote(
            project="P", element="P1", sections=(),
            ndp_summary=params_fr.summary(), issued_on=ISSUED,
        )


def test_a_note_without_a_regulatory_framework_is_refused(designs, params_fr) -> None:
    flexure, _, _, _ = designs
    stripped = dict(params_fr.summary())
    stripped["regulatory_framework"] = {}
    with pytest.raises(ValueError, match="cadre reglementaire"):
        CalculationNote(
            project="P", element="P1",
            sections=(section_from_design(flexure, title="F", basis="§6.1"),),
            ndp_summary=stripped, issued_on=ISSUED,
        )


def test_a_section_that_checks_nothing_does_not_report_success(designs) -> None:
    """Silence must not read as a green tick."""
    flexure, _, _, _ = designs
    bare = NoteSection(title="Note libre", basis="—", journal=flexure.journal)
    assert bare.passed is None
    assert bare.checks == ()


def test_a_failing_check_makes_the_whole_note_fail(params_fr) -> None:
    under = design_flexure(
        section=RectangularSection(b=Q_(300, "mm"), h=Q_(600, "mm"), d=Q_(550, "mm")),
        concrete=concrete("C30/37"), steel=reinforcement("B500B"),
        M_Ed=Q_(250, "kN*m"), params=params_fr, element="P1",
        A_s_provided=bars_area(3, 16),          # sous-ferraille
    )
    note = CalculationNote(
        project="P", element="P1",
        sections=(section_from_design(under, title="Flexion", basis="§6.1"),),
        ndp_summary=params_fr.summary(), issued_on=ISSUED,
    )
    assert not note.passed
    assert note.max_utilisation > 1.0
    html = render_html(note)
    assert "NE SONT PAS" in html
    # Et la note dit quoi faire, pas seulement que ca ne passe pas.
    assert "Action:" in html


def test_a_result_without_a_journal_cannot_become_a_section() -> None:
    class Bare:
        pass

    with pytest.raises(TypeError, match="ne porte pas de journal"):
        section_from_design(Bare(), title="X", basis="Y")


# ---------------------------------------------------------------------------
# The rendering is self-contained and stable
# ---------------------------------------------------------------------------
def test_the_html_is_self_contained(note) -> None:
    """It must open identically in ten years, offline."""
    html = render_html(note)
    assert "<style>" in html
    for external in ("http://", "https://", "<script", "<link", "@import"):
        assert external not in html, f"la note reference une ressource externe: {external}"


def test_rendering_is_deterministic(note) -> None:
    assert render_html(note) == render_html(note)
    assert render_text(note) == render_text(note)


def test_the_note_serialises_whole(note) -> None:
    import json

    data = note.to_dict()
    assert json.dumps(data, sort_keys=True)
    assert len(data["sections"]) == 4
    assert data["engine_version"] == ENGINE_VERSION
    assert data["notice"] == note.notice
    assert data["unverified_parameters"] == list(note.unverified_parameters)
