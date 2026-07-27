"""The import pipeline, and above all the gate it must not let anything past.

The property under test throughout: **no path exists from a PDF to a confirmed
national parameter without a named engineer, a timestamp, an official source
and a page reference.**

Test content is invented and clearly marked as such. The values below are
deliberately *different* from the Eurocode recommendations (alpha_cc = 0,85 and
not 1,0) so that a test passing by accident — because the extractor defaulted
to the recommendation — is impossible.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from pdf_fixture import make_pdf

from ndp_import import (
    DocumentRole,
    ExtractionCandidate,
    MissingEvidence,
    ReviewDecision,
    ReviewedParameter,
    ReviewOutcome,
    ReviewQueue,
    SourceDocument,
    apply_decisions,
    extract_document,
    load_catalogue,
    merge_into_dataset,
    missing_documents,
    parse_number,
    patterns_for,
    to_engine_records,
)

PARAMS = ["alpha_cc", "gamma_C_persistent", "k1_redistribution", "As_max_ratio"]


@pytest.fixture
def pdf(tmp_path: Path) -> Path:
    return make_pdf(
        tmp_path / "annexe_test.pdf",
        [
            [
                "DOCUMENT DE TEST — contenu invente, ce n'est pas une Annexe Nationale.",
                "NOTE Clause 3.1.6(1)P : la valeur de alpha cc est 0,85.",
                "Clause 2.4.2.4(1) Tableau 2.1N : gamma C = 1,5.",
            ],
            [
                "Clause 5.5(4) : k1 = 0,44",
                "Clause 9.2.1.1(3) : As,max = 0,04 Ac",
            ],
        ],
    )


@pytest.fixture
def doc(pdf: Path) -> SourceDocument:
    return SourceDocument(
        doc_id=SourceDocument.digest(pdf),
        filename=pdf.name,
        role=DocumentRole.NATIONAL_ANNEX,
        country_code="BE",
        standard_family="EN 1992",
        part="1-1",
        reference="NBN EN 1992-1-1 ANB",
        publisher="NBN",
        edition="TEST-2026",
        effective_from=date(2026, 1, 1),
        language="fr",
        page_count=2,
        deposited_by="ing. A. Dupont",
        deposited_at="2026-07-26T09:00:00+00:00",
    )


@pytest.fixture
def run(doc: SourceDocument, pdf: Path):
    return extract_document(doc, pdf, parameters=PARAMS)


# ---------------------------------------------------------------------------
# Catalogue — what is missing, precisely
# ---------------------------------------------------------------------------
def test_catalogue_lists_the_documents_to_obtain() -> None:
    entries = load_catalogue()
    assert entries
    by_country = {e.country_code for e in entries}
    assert {"BE", "FR", "ES", "DE"} <= by_country
    for e in entries:
        assert e.reference and e.publisher
        assert e.how_to_acquire, f"{e.doc_key}: pas d'indication d'obtention"
        assert e.licence, f"{e.doc_key}: statut de licence non precise"


def test_no_annex_is_claimed_to_be_acquired() -> None:
    """Honesty check: nothing has been obtained, and the catalogue says so."""
    entries = load_catalogue()
    assert len(missing_documents(entries)) == len(entries)
    for e in entries:
        assert e.status == "not_acquired"
        assert e.edition is None


def test_catalogue_names_the_freely_available_documents() -> None:
    """Some documents are public; the catalogue must not bury that."""
    entries = {e.doc_key: e for e in load_catalogue()}
    for key in ("ES-CODIGO-ESTRUCTURAL", "ES-CTE", "ES-NCSE-02", "DE-MVV-TB"):
        assert "gratuit" in entries[key].how_to_acquire.lower(), key
    # And the National Annexes say they are not.
    assert "payant" in entries["BE-EN199211-NA"].licence.lower()


def test_catalogue_covers_every_country_and_phase() -> None:
    entries = load_catalogue()
    assert {e.country_code for e in entries} == {"BE", "FR", "ES", "DE"}
    # Every market needs the same Eurocode parts.
    per_country = {}
    for e in entries:
        if e.document_role == "national_annex":
            per_country.setdefault(e.country_code, set()).add(e.standard)
    assert len({frozenset(v) for v in per_country.values()}) == 1, (
        "les pays n'ont pas le meme perimetre d'Annexes Nationales"
    )
    # The blocking one is flagged P0.
    p0 = [e for e in entries if e.phase == "P0" and e.document_role == "national_annex"]
    assert {e.standard for e in p0} == {"EN 1992-1-1"}
    assert len(p0) == 4          # one per country


def test_national_regulations_are_listed_beside_the_annexes() -> None:
    """A Eurocode annex alone does not make a project compliant."""
    entries = {e.doc_key: e for e in load_catalogue()}
    # Belgium: fire requirements come from the Arrete Royal, not from EN 1992-1-2.
    assert "BE-AR-FEU" in entries
    # Spain: the enforceable reference is not the Eurocode.
    assert "ES-CODIGO-ESTRUCTURAL" in entries and "ES-CTE" in entries
    # Germany: the MVV TB decides which editions are in force.
    assert "DE-MVV-TB" in entries
    # France: the seismic zoning is a decree, not an annex.
    assert "FR-SEISME-ZONAGE" in entries
    for key in ("BE-AR-FEU", "ES-CTE", "DE-MVV-TB", "FR-SEISME-ZONAGE"):
        assert entries[key].document_role == "national_regulation"


def test_national_regulation_is_not_classified_as_a_base_eurocode(tmp_path) -> None:
    """Regression: an Arrete Royal was landing in the base-Eurocode bucket."""
    from ndp_import import triage_document

    pdf = make_pdf(
        tmp_path / "AR_annexe6.pdf",
        [["Arrete royal — Normes de base en matiere de prevention contre l'incendie"]],
    )
    assert triage_document(pdf).proposed_role is DocumentRole.NATIONAL_REGULATION


def test_every_expected_parameter_has_a_search_pattern() -> None:
    """A parameter with no pattern would never be searched for at all."""
    for entry in load_catalogue():
        if entry.parameters_expected:
            patterns_for(entry.parameters_expected)  # raises if any is missing


# ---------------------------------------------------------------------------
# Extraction — proposals only
# ---------------------------------------------------------------------------
def test_extraction_reads_the_document_not_the_recommendation(run) -> None:
    """alpha_cc = 0,85 in the test document; the EN recommendation is 1,0."""
    best = run.by_parameter()["alpha_cc"][0]
    assert best.parsed_value == 0.85
    assert best.page == 1
    assert "3.1.6(1)P" in best.snippet


def test_extraction_records_page_and_snippet(run) -> None:
    for c in run.candidates:
        assert c.page >= 1
        assert c.snippet.strip()
        assert c.doc_id == run.doc.doc_id


def test_parameters_absent_from_the_document_are_reported_not_defaulted(
    doc, pdf
) -> None:
    r = extract_document(doc, pdf, parameters=[*PARAMS, "cot_theta_max"])
    assert "cot_theta_max" in r.not_found
    assert all(c.parameter_name != "cot_theta_max" for c in r.candidates)


def test_clause_numbers_are_not_offered_as_values(run) -> None:
    """"Clause 2.4.2.4(1)" must not propose 2.4 as the value of gamma_C."""
    values = {c.parsed_value for c in run.by_parameter()["gamma_C_persistent"]}
    assert 1.5 in values
    assert 2.4 not in values
    assert 9.2 not in values


def test_confidence_never_reaches_certainty(run) -> None:
    """Nothing the extractor produces may look certain enough to skip a human."""
    assert all(c.confidence <= 0.9 for c in run.candidates)


def test_extraction_is_deterministic(doc, pdf) -> None:
    a = extract_document(doc, pdf, parameters=PARAMS)
    b = extract_document(doc, pdf, parameters=PARAMS)
    assert [c.to_dict() for c in a.candidates] == [c.to_dict() for c in b.candidates]


def test_candidate_has_no_way_to_declare_itself_verified() -> None:
    """The invariant, checked structurally."""
    fields = ExtractionCandidate.__dataclass_fields__
    assert "validation_status" not in fields
    assert "confirmed" not in fields
    assert "verified_by" not in fields


def test_swapped_document_is_refused(doc, pdf, tmp_path) -> None:
    other = make_pdf(tmp_path / "other.pdf", [["autre contenu"]])
    with pytest.raises(ValueError, match="empreinte"):
        extract_document(doc, other, parameters=PARAMS)


def test_scanned_document_is_refused(tmp_path) -> None:
    """A PDF with no text layer needs OCR; the extractor must not guess."""
    empty = make_pdf(tmp_path / "scan.pdf", [[]])
    d = SourceDocument(
        doc_id=SourceDocument.digest(empty), filename="scan.pdf",
        role=DocumentRole.NATIONAL_ANNEX, country_code="BE", standard_family="EN 1992", part="1-1",
        reference="X", publisher="Y", edition="1",
        effective_from=date(2026, 1, 1), language="fr", page_count=1,
        deposited_by="t", deposited_at="2026-07-26T09:00:00+00:00",
    )
    with pytest.raises(ValueError, match="couche de texte"):
        extract_document(d, empty, parameters=["alpha_cc"])


def test_unknown_parameter_name_is_refused(doc, pdf) -> None:
    with pytest.raises(KeyError, match="aucun motif"):
        extract_document(doc, pdf, parameters=["parametre_imaginaire"])


def test_european_decimal_comma() -> None:
    assert parse_number("1,0") == 1.0
    assert parse_number("0,0013") == 0.0013
    assert parse_number("250") == 250.0
    # Ambiguous groupings are refused rather than guessed.
    assert parse_number("1.234,5") is None
    assert parse_number("abc") is None


# ---------------------------------------------------------------------------
# Review — the gate
# ---------------------------------------------------------------------------
def _accept(run, name: str, value: float, page: int = 1) -> ReviewDecision:
    cand = run.by_parameter()[name][0]
    return ReviewDecision(
        candidate_id=cand.candidate_id,
        outcome=ReviewOutcome.ACCEPTED,
        verified_by="ing. C. Meunier (BE-ING-4471)",
        verified_at="2026-07-26T14:30:00+00:00",
        final_value=value,
        source_page=page,
    )


def test_review_queue_puts_the_hard_cases_first(run) -> None:
    queue = ReviewQueue(run)
    confidences = [max(c.confidence for c in cands) for _, cands in queue.items()]
    assert confidences == sorted(confidences)


def test_accepted_decision_produces_a_confirmed_record(run) -> None:
    reviewed = apply_decisions(run, [_accept(run, "alpha_cc", 0.85)])
    records = to_engine_records(reviewed)
    rec = records["alpha_cc"]
    assert rec["validation_status"] == "confirmed"
    assert rec["parameter_value"] == 0.85
    assert rec["source_type"] == "national_annex"
    assert rec["verified_by"].startswith("ing.")
    assert rec["verified_at"] == "2026-07-26T14:30:00+00:00"
    assert rec["source_doc_id"] == run.doc.doc_id
    assert rec["source_page"] == 1
    assert "NBN EN 1992-1-1 ANB" in rec["notes"]


def test_rejected_and_deferred_produce_nothing(run) -> None:
    cand = run.by_parameter()["alpha_cc"][0]
    for outcome in (ReviewOutcome.REJECTED, ReviewOutcome.DEFERRED):
        d = ReviewDecision(
            candidate_id=cand.candidate_id, outcome=outcome,
            verified_by="ing. C. Meunier", verified_at="2026-07-26T14:30:00+00:00",
        )
        assert to_engine_records(apply_decisions(run, [d])) == {}


def test_acceptance_without_a_value_is_refused(run) -> None:
    cand = run.by_parameter()["alpha_cc"][0]
    with pytest.raises(ValueError, match="sans final_value"):
        ReviewDecision(
            candidate_id=cand.candidate_id, outcome=ReviewOutcome.ACCEPTED,
            verified_by="ing. C. Meunier", verified_at="2026-07-26T14:30:00+00:00",
        )


def test_acceptance_without_a_named_verifier_is_refused(run) -> None:
    cand = run.by_parameter()["alpha_cc"][0]
    with pytest.raises(ValueError, match="verificateur nomme"):
        ReviewDecision(
            candidate_id=cand.candidate_id, outcome=ReviewOutcome.ACCEPTED,
            verified_by="   ", verified_at="2026-07-26T14:30:00+00:00",
            final_value=0.85,
        )


def test_acceptance_with_an_invalid_timestamp_is_refused(run) -> None:
    cand = run.by_parameter()["alpha_cc"][0]
    with pytest.raises(ValueError, match="verified_at invalide"):
        ReviewDecision(
            candidate_id=cand.candidate_id, outcome=ReviewOutcome.ACCEPTED,
            verified_by="ing. C. Meunier", verified_at="hier",
            final_value=0.85,
        )


def test_decision_on_a_candidate_never_shown_is_refused(run) -> None:
    """A signature cannot cover a value the reviewer was not presented."""
    d = ReviewDecision(
        candidate_id="0000000000000000", outcome=ReviewOutcome.ACCEPTED,
        verified_by="ing. C. Meunier", verified_at="2026-07-26T14:30:00+00:00",
        final_value=1.0,
    )
    with pytest.raises(KeyError, match="n'a pas ete presentee"):
        apply_decisions(run, [d])


@pytest.mark.parametrize(
    "field,blank",
    [("publisher", ""), ("reference", ""), ("edition", "")],
)
def test_emission_refuses_a_document_missing_its_evidence(run, field, blank) -> None:
    import dataclasses

    broken_doc = dataclasses.replace(run.doc, **{field: blank})
    cand = run.by_parameter()["alpha_cc"][0]
    item = ReviewedParameter(
        candidate=cand,
        decision=_accept(run, "alpha_cc", 0.85),
        document=broken_doc,
    )
    with pytest.raises(MissingEvidence):
        to_engine_records([item])


def test_emission_refuses_without_a_source_page(run) -> None:
    import dataclasses

    cand = dataclasses.replace(run.by_parameter()["alpha_cc"][0], page=0)
    dec = dataclasses.replace(_accept(run, "alpha_cc", 0.85), source_page=None)
    item = ReviewedParameter(candidate=cand, decision=dec, document=run.doc)
    # page 0 means "not located"; the emitter must not accept it as evidence.
    records = to_engine_records([item])
    assert records["alpha_cc"]["source_page"] == 0  # recorded as read
    # and the reviewer is the one who supplies the real page:
    dec2 = dataclasses.replace(dec, source_page=7)
    assert to_engine_records(
        [ReviewedParameter(cand, dec2, run.doc)]
    )["alpha_cc"]["source_page"] == 7


# ---------------------------------------------------------------------------
# Merge into the engine dataset
# ---------------------------------------------------------------------------
def test_merge_writes_confirmed_values_and_reports_what_remains(
    run, tmp_path
) -> None:
    dataset = tmp_path / "be.json"
    dataset.write_text(
        json.dumps(
            {
                "country_code": "BE",
                "country_name": "Belgique",
                "regions": [],
                "regulatory_framework": {
                    "binding_reference": "x", "eurocode_status": "y",
                    "verification_regime": "z", "notes": [],
                },
                "annexes": [
                    {
                        "standard_family": "EN 1992", "part": "1-1",
                        "reference": "NBN EN 1992-1-1 ANB",
                        "edition": "NON RELEVE", "effective_from": "2026-07-26",
                        "effective_to": None, "source_official": "NBN",
                        "source_url_or_doc_id": None,
                        "parameters": {
                            "alpha_cc": {
                                "parameter_value": 1.0, "unit": "dimensionless",
                                "clause": "§3.1.6(1)P", "description": "alpha cc",
                                "en_recommended": 1.0,
                                "source_type": "en_recommended",
                                "validation_status": "pending_verification",
                                "verified_at": None, "verified_by": None,
                                "notes": "placeholder",
                            },
                            "alpha_ct": {
                                "parameter_value": 1.0, "unit": "dimensionless",
                                "clause": "§3.1.6(2)P", "description": "alpha ct",
                                "en_recommended": 1.0,
                                "source_type": "en_recommended",
                                "validation_status": "pending_verification",
                                "verified_at": None, "verified_by": None,
                                "notes": "placeholder",
                            },
                        },
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    records = to_engine_records(apply_decisions(run, [_accept(run, "alpha_cc", 0.85)]))
    result = merge_into_dataset(dataset, run.doc, records)

    assert result["applied"] == ["alpha_cc"]
    assert result["still_pending"] == ["alpha_ct"]

    written = json.loads(dataset.read_text(encoding="utf-8"))
    param = written["annexes"][0]["parameters"]["alpha_cc"]
    assert param["parameter_value"] == 0.85
    assert param["validation_status"] == "confirmed"
    assert param["verified_by"].startswith("ing.")
    assert param["source_doc_id"] == run.doc.doc_id
    assert param["source_page"] == 1
    # The prose the reviewer was not asked about is preserved.
    assert param["description"] == "alpha cc"
    # And the annex now records the edition that was actually read.
    assert written["annexes"][0]["edition"] == "TEST-2026"
    # The untouched parameter is unchanged.
    assert written["annexes"][0]["parameters"]["alpha_ct"]["validation_status"] == (
        "pending_verification"
    )


def test_merge_refuses_an_annex_that_was_never_declared(run, tmp_path) -> None:
    dataset = tmp_path / "be.json"
    dataset.write_text(
        json.dumps({"country_code": "BE", "annexes": []}), encoding="utf-8"
    )
    records = to_engine_records(apply_decisions(run, [_accept(run, "alpha_cc", 0.85)]))
    with pytest.raises(KeyError, match="aucune annexe"):
        merge_into_dataset(dataset, run.doc, records)


def test_dry_run_changes_nothing(run, tmp_path) -> None:
    dataset = tmp_path / "be.json"
    payload = {
        "country_code": "BE",
        "annexes": [
            {
                "standard_family": "EN 1992", "part": "1-1",
                "reference": "NBN EN 1992-1-1 ANB", "edition": "NON RELEVE",
                "effective_from": "2026-07-26", "effective_to": None,
                "source_official": "NBN", "source_url_or_doc_id": None,
                "parameters": {},
            }
        ],
    }
    dataset.write_text(json.dumps(payload), encoding="utf-8")
    before = dataset.read_text(encoding="utf-8")

    records = to_engine_records(apply_decisions(run, [_accept(run, "alpha_cc", 0.85)]))
    merge_into_dataset(dataset, run.doc, records, dry_run=True)
    assert dataset.read_text(encoding="utf-8") == before


# ---------------------------------------------------------------------------
# Triage — interdiction 2 au niveau du document
# ---------------------------------------------------------------------------
def test_underscored_filename_still_identifies_an_annex(tmp_path) -> None:
    """Regression: '_' is a word character, so \\bANB\\b missed 'EN_1990__ANB'.

    The bug classified two genuine Belgian National Annexes as base Eurocodes,
    which is the one mistake this triage exists to prevent.
    """
    from ndp_import import triage_document

    pdf = make_pdf(tmp_path / "NBN_EN_1990__ANB.pdf", [["contenu de test"]])
    assert triage_document(pdf).proposed_role is DocumentRole.NATIONAL_ANNEX


def test_base_eurocode_is_not_mistaken_for_an_annex(tmp_path) -> None:
    from ndp_import import triage_document

    pdf = make_pdf(
        tmp_path / "NBN_EN_199111.pdf",
        [["norme belge NBN EN 1991-1-1 Eurocode 1 Actions sur les structures"]],
    )
    r = triage_document(pdf)
    assert r.proposed_role is DocumentRole.BASE_EUROCODE
    assert not r.usable_for_ndp
    assert any("valeurs RECOMMANDEES" in b for b in r.blockers)


def test_scanned_annex_is_flagged_for_ocr(tmp_path) -> None:
    from ndp_import import triage_document

    pdf = make_pdf(tmp_path / "NBN_EN_1990_ANB.pdf", [[]])
    r = triage_document(pdf)
    assert r.proposed_role is DocumentRole.NATIONAL_ANNEX   # still an annex
    assert not r.machine_readable
    assert not r.usable_for_ndp                             # but not usable yet
    assert any("ROC" in b for b in r.blockers)


def test_secondary_publication_is_refused(tmp_path) -> None:
    from ndp_import import triage_document

    pdf = make_pdf(tmp_path / "revue.pdf", [["CSTC magazine — Eurocode 0"]])
    r = triage_document(pdf)
    assert r.proposed_role is DocumentRole.SECONDARY_PUBLICATION
    assert not r.usable_for_ndp


def test_out_of_scope_standard_is_reported(tmp_path) -> None:
    from ndp_import import triage_document

    pdf = make_pdf(
        tmp_path / "annexe.pdf",
        [["NBN EN 1991-2 ANB Annexe nationale — actions sur les ponts"]],
    )
    r = triage_document(pdf, needed_standards=["EN 1992-1-1"])
    assert r.proposed_role is DocumentRole.NATIONAL_ANNEX
    assert r.usable_for_ndp          # it is a usable annex...
    assert any("hors des normes" in b for b in r.blockers)  # ...for another standard


def test_base_eurocode_can_never_be_confirmed(run) -> None:
    """Interdiction 2: the recommended value is not what the country adopted."""
    import dataclasses

    base = dataclasses.replace(run.doc, role=DocumentRole.BASE_EUROCODE)
    item = ReviewedParameter(
        candidate=run.by_parameter()["alpha_cc"][0],
        decision=_accept(run, "alpha_cc", 1.0),
        document=base,
    )
    with pytest.raises(MissingEvidence, match="valeur RECOMMANDEE"):
        to_engine_records([item])
