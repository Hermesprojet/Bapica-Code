"""Reference-case runner — TICKET 2.2.

Replays each case against the engine, compares output by output within the
case's own tolerance, journalises every difference whether it passes or not,
and reports a status CI can act on.

What makes CI fail
------------------
Only :attr:`~.model.ReferenceStatus.FAILED` — a case that ran and drifted, or
refused when it should have produced a number (or the reverse). A case awaiting
its published source, or awaiting the engine module it exercises, is a *gap*:
reported in the summary, never silently green, but not a regression.

This distinction matters. If a missing source failed the build, the pressure
would be to invent one.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from ..exceptions import EurostructEngineError, OutOfValidationDomain
from .harness import get_harness
from .model import (
    Delta,
    ReferenceCase,
    ReferenceResult,
    ReferenceSourceType,
    ReferenceStatus,
    SourceDocument,
    ToleranceRule,
)

__all__ = ["run_case", "run_library", "LibraryReport", "load_library", "LIBRARY_DIR"]

LIBRARY_DIR = Path(__file__).parent / "library"


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def _case_from_dict(raw: dict[str, Any]) -> ReferenceCase:
    src = raw["source_document"]
    return ReferenceCase(
        reference_id=raw["reference_id"],
        title=raw["title"],
        normative_scope=tuple(raw["normative_scope"]),
        country_scope=tuple(raw["country_scope"]),
        source_type=ReferenceSourceType(raw["source_type"]),
        source_document=SourceDocument(
            title=src["title"],
            publisher=src.get("publisher"),
            edition=src.get("edition"),
            locator=src.get("locator"),
            isbn_or_url=src.get("isbn_or_url"),
            notes=src.get("notes"),
        ),
        harness=raw["harness"],
        input_dataset=raw.get("input_dataset", {}),
        expected_outputs=raw.get("expected_outputs", {}),
        tolerance_rules=tuple(
            ToleranceRule(
                output=r["output"], rel=r.get("rel"), abs=r.get("abs"),
                reason=r.get("reason"),
            )
            for r in raw.get("tolerance_rules", [])
        ),
        expect_refusal=raw.get("expect_refusal"),
        notes=raw.get("notes"),
    )


def load_library(directory: Path | None = None) -> tuple[ReferenceCase, ...]:
    """Load every case, sorted by identifier so runs are reproducible."""
    directory = directory or LIBRARY_DIR
    cases: list[ReferenceCase] = []
    seen: dict[str, Path] = {}
    for path in sorted(directory.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        for item in raw["cases"]:
            case = _case_from_dict(item)
            if case.reference_id in seen:
                raise ValueError(
                    f"identifiant de cas de reference duplique: "
                    f"'{case.reference_id}' dans {path.name} et "
                    f"{seen[case.reference_id].name}"
                )
            seen[case.reference_id] = path
            cases.append(case)
    return tuple(sorted(cases, key=lambda c: c.reference_id))


# ---------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------
def run_case(case: ReferenceCase) -> ReferenceResult:
    """Replay one case and compare against its published values."""
    harness = get_harness(case.harness)
    if harness is None:
        return ReferenceResult(
            case=case,
            status=ReferenceStatus.AWAITING_MODULE,
            message=(
                f"le module '{case.harness}' n'existe pas encore dans le moteur; "
                "cas declare pour la couverture a venir."
            ),
        )

    if not case.has_expectations:
        return ReferenceResult(
            case=case,
            status=ReferenceStatus.AWAITING_SOURCE,
            message=(
                f"valeurs attendues non renseignees. Source a depouiller: "
                f"{case.source_document.cite()}."
            ),
        )

    # --- refusal cases ---------------------------------------------------
    if case.expect_refusal is not None:
        try:
            harness(case.input_dataset)
        except OutOfValidationDomain as exc:
            if exc.what == case.expect_refusal:
                return ReferenceResult(
                    case=case, status=ReferenceStatus.REFUSED,
                    message=f"refus attendu obtenu: {exc.what}",
                )
            return ReferenceResult(
                case=case, status=ReferenceStatus.FAILED,
                message=(
                    f"refus attendu '{case.expect_refusal}', obtenu '{exc.what}'"
                ),
            )
        except EurostructEngineError as exc:
            return ReferenceResult(
                case=case, status=ReferenceStatus.FAILED,
                message=(
                    f"refus attendu '{case.expect_refusal}', obtenu "
                    f"{type(exc).__name__}: {exc}"
                ),
            )
        return ReferenceResult(
            case=case, status=ReferenceStatus.FAILED,
            message=(
                f"refus attendu '{case.expect_refusal}', mais le moteur a "
                "produit un resultat."
            ),
        )

    # --- numeric cases ---------------------------------------------------
    try:
        computed = harness(case.input_dataset)
    except EurostructEngineError as exc:
        return ReferenceResult(
            case=case, status=ReferenceStatus.FAILED,
            message=f"le moteur a refuse de calculer: {type(exc).__name__}: {exc}",
        )

    deltas: list[Delta] = []
    missing: list[str] = []
    for name, expected in sorted(case.expected_outputs.items()):
        if name not in computed:
            missing.append(name)
            continue
        rule = case.tolerance_for(name)
        if rule is None:
            missing.append(f"{name} (aucune tolerance definie)")
            continue
        within, abs_diff, rel_diff = rule.accepts(expected, computed[name])
        deltas.append(
            Delta(
                output=name, expected=expected, computed=computed[name],
                abs_diff=abs_diff, rel_diff=rel_diff, tolerance=rule, within=within,
            )
        )

    if missing:
        return ReferenceResult(
            case=case, status=ReferenceStatus.FAILED,
            computed_outputs=computed, delta_report=tuple(deltas),
            message=(
                "sortie(s) attendue(s) absente(s) du resultat ou sans regle de "
                f"tolerance: {', '.join(missing)}"
            ),
        )

    failed = [d for d in deltas if not d.within]
    status = ReferenceStatus.FAILED if failed else ReferenceStatus.PASSED
    message = None
    if failed:
        worst = max(failed, key=lambda d: d.rel_diff)
        message = (
            f"{len(failed)} sortie(s) hors tolerance; ecart le plus grand sur "
            f"'{worst.output}': {worst.rel_diff * 100:.4f} %"
        )
    return ReferenceResult(
        case=case, status=status, computed_outputs=computed,
        delta_report=tuple(deltas), message=message,
    )


# ---------------------------------------------------------------------------
# Library report
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LibraryReport:
    results: tuple[ReferenceResult, ...]

    @property
    def failures(self) -> tuple[ReferenceResult, ...]:
        return tuple(r for r in self.results if r.blocking)

    @property
    def ok(self) -> bool:
        return not self.failures

    def by_status(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in self.results:
            counts[r.status.value] = counts.get(r.status.value, 0) + 1
        return dict(sorted(counts.items()))

    def coverage_gaps(self) -> tuple[ReferenceResult, ...]:
        """Declared but not yet validating: awaiting a source or a module."""
        return tuple(
            r for r in self.results
            if r.status in (ReferenceStatus.AWAITING_SOURCE, ReferenceStatus.AWAITING_MODULE)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "total": len(self.results),
            "by_status": self.by_status(),
            "failures": [r.to_dict() for r in self.failures],
            "gaps": [
                {"reference_id": r.case.reference_id, "status": r.status.value,
                 "message": r.message}
                for r in self.coverage_gaps()
            ],
            "results": [r.to_dict() for r in self.results],
        }

    def render(self) -> str:
        lines = [
            "=== Validation normative — cas de reference ===",
            f"{len(self.results)} cas: "
            + ", ".join(f"{k}={v}" for k, v in self.by_status().items()),
            "",
        ]
        for r in self.results:
            lines.append(r.render())
        if self.failures:
            lines += ["", f"ECHEC: {len(self.failures)} cas hors tolerance."]
        else:
            gaps = self.coverage_gaps()
            lines += [
                "",
                "Aucun ecart sur les cas validables."
                + (
                    f" {len(gaps)} cas en attente de source ou de module "
                    "(couverture a completer, pas une regression)."
                    if gaps else ""
                ),
            ]
        return "\n".join(lines)


def run_library(cases: Iterable[ReferenceCase] | None = None) -> LibraryReport:
    """Run every case and produce the report CI consumes."""
    cases = tuple(cases) if cases is not None else load_library()
    return LibraryReport(results=tuple(run_case(c) for c in cases))
