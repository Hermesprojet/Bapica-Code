"""Human verification, and emission into the engine's dataset.

This is the gate. Everything upstream produces proposals; nothing upstream can
produce a value the engine will use in strict mode.

:func:`to_engine_records` refuses to emit a ``confirmed`` record unless all
four pieces of evidence required by the cahier des charges are present:

===========================  ==========================================
official source              ``SourceDocument.publisher``
documentary reference        ``SourceDocument.reference`` + edition + page
named verifier               ``ReviewDecision.verified_by``
timestamp                    ``ReviewDecision.verified_at``
===========================  ==========================================

Anything missing raises. There is deliberately no ``force`` flag: a value
without its evidence has nowhere to go.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .model import (
    DocumentRole,
    ExtractionCandidate,
    ExtractionRun,
    ReviewDecision,
    ReviewedParameter,
    ReviewOutcome,
    SourceDocument,
)

__all__ = [
    "ReviewQueue",
    "load_decisions",
    "apply_decisions",
    "to_engine_records",
    "merge_into_dataset",
    "MissingEvidence",
]


class MissingEvidence(Exception):
    """A value was offered as confirmed without the evidence to support it."""


# ---------------------------------------------------------------------------
# Queue
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ReviewQueue:
    """What a reviewing engineer is asked to decide, in a useful order."""

    run: ExtractionRun

    def items(self) -> list[tuple[str, list[ExtractionCandidate]]]:
        """Parameters with their candidates, best first, hardest first.

        Parameters with no confident candidate come first: they are where a
        human is genuinely needed, and leaving them to the end is how they get
        rubber-stamped.
        """
        grouped = self.run.by_parameter()
        return sorted(
            grouped.items(),
            key=lambda kv: (max((c.confidence for c in kv[1]), default=0.0), kv[0]),
        )

    def render(self) -> str:
        lines = [
            f"=== Revue: {self.run.doc.reference} ({self.run.doc.edition}) ===",
            f"Document {self.run.doc.filename} — {self.run.doc.page_count} pages, "
            f"depose par {self.run.doc.deposited_by}",
            f"Extraction {self.run.extractor_version} le {self.run.run_at}",
            "",
        ]
        for name, cands in self.items():
            best = cands[0]
            value = (
                f"{best.parsed_value!r}" if best.parsed_value is not None
                else "AUCUNE VALEUR LUE"
            )
            lines.append(
                f"  {name:<22} p.{best.page:<4} conf={best.confidence:.2f}  {value}"
            )
            lines.append(f"      « {best.snippet[:150].strip()} … »")
            if len(cands) > 1:
                others = ", ".join(
                    f"{c.parsed_value!r}@p.{c.page}" for c in cands[1:4]
                )
                lines.append(f"      autres lectures: {others}")
            lines.append("")

        if self.run.pages_skipped_overlay:
            pages = ", ".join(str(p) for p in self.run.pages_skipped_overlay)
            lines.append("  PAGES NON LUES — filigrane vertical entrelace au texte:")
            lines.append(f"    p. {pages}")
            lines.append(
                "    L'extracteur n'a RIEN propose depuis ces pages. Le filigrane "
                "traverse les nombres (« 5E61 » pour 561): un chiffre lu y serait "
                "peut-etre coupe, et aucune regle ne permet de trancher. "
                "A ouvrir a la main."
            )
            lines.append("")

        if self.run.not_found:
            lines.append("  PARAMETRES NON TROUVES dans ce document:")
            for name in self.run.not_found:
                lines.append(f"    - {name}")
            lines.append(
                "    Ces parametres restent pending_verification. Verifier "
                "s'ils figurent dans un amendement ou une autre partie."
            )
            if self.run.pages_skipped_overlay:
                lines.append(
                    "    ATTENTION: des pages ont ete ecartees ci-dessus. "
                    "« Non trouve » ne veut pas dire « absent de l'annexe »."
                )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------
def load_decisions(path: Path) -> list[ReviewDecision]:
    """Load decisions from the file the engineer filled in."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [
        ReviewDecision(
            candidate_id=d["candidate_id"],
            outcome=ReviewOutcome(d["outcome"]),
            verified_by=d["verified_by"],
            verified_at=d["verified_at"],
            final_value=d.get("final_value"),
            unit=d.get("unit", "dimensionless"),
            source_page=d.get("source_page"),
            notes=d.get("notes"),
        )
        for d in raw["decisions"]
    ]


def apply_decisions(
    run: ExtractionRun, decisions: Sequence[ReviewDecision]
) -> list[ReviewedParameter]:
    """Pair each decision with its candidate.

    :raises KeyError: for a decision referring to no candidate of this run —
        which would mean the reviewer signed for something they were not shown.
    """
    index = {c.candidate_id: c for c in run.candidates}
    out: list[ReviewedParameter] = []
    for d in decisions:
        cand = index.get(d.candidate_id)
        if cand is None:
            raise KeyError(
                f"la decision porte sur le candidat '{d.candidate_id}', absent "
                f"de l'extraction de {run.doc.reference}. Une signature ne peut "
                "pas porter sur une valeur qui n'a pas ete presentee."
            )
        out.append(ReviewedParameter(candidate=cand, decision=d, document=run.doc))
    return out


