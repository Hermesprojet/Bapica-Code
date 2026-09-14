"""The wire shapes of the four-eyes path. Never an actor, ever.

WHY THESE LIVE IN THE ENGINE AND NOT IN THE HTTP LAYER
------------------------------------------------------
The frontend must not hand-write the shapes it exchanges. That rule already
covers the calculation, because ``export_contracts.py`` emits TypeScript from
the Pydantic models — but the authority payloads were declared inside the
FastAPI route module, which the generator never reads. The browser therefore
had no generated type for them, and any client would have had to *copy* the
shape into TypeScript. A copied shape drifts the day a field is renamed, and
here that field decides who may confirm a national parameter.

The decision itself is a domain concept, not a transport detail: the four-eyes
rule exists to gate NDP confirmations, which is engine territory
(``ndp/confirmation.py``). Declaring the shapes here puts them under the same
generator as everything else, and the API imports them rather than redeclaring.

NO PAYLOAD NAMES AN ACTOR
--------------------------
Not ``actor_id``, not proposer, not approver. Those three come out of the
verified bearer token and nowhere else. A field that accepted them would make
signature verification decorative: it would be enough to lie in the body.
``Strict`` forbids extra fields, so an added ``actor_id`` is a 422 rather than
a silently ignored key.
"""

from __future__ import annotations

from pydantic import Field

from .common import Strict

__all__ = [
    "AuthorityDecisionConsumed",
    "AuthorityDecisionCreated",
    "AuthorityDecisionRequest",
    "AuthorityDecisionReview",
    "AuthorityReviewCitation",
    "AuthorityReviewDossier",
    "AuthorityReviewDraftRequest",
    "AuthorityReviewPackage",
]


class AuthorityReviewPackage(Strict):
    """The dossier the two engineers are shown, frozen at proposal time.

    WHY IT TRAVELS WITH THE PROPOSAL AND NOT WITH THE APPROVAL. "B approved"
    means nothing unless the record says *what* B approved. The dossier is
    written once, at proposal, and PostgreSQL freezes it: A and B therefore
    approve byte-identical content, and the effect produced at consumption is
    that content and no other.

    NO DIGEST IS CARRIED HERE. The server recomputes every one of them from
    the payloads below. Accepting a digest would let a caller announce a
    fingerprint that does not summarise what is stored.
    """

    rule_id: str = Field(
        description="Exact parameter identifier, e.g. 'EN 1992-1-1:alpha_cc'.",
    )
    statement: str = Field(
        description="What the reviewers declare they read and checked.",
    )
    digest_algorithm: str = Field(examples=["sha256"])
    canonicalization_version: str = Field(examples=["esc-canon/1"])
    #: The four canonical payloads. They are the signed material; the server
    #: hashes them itself.
    normative_spec_payload: str
    implementation_payload: str
    evidence_payload: str
    stack_payload: str


class AuthorityDecisionRequest(Strict):
    """What the decision is about. Never who proposes it."""

    subject_kind: str = Field(
        description="Nature of the subject, e.g. 'ndp_parameter'.",
        examples=["ndp_parameter"],
    )
    subject_id: str = Field(
        description="Identifier of the subject the decision bears on.",
        examples=["EN 1992-1-1:alpha_cc"],
    )
    org_id: str | None = Field(
        default=None,
        description="Tenant scope, or null for a referential-wide decision.",
    )
    country_code: str = Field(
        min_length=2, max_length=2,
        description="ISO 3166-1 alpha-2 code of the national annex concerned.",
        examples=["BE"],
    )
    standard_family: str = Field(examples=["EN 1992"])
    part: str = Field(examples=["1-1"])
    edition: str = Field(
        description="Edition of the standard the decision is scoped to.",
        examples=["2004"],
    )
    permission: str = Field(examples=["can_validate_normative_reference"])
    reason: str = Field(
        description="Human-readable motive. A datum, never a proof.",
    )
    review_package: AuthorityReviewPackage | None = Field(
        default=None,
        description=(
            "The dossier presented to both engineers. Required when "
            "subject_kind is 'ndp_parameter': without it the decision could "
            "be approved and consumed without producing any normative effect."
        ),
    )


class AuthorityReviewCitation(Strict):
    """What a named engineer transcribed from the published document.

    THE SERVER CANNOT PRODUCE THIS. Everything else in a dossier is derived
    from the registry — value, unit, provenance, annex reference, edition,
    clause, document digest. The quote is the one thing that only exists
    because somebody opened the annex at that page and read it. Inventing it
    would empty the four-eyes rule of its object.
    """

    document_digest: str = Field(
        description="Which required document this quote covers.",
    )
    quote: str = Field(min_length=1)
    page_printed: int = Field(
        ge=1, description="Printed folio, as it appears on the page itself.",
    )
    page_pdf: int | None = Field(
        default=None, description="PDF page number, when it differs.",
    )


class AuthorityReviewDraftRequest(Strict):
    """Ask the server to compose the dossier of one registry parameter.

    THE CLIENT SUPPLIES PROOF, NEVER SPECIFICATION. It names the parameter and
    hands over the human material — what a person read, where, and what they
    certify. Everything normative is derived server-side:

    * the value, unit, provenance, annex, edition, clause and document digest
      come from the registry;
    * what the clause *does* is a function of those registry fields;
    * the implementation fingerprint is a function of the declared code path
      that reads and applies the rule, plus the engine version.

    ``implementation_note`` AND ``effect`` USED TO BE FIELDS HERE, and both
    fed a canonical payload. Two people describing the same clause differently
    therefore signed two different subjects, and the code could change under a
    confirmation without invalidating it. ``Strict`` forbids extra fields, so
    a client still sending them now gets a 422 rather than a silent effect.
    """

    country_code: str = Field(min_length=2, max_length=2, examples=["BE"])
    rule_id: str = Field(examples=["EN 1992-1-1:alpha_cc"])
    statement: str = Field(
        min_length=1,
        description="What the two reviewers declare they read and checked.",
    )
    citations: list[AuthorityReviewCitation] = Field(
        min_length=1,
        description="One per document the specification declares.",
    )


class AuthorityReviewDossier(Strict):
    """The composed dossier: what to propose, what to show, nothing invented.

    ``package`` is what goes back on the wire at proposal time. ``digests``
    and ``summary`` are for the screen — the browser displays them, it does
    not compute them and has no way to.
    """

    package: AuthorityReviewPackage
    digests: dict[str, str]
    summary: dict[str, object]


class AuthorityDecisionReview(Strict):
    """A frozen decision, read back so the SECOND engineer can judge it.

    NO ACTOR IS RETURNED. B does not need to know who proposed in order to
    judge what was proposed, and PostgreSQL refuses a self-approval by table
    constraint rather than by the caller's prudence. Returning proposer and
    approver would turn a dossier read into a directory of licensed engineers.
    """

    decision_id: str
    state: str
    subject_kind: str
    subject_id: str
    org_id: str | None
    country_code: str
    standard_family: str
    part: str
    edition: str
    permission: str
    reason: str
    proposed_at: str
    package: AuthorityReviewPackage | None = Field(
        default=None,
        description="The frozen dossier. Null only for a non-NDP subject.",
    )
    digests: dict[str, str] = Field(
        default_factory=dict,
        description="Recomputed by the server from the frozen payloads.",
    )


class AuthorityDecisionCreated(Strict):
    """A decision now exists, and it is PENDING. Nothing is confirmed yet."""

    decision_id: str


class AuthorityDecisionConsumed(Strict):
    """The decision was spent. Exactly once: a replay is refused."""

    decision_id: str
    consumed: bool
