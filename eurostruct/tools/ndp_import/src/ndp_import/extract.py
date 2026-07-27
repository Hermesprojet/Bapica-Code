"""PDF -> extraction candidates.

The extractor reads a deposited National Annex and proposes, for each parameter
the catalogue expects from that document, one candidate per plausible reading —
with the page, the surrounding text and a confidence score.

It never decides. Three behaviours make that concrete:

* a parameter it cannot find is listed in ``not_found``, never defaulted;
* a clause it finds but cannot read a number from yields a candidate with
  ``parsed_value=None`` — which still tells the reviewer where to look;
* a value outside the plausible range is *kept*, with low confidence. Silently
  dropping it would hide a National Annex that genuinely departs from the
  Eurocode recommendation, which is the whole point of reading the annex.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

import pdfplumber

from .model import EXTRACTOR_VERSION, ExtractionCandidate, ExtractionRun, SourceDocument
from .patterns import NUMBER_RE, ParameterPattern, parse_number, patterns_for

__all__ = ["extract_document", "extract_from_pages", "PageText", "read_pages"]

#: Characters of context kept around a match, for the reviewer to judge on.
_WINDOW = 320

#: Clause and table references, so their digits are not offered as values.
#: "3.1.6(1)P" · "2.4.2.4(1)" · "9.1N" · "Tableau 2.1N" · "eq. (6.8)"
_CLAUSE_LIKE = re.compile(
    r"""
    (?:§\s*)?\d+(?:\.\d+){1,4}(?:\s*\(\d+\))?P?      # 3.1.6(1)P
  | \b\d+\.\d+N\b                                    # 9.1N
  | \b(?:Tableau|Table|Tabelle|Tabla|Fig(?:ure)?|Abb|Anexo|Annexe|Annex)\s*[\w.]+
  | \([\d.]+\)                                       # (6.8)
    """,
    re.VERBOSE | re.IGNORECASE,
)


def _mask_references(text: str) -> str:
    """Blank out clause and table references before reading numbers.

    Without this, "Clause 2.4.2.4(1)" offers 2.4 and 2.4 as candidate values
    and buries the real one. Replaced by spaces rather than removed so the
    snippet the reviewer sees keeps its offsets.
    """
    return _CLAUSE_LIKE.sub(lambda m: " " * len(m.group(0)), text)


@dataclass(frozen=True, slots=True)
class PageText:
    number: int          # 1-based
    text: str
    #: "native" for a real text layer, "ocr" for machine-recognised characters.
    #: Carried through to every candidate, because a reviewer must know whether
    #: a digit was typeset or guessed.
    source: str = "native"


def read_pages(pdf_path: Path) -> list[PageText]:
    """Extract the text of every page, keeping page numbers.

    Kept separate from the matching so a scanned annex — which yields empty
    text — is diagnosed as "no text layer" rather than as "parameter absent".
    """
    pages: list[PageText] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            pages.append(PageText(number=i, text=page.extract_text() or ""))
    return pages


def _normalise(text: str) -> str:
    """Collapse whitespace so a clause split across lines still matches."""
    return re.sub(r"[ \t ]+", " ", text.replace("\n", " "))


def _candidate_id(doc_id: str, name: str, page: int, offset: int, token: str) -> str:
    raw = f"{doc_id}:{name}:{page}:{offset}:{token}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _score(
    pattern: ParameterPattern,
    value: float | None,
    clause_hit: bool,
    symbol_hit: bool,
    numbers_in_window: int,
    text_source: str = "native",
) -> float:
    """Order the review queue. Informational only — never a gate.

    Deliberately conservative: the ceiling is 0,9. Nothing this extractor
    produces is ever "certain enough" to skip a human.
    """
    #: Recognised characters are a guess. Cap them well below native text so an
    #: OCR reading never rises to the top of the queue as if it were certain.
    ceiling = 0.9 if text_source == "native" else 0.6
    score = 0.0
    if clause_hit:
        score += 0.45
    if symbol_hit:
        score += 0.25
    if value is not None:
        score += 0.10
        if numbers_in_window == 1:
            score += 0.10          # unambiguous reading
        if pattern.plausible and pattern.plausible[0] <= value <= pattern.plausible[1]:
            score += 0.10
    return round(min(score, ceiling), 3)


def _windows(text: str, regex: re.Pattern[str]) -> Iterable[tuple[int, str]]:
    for m in regex.finditer(text):
        start = max(0, m.start() - _WINDOW // 2)
        yield m.start(), text[start : m.end() + _WINDOW // 2]


def extract_document(
    doc: SourceDocument,
    pdf_path: Path,
    parameters: Sequence[str] | None = None,
) -> ExtractionRun:
    """Read *pdf_path* and propose candidates for *parameters*.

    :param doc: the declared metadata. Its ``doc_id`` must be the digest of
        ``pdf_path`` — checked here, because a candidate attached to the wrong
        document is worse than no candidate.
    :param parameters: names to look for; all known patterns when omitted.
    :raises ValueError: on a digest mismatch, or when the PDF has no text
        layer (a scanned annex needs OCR before it can be read).
    """
    actual = SourceDocument.digest(pdf_path)
    if actual != doc.doc_id:
        raise ValueError(
            f"empreinte du fichier ({actual[:16]}...) differente de celle "
            f"declaree ({doc.doc_id[:16]}...). Le document depose n'est pas "
            "celui enregistre: re-deposer avant d'extraire."
        )

    pages = read_pages(pdf_path)
    if not any(p.text.strip() for p in pages):
        raise ValueError(
            f"aucune couche de texte dans {pdf_path.name}: le document est "
            "probablement numerise. Le passer par une ROC avant extraction. "
            "L'extracteur ne devine pas le contenu d'une image."
        )

    return extract_from_pages(doc, pages, parameters)


def extract_from_pages(
    doc: SourceDocument,
    pages: Sequence[PageText],
    parameters: Sequence[str] | None = None,
) -> ExtractionRun:
    """Propose candidates from already-extracted page text.

    Separate entry point so a scanned annex can be run through OCR first and
    fed in here. Candidates from recognised text keep ``source="ocr"`` and a
    lower confidence ceiling: the characters were guessed by a machine, and the
    reviewer has to see that before accepting a digit.
    """
    wanted = patterns_for(tuple(parameters) if parameters else None)
    candidates: list[ExtractionCandidate] = []
    found: set[str] = set()

    for pattern in wanted:
        clause_re = pattern.clause_regex()
        symbol_re = pattern.symbol_regex()

        for page in pages:
            text = _normalise(page.text)
            if not text:
                continue

            anchors = list(_windows(text, clause_re))
            clause_hit = bool(anchors)
            if not anchors and symbol_re is not None:
                anchors = list(_windows(text, symbol_re))

            for offset, window in anchors:
                symbol_hit = bool(symbol_re and symbol_re.search(window))
                tokens = NUMBER_RE.findall(_mask_references(window))
                pid = f"{pattern.parameter_name}@clause/{page.source}"

                if not tokens:
                    candidates.append(
                        ExtractionCandidate(
                            candidate_id=_candidate_id(
                                doc.doc_id, pattern.parameter_name, page.number,
                                offset, "",
                            ),
                            doc_id=doc.doc_id,
                            parameter_name=pattern.parameter_name,
                            page=page.number, snippet=window.strip(),
                            raw_value=None, parsed_value=None, unit=pattern.unit,
                            clause=pattern.clause_refs[0], pattern_id=pid,
                            confidence=_score(
                                pattern, None, clause_hit, symbol_hit, 0, page.source
                            ),
                        )
                    )
                    found.add(pattern.parameter_name)
                    continue

                for token in tokens:
                    value = parse_number(token)
                    candidates.append(
                        ExtractionCandidate(
                            candidate_id=_candidate_id(
                                doc.doc_id, pattern.parameter_name, page.number,
                                offset, token,
                            ),
                            doc_id=doc.doc_id,
                            parameter_name=pattern.parameter_name,
                            page=page.number, snippet=window.strip(),
                            raw_value=token, parsed_value=value, unit=pattern.unit,
                            clause=pattern.clause_refs[0], pattern_id=pid,
                            confidence=_score(
                                pattern, value, clause_hit, symbol_hit,
                                len(tokens), page.source,
                            ),
                        )
                    )
                    found.add(pattern.parameter_name)

    not_found = tuple(
        sorted(p.parameter_name for p in wanted if p.parameter_name not in found)
    )
    candidates.sort(key=lambda c: (c.parameter_name, c.page, -c.confidence, c.candidate_id))

    return ExtractionRun(
        doc=doc,
        candidates=tuple(candidates),
        run_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        extractor_version=EXTRACTOR_VERSION,
        not_found=not_found,
    )
