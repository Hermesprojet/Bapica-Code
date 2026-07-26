"""The catalogue of official documents still to obtain.

This is the honest half of the pipeline: a precise inventory of what is
missing, per country and per standard, with how to acquire it. None of these
documents is redistributable — National Annexes are paid publications — so the
catalogue records the need rather than the file.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

__all__ = ["CatalogueEntry", "load_catalogue", "missing_documents", "render_catalogue"]

_DATA: Final = Path(__file__).parent / "data" / "catalogue.json"


@dataclass(frozen=True, slots=True)
class CatalogueEntry:
    doc_key: str
    country_code: str
    standard_family: str
    part: str
    reference: str
    title: str
    publisher: str
    how_to_acquire: str
    licence: str
    languages: tuple[str, ...]
    status: str
    parameters_expected: tuple[str, ...]
    notes: str | None = None
    edition: str | None = None

    @property
    def standard(self) -> str:
        return f"{self.standard_family}-{self.part}"

    @property
    def acquired(self) -> bool:
        return self.status != "not_acquired"

    def to_dict(self) -> dict[str, Any]:
        return {
            "doc_key": self.doc_key,
            "country_code": self.country_code,
            "standard": self.standard,
            "reference": self.reference,
            "publisher": self.publisher,
            "how_to_acquire": self.how_to_acquire,
            "licence": self.licence,
            "status": self.status,
            "parameters_expected": list(self.parameters_expected),
            "edition": self.edition,
            "notes": self.notes,
        }


def load_catalogue(path: Path | None = None) -> tuple[CatalogueEntry, ...]:
    raw = json.loads((path or _DATA).read_text(encoding="utf-8"))
    return tuple(
        CatalogueEntry(
            doc_key=d["doc_key"],
            country_code=d["country_code"],
            standard_family=d["standard_family"],
            part=d["part"],
            reference=d["reference"],
            title=d["title"],
            publisher=d["publisher"],
            how_to_acquire=d["acquisition"]["how"],
            licence=d["acquisition"]["licence"],
            languages=tuple(d["acquisition"].get("languages", [])),
            status=d["status"],
            parameters_expected=tuple(d.get("parameters_expected", [])),
            notes=d["acquisition"].get("notes"),
            edition=d.get("edition"),
        )
        for d in raw["documents"]
    )


def missing_documents(
    entries: tuple[CatalogueEntry, ...] | None = None,
) -> tuple[CatalogueEntry, ...]:
    """Documents not yet in hand. What blocks strict mode, precisely."""
    return tuple(e for e in (entries or load_catalogue()) if not e.acquired)


def render_catalogue(entries: tuple[CatalogueEntry, ...] | None = None) -> str:
    entries = entries or load_catalogue()
    missing = missing_documents(entries)
    lines = [
        "=== Documents officiels a obtenir ===",
        f"{len(entries)} document(s) au catalogue, {len(missing)} non acquis.",
        "",
    ]
    for e in entries:
        flag = "MANQUE" if not e.acquired else e.status.upper()
        lines.append(f"[{flag}] {e.doc_key} — {e.reference}")
        lines.append(f"    {e.title}")
        lines.append(f"    Editeur   : {e.publisher}")
        lines.append(f"    Obtention : {e.how_to_acquire}")
        lines.append(f"    Licence   : {e.licence}")
        if e.parameters_expected:
            lines.append(f"    Parametres attendus : {len(e.parameters_expected)}")
        if e.notes:
            lines.append(f"    Note      : {e.notes}")
        lines.append("")
    if missing:
        lines.append(
            "Tant que ces documents ne sont pas depouilles, les parametres "
            "correspondants restent pending_verification et le mode strict "
            "refuse de calculer."
        )
    return "\n".join(lines)
