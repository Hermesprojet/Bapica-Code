"""Rendering of a :class:`~eurostruct_engine.note.document.CalculationNote`.

This module emits markup and computes nothing. It cannot: it imports no design
function, no unit registry arithmetic, no parameter set. Every number it prints
was formatted by the calculation module that produced it, and arrives already
paired with its clause.

That split is what makes interdiction 1 checkable rather than merely stated. A
renderer that could compute could also print a value no journal recorded, and
no reader would be able to tell the difference.

HTML rather than PDF, on purpose
--------------------------------
The engine's dependency audit allows fourteen packages; no PDF stack is among
them, and adding one would put a layout engine inside the calculation core. The
note is therefore emitted as self-contained HTML, which a separate tool turns
into PDF — the same separation as the document importer, and for the same
reason. What matters for defensibility is the *assembly*, and that is here.
"""

from __future__ import annotations

from html import escape
from typing import Iterable

from ..units import fmt
from .document import CalculationNote, NoteSection

__all__ = ["render_html", "render_text"]


_CSS = """
:root { --rule: #d0d0d0; --ink: #1a1a1a; --muted: #5a5a5a; --warn: #8a4b00;
        --fail: #a00000; --pass: #1a6b1a; }
* { box-sizing: border-box; }
body { font: 11pt/1.45 "DejaVu Serif", Georgia, serif; color: var(--ink);
       max-width: 190mm; margin: 0 auto; padding: 12mm; }
h1 { font-size: 16pt; margin: 0 0 2mm; }
h2 { font-size: 13pt; margin: 8mm 0 2mm; border-bottom: 1px solid var(--rule);
     padding-bottom: 1mm; }
h3 { font-size: 11pt; margin: 5mm 0 1mm; color: var(--muted); }
table { border-collapse: collapse; width: 100%; margin: 2mm 0 4mm;
        font-size: 9.5pt; }
th, td { border: 1px solid var(--rule); padding: 1.2mm 2mm; text-align: left;
         vertical-align: top; }
th { background: #f4f4f4; font-weight: 600; }
td.num, th.num { text-align: right; white-space: nowrap; }
td.sym { font-family: "DejaVu Sans Mono", monospace; white-space: nowrap; }
td.clause { font-size: 8.5pt; color: var(--muted); white-space: nowrap; }
.notice { border: 2px solid var(--ink); padding: 4mm; margin: 6mm 0;
          background: #fafafa; }
.warn { color: var(--warn); }
.fail { color: var(--fail); font-weight: 700; }
.pass { color: var(--pass); }
.meta { font-size: 9.5pt; color: var(--muted); }
ul.assump { font-size: 9.5pt; margin: 1mm 0 3mm; padding-left: 5mm; }
@media print { body { padding: 0; } h2 { page-break-after: avoid; }
               table { page-break-inside: avoid; } }
"""


def _q(value) -> str:
    """A quantity as the engine formats it — never re-derived here."""
    return escape(fmt(value))


def _rows(cells: Iterable[str]) -> str:
    return "".join(cells)


def _steps_table(section: NoteSection) -> str:
    head = (
        "<tr><th>Symbole</th><th>Designation</th><th>Formule</th>"
        "<th>Application numerique</th><th class='num'>Valeur</th>"
        "<th>Clause</th></tr>"
    )
    rows = []
    for s in section.steps:
        rows.append(
            "<tr>"
            f"<td class='sym'>{escape(s.symbol)}</td>"
            f"<td>{escape(s.description)}</td>"
            f"<td>{escape(s.latex or '')}</td>"
            f"<td>{escape(s.numeric or '')}</td>"
            f"<td class='num'>{_q(s.value)}</td>"
            f"<td class='clause'>{escape(s.clause.cite() if s.clause else '')}</td>"
            "</tr>"
        )
    return f"<table>{head}{_rows(rows)}</table>"


def _checks_table(section: NoteSection) -> str:
    if not section.checks:
        return ""
    head = (
        "<tr><th>Verification</th><th class='num'>Sollicitation</th>"
        "<th class='num'>Resistance</th><th class='num'>Taux</th>"
        "<th>Statut</th><th>Clause</th></tr>"
    )
    rows = []
    for c in section.checks:
        css = "pass" if c.passed else "fail"
        label = "OK" if c.passed else "NON VERIFIE"
        detail = ""
        if not c.passed and c.remedy:
            detail = (
                f"<tr><td colspan='6' class='warn'>Action: "
                f"{escape(c.remedy)}</td></tr>"
            )
        rows.append(
            "<tr>"
            f"<td>{escape(c.name)}</td>"
            f"<td class='num'>{_q(c.acting)}</td>"
            f"<td class='num'>{_q(c.resisting)}</td>"
            f"<td class='num'>{c.utilisation:.3f}</td>"
            f"<td class='{css}'>{label}</td>"
            f"<td class='clause'>{escape(c.clause.cite())}</td>"
            "</tr>" + detail
        )
    return f"<h3>Verifications</h3><table>{head}{_rows(rows)}</table>"


def _section_html(section: NoteSection, index: int) -> str:
    parts = [f"<h2>{index}. {escape(section.title)}</h2>",
             f"<p class='meta'>Base normative : {escape(section.basis)}</p>"]
    if section.assumptions:
        items = "".join(f"<li>{escape(a)}</li>" for a in section.assumptions)
        parts.append(f"<h3>Hypotheses</h3><ul class='assump'>{items}</ul>")
    parts.append("<h3>Deroulement du calcul</h3>")
    parts.append(_steps_table(section))
    parts.append(_checks_table(section))
    return "".join(parts)


