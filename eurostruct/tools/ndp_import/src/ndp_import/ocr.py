"""OCR stage: make a scanned National Annex machine-readable.

Six of the Belgian annexes deposited so far are scans — pages of images with no
text layer. Without OCR they cannot be read at all; with careless OCR they are
worse than unreadable, because a misrecognised digit in a normative value looks
exactly like a correct one.

Three precautions, all of them consequences of that risk:

1. **The original file is never modified.** OCR writes a *sidecar* text file.
   The document's ``doc_id`` stays the sha256 of the original PDF, so the
   provenance chain still points at the document the engineer holds.

2. **OCR text is labelled as OCR, all the way to the reviewer.** A candidate
   read from recognised text carries ``text_source="ocr"`` and its confidence
   is capped well below one read from a native text layer. The review queue
   shows it, so nobody accepts a value without knowing a machine guessed the
   characters.

3. **Per-page recognition confidence is recorded.** A page Tesseract found
   hard is flagged, because that is where a wrong digit hides.

None of this makes OCR trustworthy. It makes it *auditable*: the reviewer still
reads the value off the page, and the value still cannot become ``confirmed``
without their name and the page number.

What OCR actually delivers, measured
------------------------------------
Run against NBN EN 1992-1-1 ANB (34 scanned pages, 90 % mean word confidence),
the outcome was unambiguous and worth recording:

* **Navigation: excellent.** Clause headings came through cleanly, so the
  extractor located §2.4.2.4(1) on p. 7, §5.5(4) on p. 14, §9.2.1.1(1) on
  p. 21, §9.5.2(3) on p. 23. A 34-page scan became a precise page index.

* **Numeric values in tables: unusable.** Table 2.1N was recognised as
  "Ye Ys y beton acier ... 2 s . 1," — the partial factors were destroyed.
  Worse, plausible-looking wrong numbers appeared: gamma_C came back as
  *1992*, read from the header "NBN EN 1992-1-1 ANB:2010"; As_min_coeff came
  back as *2*, read from "NOTE 2".

The conclusion is not that the OCR settings need tuning. It is that a
recognised digit in a normative table is not evidence, at any confidence. So
the pipeline uses OCR for what it is good at — telling an engineer which page
to open — and leaves reading the value to the engineer. The 0,6 confidence
ceiling and the ``text_source="ocr"`` label exist to keep that boundary
visible in the review queue.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

__all__ = ["OcrPage", "OcrResult", "ocr_available", "ocr_document", "load_sidecar"]

#: Rendering resolution. 300 dpi is the usual floor for reliable small-text
#: recognition; below it, subscripts in symbols like gamma_C start to blur.
DEFAULT_DPI = 300

#: Belgian annexes are bilingual, so both languages are fed to Tesseract.
DEFAULT_LANG = "fra+nld"

#: A page recognised below this mean confidence is flagged for closer reading.
LOW_CONFIDENCE = 80.0


@dataclass(frozen=True, slots=True)
class OcrPage:
    number: int
    text: str
    #: Mean per-word confidence reported by Tesseract, 0-100.
    mean_confidence: float
    word_count: int

    @property
    def low_confidence(self) -> bool:
        return self.mean_confidence < LOW_CONFIDENCE

    def to_dict(self) -> dict[str, Any]:
        return {
            "number": self.number,
            "text": self.text,
            "mean_confidence": self.mean_confidence,
            "word_count": self.word_count,
            "low_confidence": self.low_confidence,
        }


@dataclass(frozen=True, slots=True)
class OcrResult:
    """Recognised text for one document, kept beside the untouched original."""

    #: sha256 of the ORIGINAL pdf — unchanged by OCR.
    doc_id: str
    source_filename: str
    pages: tuple[OcrPage, ...]
    language: str
    dpi: int
    engine: str
    run_at: str

    @property
    def mean_confidence(self) -> float:
        pages = [p for p in self.pages if p.word_count]
        if not pages:
            return 0.0
        total = sum(p.mean_confidence * p.word_count for p in pages)
        words = sum(p.word_count for p in pages)
        return round(total / words, 2)

    def low_confidence_pages(self) -> tuple[int, ...]:
        return tuple(p.number for p in self.pages if p.low_confidence)

    def to_dict(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "source_filename": self.source_filename,
            "language": self.language,
            "dpi": self.dpi,
            "engine": self.engine,
            "run_at": self.run_at,
            "mean_confidence": self.mean_confidence,
            "low_confidence_pages": list(self.low_confidence_pages()),
            "pages": [p.to_dict() for p in self.pages],
        }

    def render(self) -> str:
        lines = [
            f"=== ROC: {self.source_filename} ===",
            f"{len(self.pages)} pages, {self.language}, {self.dpi} dpi, "
            f"{self.engine}",
            f"Confiance moyenne: {self.mean_confidence:.1f} / 100",
        ]
        low = self.low_confidence_pages()
        if low:
            lines.append(
                f"Pages sous {LOW_CONFIDENCE:.0f} de confiance, a relire de pres: "
                + ", ".join(str(p) for p in low)
            )
        lines.append(
            "\nLe texte reconnu est une LECTURE MACHINE des images. Toute valeur "
            "qui en sortira portera text_source='ocr' et une confiance plafonnee: "
            "le relecteur doit verifier le chiffre sur la page, pas sur le texte."
        )
        return "\n".join(lines)


def ocr_available() -> bool:
    """Whether Tesseract and a PDF rasteriser are installed."""
    if shutil.which("tesseract") is None:
        return False
    try:
        import pypdfium2  # noqa: F401
        import pytesseract  # noqa: F401
    except ImportError:
        return False
    return True


def ocr_document(
    pdf_path: Path,
    doc_id: str,
    language: str = DEFAULT_LANG,
    dpi: int = DEFAULT_DPI,
    pages: Sequence[int] | None = None,
) -> OcrResult:
    """Recognise the text of a scanned PDF, without touching the original.

    :param doc_id: sha256 of *pdf_path*, checked here so a sidecar can never be
        attached to a different file than the one it was produced from.
    :param pages: 1-based page numbers to process; all pages when omitted.
    :raises RuntimeError: if the OCR toolchain is not installed.
    :raises ValueError: on a digest mismatch.
    """
    if not ocr_available():
        raise RuntimeError(
            "chaine ROC absente. Installer tesseract-ocr (avec les paquets de "
            "langue voulus) et les modules pypdfium2 et pytesseract."
        )

    import pypdfium2 as pdfium
    import pytesseract
    from pytesseract import Output

    from .model import SourceDocument

    actual = SourceDocument.digest(pdf_path)
    if actual != doc_id:
        raise ValueError(
            f"empreinte du fichier ({actual[:16]}...) differente de celle "
            f"declaree ({doc_id[:16]}...). La ROC porterait sur un autre "
            "document que celui enregistre."
        )

    scale = dpi / 72.0
    out: list[OcrPage] = []
    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        wanted = pages or range(1, len(pdf) + 1)
        for number in wanted:
            image = pdf[number - 1].render(scale=scale).to_pil()
            data = pytesseract.image_to_data(
                image, lang=language, output_type=Output.DICT
            )
            words: list[str] = []
            confs: list[float] = []
            for text, conf in zip(data["text"], data["conf"], strict=True):
                if not text.strip():
                    continue
                words.append(text)
                try:
                    c = float(conf)
                except (TypeError, ValueError):
                    continue
                if c >= 0:                     # -1 marks a non-text block
                    confs.append(c)
            out.append(
                OcrPage(
                    number=number,
                    text=pytesseract.image_to_string(image, lang=language),
                    mean_confidence=round(sum(confs) / len(confs), 2) if confs else 0.0,
                    word_count=len(words),
                )
            )
    finally:
        pdf.close()

    return OcrResult(
        doc_id=doc_id,
        source_filename=pdf_path.name,
        pages=tuple(out),
        language=language,
        dpi=dpi,
        engine=f"tesseract {pytesseract.get_tesseract_version()}",
        run_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def write_sidecar(result: OcrResult, path: Path) -> Path:
    path.write_text(
        json.dumps(result.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def load_sidecar(path: Path) -> OcrResult:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return OcrResult(
        doc_id=raw["doc_id"],
        source_filename=raw["source_filename"],
        pages=tuple(
            OcrPage(
                number=p["number"], text=p["text"],
                mean_confidence=p["mean_confidence"], word_count=p["word_count"],
            )
            for p in raw["pages"]
        ),
        language=raw["language"], dpi=raw["dpi"], engine=raw["engine"],
        run_at=raw["run_at"],
    )
