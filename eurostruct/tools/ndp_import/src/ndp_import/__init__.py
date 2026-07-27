"""National Annex documentary import pipeline.

Separate from ``eurostruct_engine`` on purpose: it depends on a PDF parser,
which the engine's dependency audit refuses. The two exchange JSON and never
share a process.

    catalogue  -> what official documents are needed, and how to obtain them
    extract    -> deposited PDF -> extraction candidates (proposals only)
    review     -> human verification -> confirmed records with full evidence
"""

from __future__ import annotations

from .catalogue import (
    CatalogueEntry,
    load_catalogue,
    missing_documents,
    render_catalogue,
)
from .extract import extract_document, read_pages
from .model import (
    EXTRACTOR_VERSION,
    DocumentRole,
    DocumentStatus,
    ExtractionCandidate,
    ExtractionRun,
    ReviewDecision,
    ReviewedParameter,
    ReviewOutcome,
    SourceDocument,
)
from .patterns import PATTERNS, ParameterPattern, parse_number, patterns_for
from .triage import (
    TriageResult,
    render_triage,
    triage_batch,
    triage_document,
)
from .review import (
    MissingEvidence,
    ReviewQueue,
    apply_decisions,
    load_decisions,
    merge_into_dataset,
    to_engine_records,
)

__all__ = [
    "CatalogueEntry", "load_catalogue", "missing_documents", "render_catalogue",
    "SourceDocument", "ExtractionCandidate", "ExtractionRun", "DocumentStatus",
    "DocumentRole",
    "ReviewDecision", "ReviewOutcome", "ReviewedParameter", "EXTRACTOR_VERSION",
    "extract_document", "read_pages",
    "PATTERNS", "ParameterPattern", "patterns_for", "parse_number",
    "ReviewQueue", "load_decisions", "apply_decisions", "to_engine_records",
    "merge_into_dataset", "MissingEvidence",
    "TriageResult", "triage_document", "triage_batch", "render_triage",
]