def _referential_html(note: CalculationNote) -> str:
    ndp = note.ndp_summary
    fw = ndp.get("regulatory_framework", {})
    rows = [
        "<tr><th>Pays</th><td>"
        f"{escape(str(ndp.get('country_name') or ndp.get('country', '')))}</td></tr>",
        f"<tr><th>Date de reference</th><td>{escape(str(ndp.get('as_of','')))}</td></tr>",
        "<tr><th>Reference opposable</th><td>"
        f"{escape(str(fw.get('binding_reference','')))}</td></tr>",
        "<tr><th>Statut des Eurocodes</th><td>"
        f"{escape(str(fw.get('eurocode_status','')))}</td></tr>",
        "<tr><th>Regime de verification</th><td>"
        f"{escape(str(fw.get('verification_regime','')))}</td></tr>",
        f"<tr><th>Version du moteur</th><td>{escape(note.engine_version)}</td></tr>",
    ]
    annexes = ndp.get("annexes", [])
    if annexes:
        lines = "<br>".join(
            f"{escape(str(a.get('reference','')))} — {escape(str(a.get('edition','')))}"
            for a in annexes
        )
        rows.append(f"<tr><th>Annexes Nationales</th><td>{lines}</td></tr>")

    html = [f"<h2>Referentiel applique</h2><table>{_rows(rows)}</table>"]

    unverified = note.unverified_parameters
    if unverified:
        listed = ", ".join(escape(k) for k in unverified)
        html.append(
            "<p class='warn'><strong>Parametres nationaux non releves "
            f"({len(unverified)})</strong> : {listed}.<br>"
            "Ces valeurs n'ont pas ete relevees dans l'Annexe Nationale "
            "publiee par un ingenieur. Elles proviennent de la recommandation "
            "de l'Eurocode ou d'une lecture non confirmee. La presente note "
            "ne peut pas etre emise en l'etat pour un ouvrage.</p>"
        )
    return "".join(html)


def render_html(note: CalculationNote) -> str:
    """The note as a self-contained HTML document.

    Self-contained on purpose: no external stylesheet, no font download, no
    script. A note de calcul has to open identically in ten years, on a machine
    that has never heard of this project.
    """
    status = (
        "<span class='pass'>Toutes les verifications sont satisfaites</span>"
        if note.passed else
        "<span class='fail'>UNE OU PLUSIEURS VERIFICATIONS NE SONT PAS "
        "SATISFAITES</span>"
    )
    body = [
        "<!DOCTYPE html><html lang='fr'><head><meta charset='utf-8'>",
        f"<title>Note de calcul — {escape(note.element)}</title>",
        f"<style>{_CSS}</style></head><body>",
        f"<h1>Note de calcul — {escape(note.element)}</h1>",
        f"<p class='meta'>Projet : {escape(note.project)} &middot; "
        f"Emise le {note.issued_on.isoformat()} &middot; "
        f"eurostruct-engine {escape(note.engine_version)}</p>",
        f"<p>{status} &middot; taux maximal {note.max_utilisation:.3f}</p>",
        # The notice comes FIRST, before any result. A reader who stops at the
        # first page must still have read it.
        f"<div class='notice'><strong>{escape(note.notice)}</strong>"
        f"<p class='meta'>{escape(note.software_role)}</p></div>",
    ]
    for i, section in enumerate(note.sections, start=1):
        body.append(_section_html(section, i))

    body.append(_referential_html(note))

    if note.remarks:
        items = "".join(f"<li>{escape(r)}</li>" for r in note.remarks)
        body.append(f"<h2>Observations</h2><ul>{items}</ul>")

    clauses = note.clauses()
    if clauses:
        items = "".join(f"<li>{escape(c)}</li>" for c in clauses)
        body.append(
            f"<h2>Clauses citees ({len(clauses)})</h2><ul class='assump'>{items}</ul>"
        )

    body.append("</body></html>")
    return "".join(body)


def render_text(note: CalculationNote) -> str:
    """A plain-text rendering, for a terminal or a diff.

    Same rule as the HTML: every value comes from a journal entry.
    """
    out = [
        f"NOTE DE CALCUL — {note.element}",
        f"Projet: {note.project}   Emise le {note.issued_on.isoformat()}",
        f"eurostruct-engine {note.engine_version}",
        "",
        note.notice,
        "",
    ]
    for i, section in enumerate(note.sections, start=1):
        out += [f"{i}. {section.title.upper()}", f"   Base: {section.basis}"]
        for a in section.assumptions:
            out.append(f"   Hypothese: {a}")
        out.append("")
        for s in section.steps:
            clause = f"  [{s.clause.cite()}]" if s.clause else ""
            out.append(f"   {s.symbol:<28} = {fmt(s.value):>16}{clause}")
        for c in section.checks:
            flag = "OK " if c.passed else "NON"
            out.append(
                f"   {flag} {c.name:<44} taux {c.utilisation:.3f}  "
                f"[{c.clause.cite()}]"
            )
        out.append("")

    unverified = note.unverified_parameters
    if unverified:
        out += [
            f"PARAMETRES NON RELEVES ({len(unverified)}):",
            *(f"   - {k}" for k in unverified),
            "",
        ]
    return "\n".join(out)
