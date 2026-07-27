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
    #: Roadmap phase that needs this document — P0 blocks today.
    phase: str = "?"
    #: national_annex | national_regulation
    document_role: str = "national_annex"
    #: sha256 of the file actually held. Ties "acquired" to a specific file,
    #: and lets a re-deposit of the same bytes be recognised as such.
    doc_id_sha256: str | None = None
    #: Digests of other renderings of the same document (a scan beside the
    #: text version). Held too, so re-depositing one is equally pointless.
    alternate_copy_hashes: tuple[str, ...] = ()

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
            "phase": self.phase,
            "document_role": self.document_role,
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
            phase=d.get("phase", "?"),
            document_role=d.get("document_role", "national_annex"),
            doc_id_sha256=d.get("doc_id_sha256"),
            alternate_copy_hashes=tuple(
                c["doc_id_sha256"] for c in d.get("alternate_copies", [])
            ),
        )
        for d in raw["documents"]
    )


def missing_documents(
    entries: tuple[CatalogueEntry, ...] | None = None,
) -> tuple[CatalogueEntry, ...]:
    """Documents not yet in hand. What blocks strict mode, precisely."""
    return tuple(e for e in (entries or load_catalogue()) if not e.acquired)


def render_catalogue(entries: tuple[CatalogueEntry, ...] | None = None) -> str:
    """Group by country, then by roadmap phase: what to buy, and when."""
    entries = entries or load_catalogue()
    raw = json.loads(_DATA.read_text(encoding="utf-8"))
    labels = raw.get("phases", {})
    order = ["P0", "P1", "FEU", "P2", "P3", "P4", "P6"]

    free = [e for e in entries if "gratuit" in e.how_to_acquire.lower()]
    held = [e for e in entries if e.acquired]
    lines = [
        "=== Documents officiels a obtenir, par pays ===",
        f"{len(entries)} documents, dont {len(free)} librement telechargeables "
        f"et {len(entries) - len(free)} payants.",
        f"{len(held)} deja en main, {len(entries) - len(held)} a obtenir.",
        "",
    ]
    for cc in ("BE", "FR", "ES", "DE"):
        country = [e for e in entries if e.country_code == cc]
        if not country:
            continue
        lines.append(f"--- {cc} " + "-" * 66)
        for phase in order:
            group = [e for e in country if e.phase == phase]
            if not group:
                continue
            lines.append(f"  {labels.get(phase, phase)}")
            for e in group:
                cost = "gratuit" if "gratuit" in e.how_to_acquire.lower() else "payant"
                params = (
                    f"  [{len(e.parameters_expected)} parametres]"
                    if e.parameters_expected else ""
                )
                # Marque ce qui est en main. Sans elle, ce rapport annoncait
                # comme « a obtenir » des documents deja lus.
                mark = "[EN MAIN] " if e.acquired else "          "
                lines.append(f"    {mark}{e.reference:<44} {cost:<8}{params}")
            lines.append("")

    if held:
        lines.append(
            f"{len(held)} document(s) EN MAIN. Les detenir ne confirme AUCUNE "
            "valeur: seule la decision nominative d'un ingenieur habilite fait "
            "passer un parametre en 'confirmed'. Le mode strict reste bloque."
        )
    else:
        lines.append(
            "Aucun de ces documents n'est acquis. Tant qu'ils ne sont pas "
            "depouilles, les parametres restent pending_verification et le mode "
            "strict refuse de calculer."
        )
    return "\n".join(lines)
