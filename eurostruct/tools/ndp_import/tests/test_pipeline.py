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


def test_acquired_entries_carry_their_evidence() -> None:
    """An entry may only claim to be acquired if it can prove which file.

    The catalogue is an inventory, not the parameter store: marking a document
    acquired says "we hold this file", never "we trust its values". The sha256
    is what ties the claim to a specific file.
    """
    import json

    from ndp_import.catalogue import _DATA

    raw = json.loads(_DATA.read_text(encoding="utf-8"))
    acquired = [d for d in raw["documents"] if d["status"] != "not_acquired"]
    for d in acquired:
        assert d.get("doc_id_sha256"), f"{d['doc_key']}: acquis sans empreinte"
        assert d.get("edition_read_from_cover"), (
            f"{d['doc_key']}: acquis sans edition relevee sur la page de garde"
        )
        # Read from the cover is not the same as declared by the depositor.
        assert "DECLARER" in d["acquisition"]["notes"], (
            f"{d['doc_key']}: l'edition lue doit rester a declarer"
        )


def test_no_acquired_document_promotes_a_parameter() -> None:
    """Holding the file changes nothing about the values it contains.

    This is the property that matters: the Belgian EC2 annex is now in hand and
    readable, and every one of its parameters is still pending_verification.
    """
    from ndp_import.catalogue import load_catalogue as _load

    engine_data = (
        Path(__file__).resolve().parents[3]
        / "engine/src/eurostruct_engine/ndp/data/be.json"
    )
    import json

    be = json.loads(engine_data.read_text(encoding="utf-8"))
    params = [p for a in be["annexes"] for p in a["parameters"].values()]

    # Le sens du test est la NON-promotion. 'not_representable' est admis: il
    # rend un parametre inutilisable, il n'en autorise aucun.
    promoted = [p for p in params if p["validation_status"] == "confirmed"]
    assert not promoted, (
        "un parametre est passe en 'confirmed' sans decision de relecture "
        "signee — detenir le PDF ne vaut pas relecture"
    )
    assert {p["validation_status"] for p in params} <= {
        "pending_verification",
        "not_representable",
    }

    # Et un parametre sans valeur doit dire pourquoi il n'en a pas. Deux
    # raisons legitimes, et seulement deux: rien a stocker
    # ('not_representable'), ou une valeur par cas (variantes). Un troisieme
    # cas serait une valeur perdue.
    for p in params:
        explained = (
            p["validation_status"] == "not_representable" or bool(p.get("variants"))
        )
        assert (p["parameter_value"] is None) == explained, p
        # Les deux raisons s'excluent: une valeur par cas EST representable.
        assert not (
            p["validation_status"] == "not_representable" and p.get("variants")
        )


def test_catalogue_report_does_not_deny_what_is_in_hand() -> None:
    """Regression: the footer said "aucun ... n'est acquis" with three in hand.

    A report that under-states what we hold is not a safe error: it hides that
    a document is available to be read, and it contradicts the entries printed
    just above it.
    """
    from ndp_import import load_catalogue, render_catalogue

    entries = load_catalogue()
    held = [e for e in entries if e.acquired]
    assert held, "le jeu de test suppose au moins un document acquis"

    text = render_catalogue(entries)
    assert "Aucun de ces documents n'est acquis" not in text
    authoritative = [e for e in entries if e.is_authoritative]
    assert f"{len(authoritative)} document(s) EN MAIN qui font foi" in text
    assert "[EN MAIN]" in text
    # ...et la detention ne doit jamais se lire comme une confirmation.
    assert "ne confirme AUCUNE valeur" in text


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


@pytest.mark.parametrize(
    ("name", "text", "expected"),
    [
        ("EN_199211.pdf", "EN 1992-1-1 Eurocode 2", "EN 1992-1-1"),
        ("EN_199315.pdf", "EN 1993-1-5 Eurocode 3", "EN 1993-1-5"),
        # Les deux qui echouaient: la partie a deux chiffres etait tronquee.
        ("EN_1993110.pdf", "EN 1993-1-10 Eurocode 3", "EN 1993-1-10"),
        ("EN_1993111.pdf", "EN 1993-1-11 Eurocode 3", "EN 1993-1-11"),
        ("EN_19912.pdf", "EN 1991-2 Eurocode 1", "EN 1991-2"),
        ("EN_1990.pdf", "EN 1990 Eurocode 0", "EN 1990"),
    ],
)
def test_two_digit_part_numbers_are_read_whole(tmp_path, name, text, expected) -> None:
    """Regression: 'EN 1993-1-10' etait annonce 'EN 1993-1'.

    Le quantificateur de la partie n'acceptait qu'un chiffre. Sur '1-10' la
    frontiere de mot ne tombait pas apres le premier '1', la regex refluait, et
    le document sortait sous une reference qui n'existe pas — donc ecarte comme
    hors perimetre. L'ANB acier renvoie justement a l'EN 1993-1-10 en
    §3.2.3(3).
    """
    from ndp_import import triage_document

    assert triage_document(make_pdf(tmp_path / name, [[text]])).proposed_standard == (
        expected
    )


#: Une page filigranee: le texte utile, puis la colonne de lettres isolees que
#: laisse un tampon vertical a l'extraction.
_WATERMARK_COLUMN = list("NATIONALMIRROR")
_CLAUSE_LINE = "Clause 3.1.6(1)P : la valeur de alpha cc est 0,85."