# ---------------------------------------------------------------------------
# Emission
# ---------------------------------------------------------------------------
def to_engine_records(
    reviewed: Sequence[ReviewedParameter],
) -> dict[str, dict[str, Any]]:
    """Turn accepted decisions into the engine's parameter records.

    Rejected and deferred decisions are dropped: they carry no value. Accepted
    and corrected ones must bring their full evidence, or this raises.

    :raises MissingEvidence: when any of the four required elements is absent.
    """
    records: dict[str, dict[str, Any]] = {}

    for item in reviewed:
        if not item.confirmed:
            continue

        doc, dec, cand = item.document, item.decision, item.candidate

        # Interdiction 2, enforced at the document level: the recommended value
        # printed in the Eurocode's own Note is not what the country adopted.
        if not doc.role.can_fix_national_parameters:
            raise MissingEvidence(
                f"impossible de confirmer '{cand.parameter_name}' depuis "
                f"{doc.reference}: ce document est de type '{doc.role.value}'. "
                "Seule une Annexe Nationale (ou une reglementation nationale) "
                "fixe un parametre determine nationalement. Un Eurocode de "
                "base, meme homologue NF ou enregistre NBN, ne porte que la "
                "valeur RECOMMANDEE."
            )

        # Un fichier lisible n'est pas forcement le texte qui fait foi. Une
        # consolidation d'editeur declare elle-meme le contraire; confirmer
        # une valeur contre elle citerait, dans la note de calcul, un document
        # qui nie etre la source.
        if not doc.is_authoritative:
            raise MissingEvidence(
                f"impossible de confirmer '{cand.parameter_name}' depuis "
                f"{doc.reference}: ce fichier est declare NON OPPOSABLE "
                "(consolidation d'editeur, copie licenciee a un tiers, "
                "traduction). Il sert a preparer le depouillement — reperer "
                "les clauses, batir le dossier de relecture — mais une valeur "
                "confirmee doit citer la norme publiee par l'organisme."
            )

        missing: list[str] = []
        if not doc.publisher.strip():
            missing.append("source officielle (publisher)")
        if not doc.reference.strip():
            missing.append("reference documentaire (reference)")
        if not doc.edition.strip():
            missing.append("edition du document")
        if not dec.verified_by.strip():
            missing.append("verificateur nomme (verified_by)")
        if not dec.verified_at.strip():
            missing.append("horodatage (verified_at)")
        if item.source_page is None:
            missing.append("page source (source_page)")
        if dec.final_value is None:
            missing.append("valeur (final_value)")

        if missing:
            raise MissingEvidence(
                f"impossible de confirmer '{cand.parameter_name}' "
                f"({doc.country_code}/{doc.standard}): "
                + ", ".join(missing)
                + ". Une valeur nationale ne devient opposable qu'avec sa "
                "source, sa reference, son verificateur et sa date."
            )

        records[cand.parameter_name] = {
            "parameter_value": float(dec.final_value),
            "unit": dec.unit,
            "clause": f"§{cand.clause}" if cand.clause else "",
            "description": "",
            "en_recommended": None,
            "source_type": "national_annex",
            "validation_status": "confirmed",
            "verified_at": dec.verified_at,
            "verified_by": dec.verified_by,
            "source_doc_id": doc.doc_id,
            "source_page": item.source_page,
            "notes": (
                f"Releve dans {doc.reference} ({doc.edition}), p. "
                f"{item.source_page}, par {dec.verified_by} le {dec.verified_at}."
                + (f" {dec.notes}" if dec.notes else "")
            ),
        }

    return records


def merge_into_dataset(
    dataset_path: Path,
    doc: SourceDocument,
    records: Mapping[str, dict[str, Any]],
    dry_run: bool = False,
) -> dict[str, Any]:
    """Write confirmed records into the engine's country dataset.

    Only fields backed by the review are overwritten; ``description`` and
    ``en_recommended`` are kept from the existing entry, because the reviewer
    was asked about the *value*, not about the prose around it.

    :raises KeyError: if the dataset has no annex matching the document. The
        importer does not create annexes: an annex is declared once, with its
        edition and dates, by someone who has the document.
    """
    data = json.loads(dataset_path.read_text(encoding="utf-8"))

    annex = next(
        (
            a for a in data["annexes"]
            if a["standard_family"] == doc.standard_family
            and a["part"] == doc.part
            and a["reference"] == doc.reference
        ),
        None,
    )
    if annex is None:
        raise KeyError(
            f"aucune annexe '{doc.reference}' ({doc.standard}) dans "
            f"{dataset_path.name}. Declarer l'annexe et son edition avant "
            "d'importer ses valeurs."
        )

    applied: list[str] = []
    for name, rec in sorted(records.items()):
        existing = annex["parameters"].get(name, {})
        merged = dict(existing)
        merged.update(
            {
                k: v for k, v in rec.items()
                if k not in ("description", "en_recommended") or not existing.get(k)
            }
        )
        annex["parameters"][name] = merged
        applied.append(name)

    # The edition recorded on the annex must be the one that was read.
    if annex.get("edition") != doc.edition and applied:
        annex["edition"] = doc.edition
        annex["effective_from"] = doc.effective_from.isoformat()

    if not dry_run:
        dataset_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    return {
        "dataset": str(dataset_path),
        "annex": doc.reference,
        "edition": doc.edition,
        "applied": applied,
        "still_pending": sorted(
            n for n, p in annex["parameters"].items()
            if p.get("validation_status") != "confirmed"
        ),
        "dry_run": dry_run,
    }
