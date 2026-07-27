"""Triage of deposited documents: what is each one, and can it be used?

Before extracting anything, a batch of PDFs has to be sorted. Three questions,
in order, and a document must pass all three:

1. **Is it machine-readable?** A scanned annex has no text layer and needs OCR.
2. **What is it, normatively?** A base Eurocode — even adopted as NF EN or
   registered as NBN EN — carries the Eurocode's *recommended* values. Only a
   National Annex fixes what a country adopted. This is interdiction 2, and it
   is where a filename lies most often: "NBN EN 1991-1-1" and
   "NBN EN 1991-1-1 ANB" are two different documents.
3. **Does it cover a standard the engine needs?** An annex to EN 1991-2 is a
   real annex and still unblocks nothing if the engine's pending parameters all
   belong to EN 1992-1-1.

The classification below is a *proposal*, derived from the document's own front
matter. It is offered to the depositing engineer, who declares the truth — the
same rule as everywhere else in this pipeline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import pdfplumber

from .model import DocumentRole

__all__ = ["TriageResult", "triage_document", "triage_batch", "render_triage"]

#: A National Annex names itself. These markers appear in the title block.
_ANNEX_MARKERS = re.compile(
    r"\bANB\b|\bNA\b(?!\w)|annexe\s+nationale|nationale\s+bijlage|"
    r"anexo\s+nacional|nationaler\s+anhang|national\s+annex",
    re.IGNORECASE,
)

#: National regulation outside the Eurocode system. It *can* fix requirements
#: (Belgian Arrete Royal on fire, Spanish Codigo Estructural, German MVV TB),
#: so it must not be lumped in with the base Eurocodes.
_REGULATION_MARKERS = re.compile(
    r"arrete\s+royal|koninklijk\s+besluit|moniteur\s+belge|"
    r"real\s+decreto|codigo\s+estructural|codigo\s+tecnico|\bCTE\b|\bNCSE\b|"
    r"\bMVV\s*TB\b|verwaltungsvorschrift|\bDIN\s*1054\b|\bDTU\b|"
    r"\bNBN\s*S\s*\d|normes?\s+de\s+base",
    re.IGNORECASE,
)

#: Guidance and articles, never a source of an enforceable value.
_SECONDARY_MARKERS = re.compile(
    r"\bCSTC\b|\bWTCB\b|\bJRC\b|\bCSTB\b|magazine|\bnotes?\s+d[eu]\s+information\b",
    re.IGNORECASE,
)

_STANDARD_RE = re.compile(
    r"\bEN\s*(\d{4})(?:\s*[-–]\s*(\d(?:\s*[-–]\s*\d)?))?\b", re.IGNORECASE
)


def _searchable(*parts: str) -> str:
    """Normalise a haystack before matching.

    Underscores are word characters in a regex, so ``\bANB\b`` does not match
    inside ``NBN_EN_1990__ANB``. Filenames use them constantly, and getting
    this wrong classified two genuine National Annexes as base Eurocodes.
    """
    return re.sub(r"[_\-]+", " ", " ".join(parts))


@dataclass(frozen=True, slots=True)
class TriageResult:
    """What a deposited file appears to be, and whether it can be used."""

    path: Path
    doc_id: str
    page_count: int
    text_chars: int
    proposed_role: DocumentRole
    proposed_standard: str | None
    front_matter: str
    blockers: tuple[str, ...]

    @property
    def machine_readable(self) -> bool:
        return self.text_chars > 0

    @property
    def usable_for_ndp(self) -> bool:
        """Can this document yield a *national* parameter at all?"""
        return self.machine_readable and self.proposed_role.can_fix_national_parameters

    def to_dict(self) -> dict[str, Any]:
        return {
            "filename": self.path.name,
            "doc_id": self.doc_id,
            "page_count": self.page_count,
            "text_chars": self.text_chars,
            "machine_readable": self.machine_readable,
            "proposed_role": self.proposed_role.value,
            "proposed_standard": self.proposed_standard,
            "usable_for_ndp": self.usable_for_ndp,
            "blockers": list(self.blockers),
        }


def _classify(front: str, filename: str) -> DocumentRole:
    hay = _searchable(front, filename)
    if _SECONDARY_MARKERS.search(hay):
        return DocumentRole.SECONDARY_PUBLICATION
    if _ANNEX_MARKERS.search(hay):
        return DocumentRole.NATIONAL_ANNEX
    if _REGULATION_MARKERS.search(hay):
        return DocumentRole.NATIONAL_REGULATION
    return DocumentRole.BASE_EUROCODE


def _standard_of(front: str, filename: str) -> str | None:
    """Best guess at which standard the document covers.

    Handles both ``EN 1992-1-1`` and a part-less ``EN 1990``. From a filename
    the separators have already been flattened, so ``EN_199111`` cannot be
    split reliably — that case falls back to the front matter, and failing that
    to ``None`` rather than to a wrong part number.
    """
    for hay in (front, _searchable(filename)):
        m = _STANDARD_RE.search(hay)
        if m:
            if m.group(2):
                part = re.sub(r"\s*[-–]\s*", "-", m.group(2)).strip()
                return f"EN {m.group(1)}-{part}"
            return f"EN {m.group(1)}"
    return None


def triage_document(path: Path, needed_standards: Sequence[str] = ()) -> TriageResult:
    """Classify one deposited file."""
    from .model import SourceDocument

    with pdfplumber.open(str(path)) as pdf:
        pages = [(p.extract_text() or "") for p in pdf.pages]
    text = "".join(pages)
    front = " ".join((pages[0] if pages else "").split())[:400]

    role = _classify(front, path.name)
    standard = _standard_of(front, path.name)

    blockers: list[str] = []
    if not text.strip():
        blockers.append(
            "aucune couche de texte: document numerise, une ROC est necessaire "
            "avant tout depouillement automatique"
        )
    if role is DocumentRole.BASE_EUROCODE:
        blockers.append(
            "Eurocode de base (meme homologue NF ou enregistre NBN): il porte "
            "les valeurs RECOMMANDEES, pas les valeurs nationales. Il ne peut "
            "pas fixer un NDP"
        )
    if role is DocumentRole.SECONDARY_PUBLICATION:
        blockers.append(
            "publication secondaire (article, guide): utile au relecteur, "
            "jamais source d'une valeur opposable"
        )
    if needed_standards and standard and standard not in needed_standards:
        blockers.append(
            f"porte sur {standard}, hors des normes dont le moteur a besoin "
            f"({', '.join(needed_standards)})"
        )

    return TriageResult(
        path=path,
        doc_id=SourceDocument.digest(path),
        page_count=len(pages),
        text_chars=len(text),
        proposed_role=role,
        proposed_standard=standard,
        front_matter=front,
        blockers=tuple(blockers),
    )


def triage_batch(
    paths: Iterable[Path], needed_standards: Sequence[str] = ()
) -> list[TriageResult]:
    return sorted(
        (triage_document(p, needed_standards) for p in paths),
        key=lambda r: (not r.usable_for_ndp, r.path.name),
    )


def render_triage(results: Sequence[TriageResult]) -> str:
    usable = [r for r in results if r.usable_for_ndp]
    scanned = [r for r in results if not r.machine_readable]

    lines = [
        "=== Triage des documents deposes ===",
        f"{len(results)} document(s): {len(usable)} exploitable(s) pour un "
        f"parametre national, {len(scanned)} numerise(s).",
        "",
    ]
    for r in results:
        mark = "OK    " if r.usable_for_ndp else "REJET "
        std = r.proposed_standard or "norme non identifiee"
        lines.append(
            f"[{mark}] {r.path.name[:44]:<46} {r.page_count:>3}p  "
            f"{r.proposed_role.value:<22} {std}"
        )
        for b in r.blockers:
            lines.append(f"           - {b}")
    lines.append("")

    if scanned:
        lines.append(
            f"{len(scanned)} document(s) numerise(s) — a passer par une ROC "
            "avant depouillement:"
        )
        for r in scanned:
            lines.append(f"    - {r.path.name} ({r.page_count} pages)")
        lines.append("")

    if usable:
        lines.append("Annexes Nationales exploitables en l'etat:")
        for r in usable:
            lines.append(
                f"    - {r.path.name} — {r.proposed_standard or '?'} "
                f"({r.text_chars} caracteres)"
            )
    else:
        lines.append(
            "AUCUN de ces documents ne peut fixer un parametre national en "
            "l'etat. Le mode strict reste bloque."
        )
    lines.append("")
    lines.append(
        "Le role propose ci-dessus est une LECTURE de la page de garde. "
        "L'ingenieur qui depose declare le role reel: un nom de fichier "
        "portant « NBN » ne fait pas d'un document une ANB."
    )
    return "\n".join(lines)