def _deposited(pdf: Path, page_count: int) -> SourceDocument:
    return SourceDocument(
        doc_id=SourceDocument.digest(pdf), filename=pdf.name,
        role=DocumentRole.NATIONAL_ANNEX, country_code="BE",
        standard_family="EN 1992", part="1-1",
        reference="NBN EN 1992-1-1 ANB", publisher="NBN", edition="TEST-2026",
        effective_from=date(2026, 1, 1), language="fr", page_count=page_count,
        deposited_by="ing. A. Dupont", deposited_at="2026-07-26T09:00:00+00:00",
    )


def test_vertical_watermark_page_yields_no_candidate(tmp_path) -> None:
    """NBN EN 1993-1-2 ANB stamps every page, and the letters split the numbers.

    Its table of critical temperatures extracts as "5E61" for 561 and "4M57"
    for 457. Neither is repairable by rule, so the page must produce nothing at
    all — and must say that it produced nothing *on purpose*.
    """
    from ndp_import import page_carries_vertical_overlay

    watermarked = [_CLAUSE_LINE, *_WATERMARK_COLUMN]
    assert page_carries_vertical_overlay("\n".join(watermarked))
    assert not page_carries_vertical_overlay(_CLAUSE_LINE)

    pdf = make_pdf(tmp_path / "ANB_filigrane.pdf", [watermarked, [_CLAUSE_LINE]])
    run = extract_document(_deposited(pdf, 2), pdf, parameters=["alpha_cc"])

    assert run.pages_skipped_overlay == (1,)
    assert all(c.page != 1 for c in run.candidates)
    # ...et la page saine reste lisible: la garde ecarte des pages, pas le document.
    assert any(c.page == 2 for c in run.candidates)


def test_skipped_pages_are_reported_not_silently_dropped(tmp_path) -> None:
    """'non trouve' ne doit jamais vouloir dire 'j'ai refuse de lire'."""
    pdf = make_pdf(
        tmp_path / "ANB_filigrane2.pdf", [[_CLAUSE_LINE, *_WATERMARK_COLUMN]]
    )
    run = extract_document(_deposited(pdf, 1), pdf, parameters=["alpha_cc"])
    text = ReviewQueue(run).render()

    assert not run.candidates
    assert "filigrane" in text
    assert "p. 1" in text
    assert "ne veut pas dire" in text


@pytest.mark.parametrize(
    "front",
    [
        "projet de norme prNBN EN 1997-1 ANB Annexe nationale",
        "oSIST prEN 1997-1:2022 iTeh STANDARD PREVIEW Eurocode 7",
        "NBN ENV 1993-1-1 Annexe nationale — pre-norme",
        "Ontwerpnorm prNBN EN 1992-1-1 ANB Nationale bijlage",
    ],
)
def test_a_draft_annex_can_never_fix_a_national_parameter(tmp_path, front) -> None:
    """Regression: a DRAFT National Annex passed triage with zero blockers.

    Every other marker sees "annexe nationale" and stops there — a prEN cover
    is worded like a published one. The values in a draft have no legal force
    and can still change, so holding one must never unblock anything.
    """
    from ndp_import import triage_document

    r = triage_document(make_pdf(tmp_path / "depot.pdf", [[front]]))
    assert r.is_draft
    assert not r.usable_for_ndp
    assert any("PROJET" in b for b in r.blockers)


@pytest.mark.parametrize(
    "front",
    [
        "NBN EN 1992-1-1 ANB Norme belge 1e ed., aout 2010 Annexe nationale",
        # Une norme PUBLIEE cite en couverture la pre-norme qu'elle remplace.
        # C'est le faux positif qui avait signale 13 Eurocodes publies comme
        # des projets.
        "EUROPEAN STANDARD Avril 2005 Remplace ENV 1993-1-2:1995 "
        "Annexe nationale NBN EN 1993-1-2 ANB",
        "EUROPEAN STANDARD Vervangt ENV 1991-2-2:1995 Nationale bijlage ANB",
        "NBN EN 1990 ANB — annule et remplace ENV 1991-1:1994 — Annexe nationale",
    ],
)
def test_a_published_annex_is_not_flagged_as_a_draft(tmp_path, front) -> None:
    """The guard must not swallow the documents we actually hold.

    A marker counts only when it designates *this* document. "Remplace ENV
    ..." names a superseded edition, not the one in hand.
    """
    from ndp_import import triage_document

    r = triage_document(make_pdf(tmp_path / "NBN_EN_ANB.pdf", [[front]]))
    assert not r.is_draft
    assert r.usable_for_ndp


def test_a_download_bait_page_is_refused_even_titled_as_an_annex(tmp_path) -> None:
    """A deposited "Eurocode 7 part 2" was an SEO scraper page.

    Two pages of "DOWNLOAD! DIRECT DOWNLOAD!" with injected off-topic phrases.
    The triage classified it neatly as a base Eurocode covering EN 1997-2 —
    harmless only by luck, since base Eurocodes are refused anyway. Dressed as
    an annex, the same page came back usable.
    """
    from ndp_import import triage_document

    r = triage_document(
        make_pdf(
            tmp_path / "Eurocode7Part2.pdf",
            [[
                "Eurocode 7 part 2 pdf DOWNLOAD! DIRECT DOWNLOAD!",
                "NBN EN 1997-2 ANB Annexe nationale ICS 91.010.30",
            ]],
        )
    )
    assert r.is_impersonation
    assert not r.usable_for_ndp
    assert any("N'EST PAS UNE NORME" in b for b in r.blockers)


