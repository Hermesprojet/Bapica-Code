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


# ---------------------------------------------------------------------------
# Niveau 1 et niveau 2 sont deux personnes, pas un champ partage
# ---------------------------------------------------------------------------
def test_a_normative_reading_is_bound_to_one_edition() -> None:
    """Une validation normative ne s'herite JAMAIS d'une edition a la suivante.

    Le cas est reel et il attendait: l'archive du 15/08 apporte
    ``NBN EN 1993-1-1 ANB:2018``, qui remplace l'edition de decembre 2010 —
    laquelle porte onze parametres et le statut le plus eleve du catalogue.

    Faire heriter la validation aurait presente comme verifiees des valeurs
    lues dans un document que personne n'a ouvert. Une nouvelle edition existe
    justement parce que quelque chose a change.
    """
    from eurostruct_engine.validation_levels import (
        NormativeValidation,
        NormativeVerifier,
        normative_validation_applies,
    )

    v = NormativeValidation(
        country_code="BE", standard_family="EN 1993", part="1-1",
        edition="1e ed., decembre 2010", parameter_name="gamma_M0",
        verifier=NormativeVerifier("u1", "Relecteur Test", "2026-08-15"),
        source_doc_id="a" * 64, source_page=12,
    )

    ok, why = normative_validation_applies(
        v, country_code="BE", standard_family="EN 1993", part="1-1",
        edition="1e ed., decembre 2010",
    )
    assert ok, why

    ok, why = normative_validation_applies(
        v, country_code="BE", standard_family="EN 1993", part="1-1",
        edition="2018",
    )
    assert not ok
    assert "JAMAIS" in why and "2018" in why


def test_a_normative_reading_does_not_cross_a_border_or_a_part() -> None:
    """Meme parametre, autre pays ou autre partie: autre lecture."""
    from eurostruct_engine.validation_levels import (
        NormativeValidation,
        NormativeVerifier,
        normative_validation_applies,
    )

    v = NormativeValidation(
        country_code="BE", standard_family="EN 1992", part="1-1",
        edition="2010", parameter_name="alpha_cc",
        verifier=NormativeVerifier("u1", "Relecteur Test", "2026-08-15"),
        source_doc_id="b" * 64, source_page=10,
    )
    assert not normative_validation_applies(
        v, country_code="FR", standard_family="EN 1992", part="1-1",
        edition="2010")[0]
    assert not normative_validation_applies(
        v, country_code="BE", standard_family="EN 1992", part="1-2",
        edition="2010")[0]


def test_the_platform_can_never_sign_a_client_study() -> None:
    """Decision produit, ecrite dans le code plutot que dans une politique.

    L'exploitant de la plateforme ne repond pas professionnellement des etudes
    d'un bureau d'etudes client. Un systeme qui laisserait son compte signer
    placerait la responsabilite chez celui qui a installe le logiciel — en
    silence, et par defaut.

    Le controle d'organisation attrape deja le cas courant. Celui-ci attrape
    le reste: un exploitant ajoute a l'organisation d'un client pour du
    support ne signe toujours pas ses etudes.
    """
    from eurostruct_engine.validation_levels import (
        ProjectValidatingEngineer,
        validator_may_sign,
    )

    exploitant = ProjectValidatingEngineer(
        user_id="p1", full_name="Exploitant Plateforme", role="platform_owner",
        org_id="ORG-CLIENT", is_active=True,   # meme organisation, exprès
    )
    ok, why = validator_may_sign(exploitant, "ORG-CLIENT")
    assert not ok
    assert "plateforme" in why and "bureau d'etudes" in why


def test_a_normative_verifier_is_not_a_project_signatory() -> None:
    """Deux types distincts, et non un drapeau sur un type partage.

    Avoir lu l'Annexe Nationale ne fait prendre la responsabilite d'aucune
    etude. Les deux roles peuvent etre tenus par deux personnes qui n'ont
    aucun rapport, et le modele doit rendre la confusion impossible plutot que
    la deconseiller.
    """
    from eurostruct_engine.validation_levels import (
        NormativeVerifier,
        ProjectValidatingEngineer,
    )

    assert NormativeVerifier is not ProjectValidatingEngineer
    champs_normatif = set(NormativeVerifier.__dataclass_fields__)
    champs_projet = set(ProjectValidatingEngineer.__dataclass_fields__)
    # Le verificateur normatif n'a NI organisation NI role: sa lecture ne
    # depend d'aucun projet et n'engage aucun bureau d'etudes.
    assert "org_id" not in champs_normatif
    assert "role" not in champs_normatif
    assert {"org_id", "role", "is_active"} <= champs_projet
