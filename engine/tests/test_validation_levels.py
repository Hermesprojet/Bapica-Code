"""The three validations, and who may perform the second one.

The rule under test: nominative human validation belongs to the engineering
firm **using** the software. No external certifier is required. What is
required is that the signatory be authenticated, active, attached to the
project's organisation, and hold a role carrying technical validation.
"""

from __future__ import annotations

import pytest

from eurostruct_engine.validation_levels import (
    TECHNICAL_VALIDATION_ROLES,
    ValidationLevel,
    Validator,
    validator_may_sign,
)

ORG = "org-1"


def _validator(**kw) -> Validator:
    base = dict(
        user_id="u-1", full_name="C. Meunier", role="validating_engineer",
        org_id=ORG, is_active=True, professional_id="BE-ING-4471",
    )
    base.update(kw)
    return Validator(**base)


# ---------------------------------------------------------------------------
# The three levels are distinct, and say so
# ---------------------------------------------------------------------------
def test_the_three_levels_are_named_and_distinct() -> None:
    assert [lv.value for lv in ValidationLevel] == [
        "normative", "engineering", "issuance",
    ]
    questions = {lv.question for lv in ValidationLevel}
    assert len(questions) == 3


def test_each_level_says_who_performs_it() -> None:
    """Confusing the three is how a deliverable gets blocked by the wrong thing."""
    assert "Annexe Nationale" in ValidationLevel.NORMATIVE.performed_by
    # Niveau 2: l'ingenieur du bureau d'etudes, pas un tiers.
    assert "bureau d'etudes" in ValidationLevel.ENGINEERING.performed_by
    assert "machine a etats" in ValidationLevel.ISSUANCE.performed_by


# ---------------------------------------------------------------------------
# Who may sign — level 2
# ---------------------------------------------------------------------------
def test_the_firms_own_engineer_may_sign() -> None:
    """The central point: no external third party is required."""
    allowed, reason = validator_may_sign(_validator(), ORG)
    assert allowed, reason


def test_no_professional_registration_is_required_by_default() -> None:
    """A firm may record one; the software does not demand it."""
    allowed, _ = validator_may_sign(_validator(professional_id=None), ORG)
    assert allowed


def test_a_signatory_from_another_organisation_is_refused() -> None:
    allowed, reason = validator_may_sign(_validator(org_id="org-2"), ORG)
    assert not allowed
    assert "n'appartient pas a l'organisation du projet" in reason


def test_a_deactivated_member_may_not_sign() -> None:
    """The row survives for traceability; the right to sign does not."""
    allowed, reason = validator_may_sign(_validator(is_active=False), ORG)
    assert not allowed
    assert "n'est plus actif" in reason


@pytest.mark.parametrize("role", ["viewer", "engineer", "admin", "owner"])
def test_a_role_without_technical_validation_is_refused(role: str) -> None:
    """'owner' and 'admin' are administrative: a business owner is not the
    firm's responsible engineer, and widening the set here would take that
    decision away from the firm."""
    allowed, reason = validator_may_sign(_validator(role=role), ORG)
    assert not allowed
    assert "ne porte pas la validation technique" in reason
    assert role not in TECHNICAL_VALIDATION_ROLES


def test_an_organisation_name_is_not_a_signature() -> None:
    """A legal entity does not read a study; a person does.

    This is why 'Bureau de Normalisation' was refused as a verifier — not
    because it was external, but because it is not somebody.
    """
    allowed, reason = validator_may_sign(_validator(full_name="   "), ORG)
    assert not allowed
    assert "nom de personne" in reason