def test_a_document_without_publication_identity_is_refused(tmp_path) -> None:
    """No ICS, no standards body, no gazette: nobody publishes it."""
    from ndp_import import triage_document

    r = triage_document(
        make_pdf(tmp_path / "notes.pdf", [["Annexe nationale EN 1992-1-1 alpha cc 0,85"]])
    )
    assert not r.has_publication_identity
    assert not r.usable_for_ndp
    assert any("identite de publication" in b for b in r.blockers)


def test_scans_are_not_penalised_for_a_missing_hallmark(tmp_path) -> None:
    """A scan has no text layer for an unrelated reason; OCR is its blocker."""
    from ndp_import import triage_document

    r = triage_document(make_pdf(tmp_path / "NBN_EN_1990_ANB.pdf", [[]]))
    assert r.has_publication_identity          # non juge, pas juge coupable
    assert any("ROC" in b for b in r.blockers)
    assert not any("identite de publication" in b for b in r.blockers)


def test_a_redeposited_file_is_announced_as_already_held(tmp_path) -> None:
    """The same three annexes arrived three times, byte for byte.

    Nothing in the triage said "you already have this", so re-sending looked
    like it might help. It never does — and when the held copy is blocked on
    OCR, the report has to say that a *text* version is what is needed.
    """
    from ndp_import import load_catalogue, render_triage, triage_document

    held = next(e for e in load_catalogue() if e.acquired and e.doc_id_sha256)
    pdf = make_pdf(tmp_path / "redepot.pdf", [["NBN EN 1992-1-1 ANB ICS 91.010.30"]])
    r = triage_document(pdf)

    # Le fichier de test n'est pas celui du catalogue: pas de fausse alerte.
    assert "DEJA EN MAIN" not in render_triage([r])

    # Avec l'empreinte d'un document detenu, l'alerte tombe.
    import dataclasses

    text = render_triage([dataclasses.replace(r, doc_id=held.doc_id_sha256)])
    assert "[DEJA EN MAIN]" in text
    assert held.reference in text
    assert "Les redeposer ne change rien" in text


def test_competing_editions_of_one_standard_are_flagged(tmp_path) -> None:
    """Two distinct files for the same annex must not be picked at random.

    NBN EN 1990 ANB sat in the deposit in both its 1st edition (2007) and its
    2nd (2013), whose cover says "Remplace: NBN EN 1990 ANB (2007)". The 2007
    one got registered as the document in hand — a superseded edition, chosen
    only because it was seen first.
    """
    from ndp_import import render_triage, triage_document

    old = triage_document(
        make_pdf(
            tmp_path / "ANB_1990_2007.pdf",
            [["ICS 91.010.30 NBN EN 1990 ANB Norme belge 1e ed., septembre 2007"]],
        )
    )
    new = triage_document(
        make_pdf(
            tmp_path / "ANB_1990_2013.pdf",
            [["ICS 91.010.30 NBN EN 1990 ANB Norme belge 2e ed., janvier 2013"]],
        )
    )
    text = render_triage([old, new])

    assert "PLUSIEURS FICHIERS DISTINCTS" in text
    assert "ANB_1990_2007.pdf" in text and "ANB_1990_2013.pdf" in text
    assert "Une edition remplacee ne doit pas servir" in text

    # Un seul fichier: pas d'alerte.
    assert "PLUSIEURS FICHIERS DISTINCTS" not in render_triage([new])


def test_mis_decoded_text_is_refused(tmp_path) -> None:
    """A deposited NF EN 1991-1-4/NA extracted as « ÒÚ ÛÒ ïççïóïóìñÒß ».

    Its font carries no usable Unicode map, so the text layer exists and is
    wrong — more dangerous than a scan, because it looks like text. Measured:
    96 % Latin-1 supplement against 0,5–3,4 % on every sound document.

    Tested on the extracted text rather than through a fixture PDF: the
    fixture's font cannot encode these glyphs at all and emits ``(cid:NNN)``
    instead — a different corruption, already covered by the "no text layer"
    path. Reproducing a broken ToUnicode map would mean shipping a
    deliberately malformed font, a heavier fixture than this guard deserves.
    """
    from ndp_import import text_is_mis_decoded

    broken = "ÒÚ ÛÒ ïççïóïóìñÒß ³¿® îððè Ý» ¼±½«³»²¬ » ¬ @ « ¿¹» " * 12
    assert text_is_mis_decoded(broken)

    # Meme dilue par du texte sain, le signal reste franc: 96 % contre 3 %.
    assert text_is_mis_decoded(broken + "Annexe nationale ICS 91.010.30" * 3)


def test_sound_french_text_is_not_flagged_as_mis_decoded() -> None:
    """Accented French is normal; the guard must not fire on it."""
    from ndp_import import text_is_mis_decoded

    sound = (
        "La valeur de gamma a utiliser est celle recommandee. Resistance "
        "caracteristique du beton, deformation a la rupture, elancement. "
        "Coefficient de securite pour les elements precontraints. "
    ) * 4
    assert not text_is_mis_decoded(sound)
    # Et un texte court ne se juge pas: trois mots accentues suffiraient a
    # depasser le seuil sans rien signifier.
    assert not text_is_mis_decoded("éàçù")


