"""Assembly and rendering of the note de calcul.

Split deliberately: :mod:`document` builds the note from journals and knows no
markup; :mod:`render` emits markup and knows no arithmetic. Neither can invent
a number, because neither computes one.
"""

from __future__ import annotations

from .document import CalculationNote, NoteSection, section_from_design
from .render import render_html, render_text

__all__ = [
    "NoteSection",
    "CalculationNote",
    "section_from_design",
    "render_html",
    "render_text",
]
