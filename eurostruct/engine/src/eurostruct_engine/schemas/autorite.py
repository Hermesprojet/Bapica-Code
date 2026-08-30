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
    "AuthorityDecisionRequest",
    "AuthorityDecisionCreated",
    "AuthorityDecisionConsumed",
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


class AuthorityDecisionCreated(Strict):
    """A decision now exists, and it is PENDING. Nothing is confirmed yet."""

    decision_id: str


class AuthorityDecisionConsumed(Strict):
    """The decision was spent. Exactly once: a replay is refused."""

    decision_id: str
    consumed: bool