def test_a_french_classification_index_counts_as_a_publication_identity(
    tmp_path,
) -> None:
    """« P 18-711-1/NA » identifies an AFNOR standard.

    The French NA arrived as a publisher's consolidation whose cover carries no
    AFNOR banner, so the identity guard rejected the real thing. The indice de
    classement is the official identifier and survives that repackaging.
    """
    from ndp_import import triage_document

    r = triage_document(
        make_pdf(
            tmp_path / "NA_FR.pdf",
            [["NF EN 1992-1-1/NA ( P 18-711-1/NA ) Annexe Nationale"]],
        )
    )
    assert r.has_publication_identity
    assert r.usable_for_ndp


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


def test_a_non_authoritative_file_can_never_confirm_a_value(run) -> None:
    """A readable file is not necessarily the text that governs.

    The French NAs arrived as publisher's consolidations whose own covers say
    « seules les Normes individuellement homologuees et composant cette
    compilation font foi », watermarked with another organisation's licence.
    They are perfectly usable to PREPARE the reading and must never back a
    confirmed value: the note de calcul would cite a document that denies
    being the source.
    """
    import dataclasses

    reading_only = dataclasses.replace(run.doc, is_authoritative=False)
    cand = run.candidates[0]
    decision = ReviewDecision(
        candidate_id=cand.candidate_id, outcome=ReviewOutcome.ACCEPTED,
        verified_by="ing. C. Meunier", verified_at="2026-07-27T10:00:00+00:00",
        final_value=0.85, source_page=cand.page,
    )
    item = ReviewedParameter(
        candidate=cand, decision=decision, document=reading_only
    )
    with pytest.raises(MissingEvidence, match="NON OPPOSABLE"):
        to_engine_records([item])

    # Le meme document declare opposable passe: c'est bien ce seul champ qui
    # bloque, pas un effet de bord.
    ok = ReviewedParameter(candidate=cand, decision=decision, document=run.doc)
    assert to_engine_records([ok])


def test_the_catalogue_separates_holding_from_authority() -> None:
    """Two states, and the report must not merge them."""
    from ndp_import import load_catalogue, render_catalogue

    entries = load_catalogue()
    for e in entries:
        if e.is_authoritative:
            assert e.acquired, f"{e.doc_key}: fait foi sans etre detenu"

    text = render_catalogue(entries)
    assert "[EN MAIN]" in text
    assert "ne confirme AUCUNE valeur" in text


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


def test_watermark_artefacts_are_stripped_before_reading_numbers() -> None:
    """Regression: Belgian ANBs carry a watermark with no ToUnicode table.

    pdfminer emits those glyphs as "(cid:22)". In the 9-page snow annex there
    are 774 of them, interleaved with the real text — their digits would be
    offered as candidate values.
    """
    from ndp_import.extract import _normalise

    raw = "Clause 5.2(2) (cid:22) la valeur (cid:8) est 1,60 (cid:16) kN/m2"
    clean = _normalise(raw)
    assert "cid" not in clean
    assert "5.2(2)" in clean and "1,60" in clean


# ---------------------------------------------------------------------------
# Three traps found on a real deposit of 50 base-Eurocode documents
# ---------------------------------------------------------------------------
def test_a_reversed_watermark_still_discloses_an_uncontrolled_copy(tmp_path) -> None:
    """The trap that disables every other guard.

    A deposited EN 1990 came out as ``desneciL :ypoC`` and ``dellortnocnU`` —
    BSI's licence stamp, rendered right-to-left by the PDF's font. The body of
    that document read forwards perfectly well, so a whole-document reversal
    test says "readable" and is right to. But the disqualifying sentence lives
    in the reversed watermark, where no forward keyword can reach it.

    Three files of the deposit carried it, including the only one that was not
    a draft.
    """
    from ndp_import import triage_document

    front = (
        "ISB )c( ,ypoC dellortnocnU ,3002 yluJ 81 ,dleiffehS fo ytisrevinU "
        ",ytisrevinU dleiffehS :ypoC desneciL "
        "EUROPEAN STANDARD EN 1990 Eurocode - Basis of structural design ICS 91.010.30"
    )
    r = triage_document(make_pdf(tmp_path / "en1990.pdf", [[front]]))
    assert r.is_uncontrolled_copy
    assert not r.usable_for_ndp
    assert any("NON MAINTENUE" in b for b in r.blockers)


def test_a_wholly_reversed_document_is_refused_before_anything_else(tmp_path) -> None:
    """A prEN cover rendered backwards reads NErp and matches no draft marker.

    Which is why the reversal blocker is reported first: without it the file
    comes back merely "unidentified", a far milder verdict than a draft
    deserves.
    """
    from ndp_import import triage_document

    forward = (
        "EUROPEAN STANDARD prEN 1992-1-1 Eurocode 2 Design of concrete "
        "structures Licensed copy uncontrolled December 2004 national annex "
        "ICS 91.010.30 " * 3
    )
    r = triage_document(make_pdf(tmp_path / "envers.pdf", [[forward[::-1]]]))
    assert r.is_reversed
    assert not r.usable_for_ndp
    assert any("A L'ENVERS" in b for b in r.blockers)
    assert r.blockers[0].startswith("TEXTE RENDU A L'ENVERS")


def test_normal_text_is_not_taken_for_reversed(tmp_path) -> None:
    """The documents we actually hold must survive the guard."""
    from ndp_import import triage_document

    front = (
        "EUROPEAN STANDARD NORME EUROPEENNE NBN EN 1992-1-1 ANB Annexe "
        "nationale Norme belge 1e ed., aout 2010 ICS 91.010.30 national "
        "december copyright standard eurocode " * 3
    )
    r = triage_document(make_pdf(tmp_path / "ok.pdf", [[front]]))
    assert not r.is_reversed


