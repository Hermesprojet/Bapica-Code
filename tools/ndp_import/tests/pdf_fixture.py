"""Build a minimal, valid PDF from text lines — for testing the extractor.

Written by hand rather than pulling in a PDF *writer*: the importer already
depends on a parser, and a test fixture is a poor reason to add a second
library. The output is a real PDF with a real text layer, which is what the
extractor needs to be exercised honestly.

The content is invented *test* text. It is never National Annex content: no
value produced here may reach the engine's dataset.
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence


def _escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def make_pdf(path: Path, pages: Sequence[Sequence[str]]) -> Path:
    """Write a PDF where each element of *pages* is a list of text lines."""
    objects: list[bytes] = []

    n_pages = len(pages)
    # 1 catalog, 2 pages tree, then per page: page object + content stream,
    # and finally the font.
    page_ids = [3 + 2 * i for i in range(n_pages)]
    content_ids = [4 + 2 * i for i in range(n_pages)]
    font_id = 3 + 2 * n_pages

    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects.append(
        f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode("latin-1")
    )

    for i, lines in enumerate(pages):
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
                f"/Contents {content_ids[i]} 0 R "
                f"/Resources << /Font << /F1 {font_id} 0 R >> >> >>"
            ).encode("latin-1")
        )
        body = ["BT", "/F1 10 Tf", "50 800 Td", "12 TL"]
        for line in lines:
            body.append(f"({_escape(line)}) Tj")
            body.append("T*")
        body.append("ET")
        stream = "\n".join(body).encode("latin-1", errors="replace")
        objects.append(
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n"
            + stream + b"\nendstream"
        )

    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"

    xref_at = len(out)
    count = len(objects) + 1
    out += f"xref\n0 {count}\n".encode()
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {count} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n"
    ).encode()

    path.write_bytes(bytes(out))
    return path