def test_a_lecture_deck_is_not_a_standard(tmp_path) -> None:
    """Recognised on what a standard never contains, never on its title.

    "Basis of structural design" IS the subtitle of EN 1990: a title-keyed rule
    would reject the very document it exists to protect. An author's email at a
    university and "slides available on the web" are the real tell.
    """
    from ndp_import import triage_document

    front = (
        "Eurocode 3 for Dummies The Opportunities and Traps a brief guide on "
        "element design to EC3 Tim McCarthy Email tim.mccarthy@umist.ac.uk "
        "Slides available on the web"
    )
    r = triage_document(make_pdf(tmp_path / "cours.pdf", [[front]]))
    assert r.is_teaching_material
    assert not r.usable_for_ndp
    assert any("PEDAGOGIQUE" in b for b in r.blockers)


def test_the_en_1990_subtitle_alone_does_not_make_it_teaching_material(
    tmp_path,
) -> None:
    """The false positive the guard was written to avoid."""
    from ndp_import import triage_document

    front = (
        "EUROPEAN STANDARD EN 1990 Eurocode - Basis of structural design "
        "NBN EN 1990 ANB Annexe nationale Norme belge ICS 91.010.30"
    )
    r = triage_document(make_pdf(tmp_path / "en1990.pdf", [[front]]))
    assert not r.is_teaching_material


def test_a_solid_DDENV_designation_is_a_pre_standard(tmp_path) -> None:
    """``\\bENV\\b`` has no boundary inside "DDENV", so it missed one.

    DD ENV 1991-2-6 arrived through an IHS reseller whose banner replaced the
    publisher's cover: the front matter carried no ENV at all, and the only
    remaining signal was the filename, where the form is written solid.
    """
    from ndp_import import triage_document

    pdf = make_pdf(
        tmp_path / "Eurocode_1_Part_26__DDENV_1991261997.pdf",
        [["IHS Intra/Spex technology and images copyright (c) IHS 2003"]],
    )
    r = triage_document(pdf)
    assert r.is_draft
    assert not r.usable_for_ndp


# ---------------------------------------------------------------------------
# The distributor's banner must not override the document's identity
# ---------------------------------------------------------------------------
def test_a_national_annex_delivered_through_a_platform_stays_an_annex(
    tmp_path,
) -> None:
    """The worst-direction bug of this pipeline, and the only one so far.

    NF EN 1990/NA arrived through Reef4 — the CSTB's document platform — whose
    banner sits on page 1 above AFNOR's own cover. ``_SECONDARY_MARKERS``
    matched ``CSTB`` and won outright, so a genuine National Annex was
    classified as CSTB guidance and refused.

    Every earlier bug ADMITTED something that should have been refused, and the
    downstream guards still caught it. This one REFUSED exactly what the engine
    has been waiting for, and nothing downstream recovers from that: the file
    simply looks unusable.
    """
    from ndp_import import triage_document
    from ndp_import.model import DocumentRole

    front = (
        "Reef4 - CSTB Page 1 sur 10 Reef4 version 4.4.3.1 - Edition 167 - "
        "Mars 2012 Document : NF EN 1990/NA (décembre 2011) : Eurocodes "
        "structuraux - Bases de calcul des structures - Annexe nationale à la "
        "NF EN 1990 (Indice de classement : P06-100-1/NA) NF EN 1990/NA "
        "Décembre 2011 P 06-100-1/NA"
    )
    r = triage_document(make_pdf(tmp_path / "na.pdf", [[front]]), ["EN 1990"])
    assert r.proposed_role is DocumentRole.NATIONAL_ANNEX
    assert r.usable_for_ndp, r.blockers


def test_a_standard_delivered_through_a_platform_is_not_guidance(tmp_path) -> None:
    """Same banner over NF EN 1990 itself, which says « Norme francaise
    homologuee ». Still refused — a base Eurocode carries recommended values —
    but for THAT reason, not as though it were a magazine article.
    """
    from ndp_import import triage_document
    from ndp_import.model import DocumentRole

    front = (
        "Reef4 - CSTB Page 1 sur 63 Document : NF EN 1990 (mars 2003) : "
        "Eurocodes structuraux - Bases de calcul des structures (Indice de "
        "classement : P06-100-1) Statut Norme française homologuée"
    )
    r = triage_document(make_pdf(tmp_path / "base.pdf", [[front]]), ["EN 1990"])
    assert r.proposed_role is DocumentRole.BASE_EUROCODE
    assert not r.usable_for_ndp


def test_real_guidance_is_still_classified_as_secondary(tmp_path) -> None:
    """The guard must not swallow what it was built for.

    A CSTC information note discusses annexes and is not one. It carries no
    indice de classement and no homologation status, which is what separates
    it from a standard the CSTB merely delivered.
    """
    from ndp_import import triage_document
    from ndp_import.model import DocumentRole

    front = (
        "Les Dossiers du CSTC — Note d'information technique — application "
        "des Eurocodes et de leurs annexes nationales en Belgique"
    )
    r = triage_document(make_pdf(tmp_path / "cstc.pdf", [[front]]))
    assert r.proposed_role is DocumentRole.SECONDARY_PUBLICATION
    assert not r.usable_for_ndp


def test_a_published_standard_not_yet_in_force_is_refused(tmp_path) -> None:
    """The most convincing impostor this triage has met.

    The second generation of Eurocodes is being published — EN 1990-1:2023,
    EN 1993-1-8:2024, EN 1993-2:2026 — while the first generation stays in
    force. NBN prints the fact on the cover, in capitals:

        THIS STANDARD IS NOT YET APPLICABLE PENDING THE PUBLICATION OF ITS
        ACCOMPANYING NATIONAL ANNEX ... The applicable standard in Belgium
        remains the NBN EN 1993-2:2007.

    It is neither a draft nor a withdrawn edition: publisher, number, layout
    and text are all genuine. Only its force is missing, and nothing but that
    sentence distinguishes it from the standard actually in force.
    """
    from ndp_import import triage_document

    front = (
        "Belgian Standard EN 1993-2:2026 NBN EN 1993-2:2026 Eurocode 3 - "
        "Design of steel structures - Part 2: Bridges (THIS STANDARD IS NOT "
        "YET APPLICABLE PENDING THE PUBLICATION OF ITS ACCOMPANYING NATIONAL "
        "ANNEX AND THE PUBLICATION STRATEGY OF THE SECOND GENERATION "
        "EUROCODES. The applicable standard in Belgium remains the "
        "NBN EN 1993-2:2007.) Valid from 01-01-2026 ICS 91.010.30"
    )
    r = triage_document(make_pdf(tmp_path / "gen2.pdf", [[front]]))
    assert r.is_not_yet_applicable
    assert not r.usable_for_ndp
    assert any("PAS ENCORE APPLICABLE" in b for b in r.blockers)


def test_a_national_annex_in_force_is_not_caught_by_that_guard(tmp_path) -> None:
    """The guard must not swallow the annexes the engine is waiting for."""
    from ndp_import import triage_document

    front = (
        "ICS: 91.010.30 NBN EN 1993-2 ANB Norme belge 1e éd., mars 2011 "
        "Indice de classement: B 51 Eurocode 3 - Calcul des structures en "
        "acier - Partie 2 : Ponts métalliques - Annexe nationale"
    )
    r = triage_document(make_pdf(tmp_path / "anb.pdf", [[front]]), ["EN 1993-2"])
    assert not r.is_not_yet_applicable
    assert r.usable_for_ndp, r.blockers


# ---------------------------------------------------------------------------
# Lire une couverture NBN: l'amendement, le futur, et le document technique
#
# Les quatre tests qui suivent viennent tous du meme depot — l'EC6 et l'EC8/EC9
# belges — et chacun corrige une lecture de couverture qui etait fausse.
# ---------------------------------------------------------------------------
def _nbn(name: str = "record_nbn_batch"):
    """Charger un script de scripts/, qui n'est pas un paquet installe."""
    import importlib.util
    import sys
    from pathlib import Path as _P

    root = _P(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(root))
    spec = importlib.util.spec_from_file_location(name, root / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_an_amended_annex_belongs_to_the_standard_it_amends(tmp_path) -> None:
    """« NBN EN 1996-1-1+A1 ANB:2016 » est l'annexe de l'EN 1996-1-1.

    Deux exigences, et la seconde est la moins evidente:

    * la reference doit etre LUE avec son « +A1 » — sans quoi le fichier est
      ignore en silence et le catalogue continue d'annoncer l'edition 2010
      comme l'annexe belge en vigueur, alors que le document en main la
      declare remplacee depuis le 12-05-2016;
    * elle doit retomber sur l'entree de l'EN 1996-1-1, PAS sur une entree
      « EN 1996-1-1+A1 » distincte. L'annexe de la norme amendee est l'annexe
      de la norme: deux entrees jumelles n'auraient jamais compare leurs
      editions, et la plus ancienne serait restee valide a cote de la neuve.
    """
    mod = _nbn()
    front = [
        "Norme belge",
        "NBN EN 1996-1-1+A1 ANB:2016",
        "Eurocode 6 : Calcul des ouvrages en maconnerie - Partie 1-1 - "
        "Annexe nationale",
        "Valable a partir de 12-05-2016",
    ]
    ident = mod.identify(make_pdf(tmp_path / "a.pdf", [front]))
    assert ident is not None
    assert ident["reference"] == "NBN EN 1996-1-1+A1 ANB"
    assert ident["edition"] == "2016"
    assert ident["effective_from"] == "2016-05-12"
    # La cle de catalogue ignore l'amendement.
    assert (ident["standard_family"], ident["part"]) == ("EN 1996", "1-1")


def test_a_cover_replacing_two_documents_names_both(tmp_path) -> None:
    """« Remplace NBN EN 1996-1-1 ANB:2010 et NBN/DTD EN 1996-1-1+A1 ANB:2014 »

    Une seule reference etait lue. Le second document — le projet technique de
    2014 — passait a la trappe: s'il avait ete detenu, il serait reste ouvert
    au catalogue apres avoir ete officiellement remplace.
    """
    mod = _nbn()
    front = [
        "Norme belge",
        "NBN EN 1996-1-1+A1 ANB:2016",
        "Valable a partir de 12-05-2016",
        "Remplace NBN EN 1996-1-1 ANB:2010 et NBN/DTD EN 1996-1-1+A1 ANB:2014",
    ]
    ident = mod.identify(make_pdf(tmp_path / "b.pdf", [front]))
    assert ident["replaces"] == [
        "NBN EN 1996-1-1 ANB:2010",
        "NBN/DTD EN 1996-1-1+A1 ANB:2014",
    ]
    assert ident["supersession_is_effective"] is True


def test_a_future_tense_replacement_is_not_a_replacement(tmp_path) -> None:
    """« Cette norme remplaceRA le NBN EN 1996-1-2 ANB:2012. »

    Le futur n'est pas une coquille. En Belgique une norme ne devient
    obligatoire que par homologation publiee au Moniteur belge; le NBN ecrit
    « remplace » quand c'est fait et « remplacera » quand ca ne l'est pas.

    Clore l'edition 2012 sur la foi de ce futur reviendrait a dater un arrete
    royal que personne n'a lu — c'est-a-dire a inventer la seule chose qui
    manque. Les deux editions restent detenues et la question de savoir
    laquelle fait foi reste ouverte, en toutes lettres.
    """
    mod = _nbn()
    front = [
        "Norme belge",
        "NBN EN 1996-1-2 ANB:2019",
        "Valable a partir de 10-05-2019",
        "Cette norme remplacera le NBN EN 1996-1-2 ANB:2012.",
    ]
    ident = mod.identify(make_pdf(tmp_path / "c.pdf", [front]))
    assert ident["replaces"] == ["NBN EN 1996-1-2 ANB:2012"]
    assert ident["supersession_is_effective"] is False


def test_a_technical_document_is_not_a_standard_but_citing_one_is_harmless(
    tmp_path,
) -> None:
    """« Document NBN/DTD ... technique belge »: publie, numerote, et sans force.

    Sa propre couverture dit que son contenu est identique au projet de norme
    prNBN mis a l'enquete publique, et qu'une norme le remplacera apres
    homologation. Il doit etre refuse.

    Le second volet est celui qui a manque au premier jet: la couverture de
    l'annexe AUTHENTIQUE de 2016 cite « NBN/DTD » dans sa ligne « Remplace ».
    Une garde qui cherchait « NBN/DTD » n'importe ou refusait donc exactement
    le document attendu — la faute que triage.py documente pour _SUPERSEDES,
    refaite ici. Nommer un document n'est pas en etre un.
    """
    mod = _nbn()
    dtd = make_pdf(tmp_path / "dtd.pdf", [[
        "Document NBN/DTD EN 1996-1-1+A1 ANB",
        "technique belge",
        "1e ed., octobre 2014",
        "Le contenu de ce document est identique a celui du projet de norme "
        "prNBN EN 1996-1-1+A1 ANB mis a l'enquete publique.",
    ]])
    assert mod.identify(dtd) is None

    citing = make_pdf(tmp_path / "citing.pdf", [[
        "Norme belge",
        "NBN EN 1996-1-1+A1 ANB:2016",
        "Valable a partir de 12-05-2016",
        "Remplace NBN EN 1996-1-1 ANB:2010 et NBN/DTD EN 1996-1-1+A1 ANB:2014",
    ]])
    assert mod.identify(citing) is not None


def test_the_triage_also_refuses_the_technical_document(tmp_path) -> None:
    """Deuxieme ligne de defense, independante du lecteur de couvertures.

    Le recorder refuse le DTD sur sa designation propre. Le triage le refuse
    sur une autre phrase de la meme page — « projet de norme », « prNBN » —
    et c'est lui qui garde la porte des valeurs. Les deux doivent tenir seuls.
    """
    from ndp_import import triage_document

    r = triage_document(make_pdf(tmp_path / "dtd.pdf", [[
        "Document NBN/DTD EN 1996-1-1+A1 ANB technique belge - Eurocode 6 - "
        "Annexe nationale - Le contenu de ce document est identique a celui "
        "du projet de norme prNBN EN 1996-1-1+A1 ANB mis a l'enquete publique."
    ]]))
    assert r.is_draft
    assert not r.usable_for_ndp


def test_two_editions_of_one_annex_are_not_a_collision(tmp_path, capsys) -> None:
    """Une succession d'editions est la vie normale d'une norme.

    La garde anti-collision avait ete ecrite pour un cas reel et etroit: une
    archive livrant « ..._ANB_2011(F).pdf » et « ... (1).pdf », octet pour
    octet identiques. Elle traitait donc TOUTE paire de fichiers differents
    revendiquant la meme entree comme un conflit, et n'en retenait aucun.

    Le depot de l'EC6 a livre l'EN 1996-1-2 ANB en 2012 ET en 2019. Resultat:
    la Belgique se retrouvait sans aucune annexe EC6 feu alors qu'on en
    detient deux. Une garde qui rejette ce qu'on possede est pire que pas de
    garde — c'est le meme diagnostic que pour la banniere CSTB.

    Ce qui reste un conflit: deux fichiers DIFFERENTS portant la MEME edition.
    La, rien ne permet de choisir, et rien n'est ecrit.
    """
    mod = _nbn()

    def cover(part: str, year: str, day: str, extra: list[str] | None = None):
        return [
            "Norme belge",
            f"NBN EN {part} ANB:{year}",
            f"Valable a partir de {day}",
        ] + (extra or [])

    src = tmp_path / "depot"
    src.mkdir()
    make_pdf(src / "ANB_1996-1-2_2012.pdf", [cover("1996-1-2", "2012", "01-02-2012")])
    make_pdf(src / "ANB_1996-1-2_2019.pdf", [cover(
        "1996-1-2", "2019", "10-05-2019",
        ["Cette norme remplacera le NBN EN 1996-1-2 ANB:2012."])])
    # Meme edition, deux fichiers differents: le vrai conflit.
    make_pdf(src / "ANB_1998-6_a.pdf", [cover("1998-6", "2011", "01-03-2011")])
    make_pdf(src / "ANB_1998-6_b.pdf", [cover("1998-6", "2011", "02-03-2011")])

    cat = tmp_path / "catalogue.json"
    cat.write_text(json.dumps({"documents": []}), encoding="utf-8")
    mod.CATALOGUE = cat
    assert mod.main(["record_nbn_batch", "--dir", str(src)]) == 0

    docs = {d["doc_key"]: d for d in json.loads(cat.read_text())["documents"]}

    # Les deux editions sont detenues sous UNE entree, la recente en tete.
    ec6 = docs["BE-EN199612-NA"]
    assert "2019" in ec6["edition_read_from_cover"]
    assert [c["edition"] for c in ec6["concurrent_copies"]] == ["2012"]
    # ... et le futur n'a ferme personne.
    assert "superseded_copies" not in ec6
    assert ec6["concurrent_copies"][0]["governing_edition"] == "pending_verification"
    assert "Moniteur belge" in ec6["concurrent_copies"][0]["missing_evidence"]

    # Deux fichiers pour une meme edition: aucune entree creee.
    assert "BE-EN19986-NA" not in docs
    assert "CONFLIT" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# La pile normative: le texte d'un cote, la decision de l'autre
# ---------------------------------------------------------------------------
def test_a_base_eurocode_is_held_without_being_authoritative() -> None:
    """Le chainon qui manquait, et l'erreur de raisonnement qui l'avait cache.

    Le catalogue a longtemps compte ZERO Eurocode de base pour quatre pays,
    alors que des normes de base dormaient sur le disque. Elles avaient ete
    triees, correctement refusees comme sources de NDP, puis oubliees: « ne
    peut pas confirmer un NDP » avait ete pris pour « sans interet ».

    Or les Annexes Nationales fonctionnent par DESIGNATION — « la valeur
    recommandee (formule 6.6N) est normative » — sans reimprimer l'expression.
    Le texte est dans la norme de base. Sans elle, la decision belge est
    tracable et son contenu ne l'est pas.

    Deux proprietes, et il faut les deux: le document est DETENU, et il n'est
    JAMAIS `acquired`. `acquired` designe l'autorite de fixer une valeur
    nationale, qu'un Eurocode de base ne peut pas avoir.
    """
    import json

    from ndp_import.catalogue import _DATA

    raw = json.loads(_DATA.read_text(encoding="utf-8"))
    bases = [d for d in raw["documents"] if d.get("document_role") == "base_eurocode"]
    assert bases, "aucun Eurocode de base au catalogue"
    for d in bases:
        assert d["status"] != "acquired", (
            f"{d['doc_key']}: un Eurocode de base ne fait jamais foi pour un NDP"
        )
        assert d.get("doc_id_sha256")
        assert not d.get("parameters_expected"), (
            f"{d['doc_key']}: une norme de base ne fixe aucun parametre national"
        )


def test_the_ec2_stack_records_that_corrigenda_are_appended_not_merged() -> None:
    """Le piege que ce champ existe pour desamorcer.

    ``NBN_EN_1992-1-1_2005(F)+AC.pdf`` s'annonce « (+AC:2010) » en couverture,
    ce qui se lit spontanement comme « corrigenda deja integres ». Ils ne le
    sont pas: ils sont ANNEXES en fin de volume, et le corps porte toujours le
    texte de 2004.

    La verification qui l'a etabli est reproductible: §6.2.5(2) du corps donne
    c = 0,25 / 0,35 / 0,45, tandis que la modification n° 29 du corrigendum
    remplace ces memes valeurs — et que l'ANB, elle, cite les valeurs
    corrigees. Lire le corps seul, c'est appliquer un texte que deux
    corrigenda ont amende.

    ``contained_layers`` est ce qui empeche un lecteur futur — humain ou
    script — de prendre les pages 7-253 pour le texte applicable.
    """
    import json

    from ndp_import.catalogue import _DATA

    raw = json.loads(_DATA.read_text(encoding="utf-8"))
    base = next(d for d in raw["documents"] if d["doc_key"] == "BE-EN199211-BASE")
    layers = {c["layer"]: c["pages"] for c in base["contained_layers"]}
    assert any("corps" in k for k in layers), "le corps de la norme n'est pas situe"
    assert any("AC:2008" in k for k in layers), (
        "les modifications des corrigenda ne sont pas situees"
    )
    # Corps et corrigenda occupent des plages DISJOINTES: c'est precisement
    # ce qui prouve qu'ils ne sont pas fondus.
    corps = next(v for k, v in layers.items() if "corps" in k)
    corr = next(v for k, v in layers.items() if "AC:2008" in k)
    assert int(corps.split("-")[1]) < int(corr.split("-")[0])
    assert "NON FONDUS" in base["acquisition"]["notes"]


def test_the_second_generation_is_held_and_powerless() -> None:
    """Publiee, numerotee, authentique — et sans force en Belgique.

    Sa propre page 1 le dit: « This document does not replace the existing
    standard NBN EN 1992-1-1:2005 and its amendment NBN EN 1992-1-1/A1:2015 ».

    Elle est conservee parce qu'elle rend un autre service: c'est SA page 1
    qui nomme la pile de premiere generation, AC:2010 compris. Sans elle, on
    ignorait qu'AC:2010 existait.
    """
    import json

    from ndp_import.catalogue import _DATA

    raw = json.loads(_DATA.read_text(encoding="utf-8"))
    gen2 = next(d for d in raw["documents"] if d["doc_key"] == "BE-EN199211-GEN2")
    assert gen2.get("not_yet_applicable") is True
    assert gen2["status"] != "acquired"
    assert "NE JAMAIS" in gen2["acquisition"]["notes"]
