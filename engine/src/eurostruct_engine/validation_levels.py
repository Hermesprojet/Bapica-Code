"""The three validations EUROSTRUCT keeps strictly apart.

They are constantly confused, and confusing them is how a deliverable ends up
signed by nobody or blocked by the wrong thing. Each answers a different
question, is performed by a different party, and blocks a different step.

1. :data:`ValidationLevel.NORMATIVE` — *is this number what the country
   adopted?*

   Answered by reading the published National Annex. It concerns the parameter
   set, not the project: ``alpha_cc = 0,85`` is true for every Belgian project
   or for none. Recorded once, per country and per edition, and reused.

   Blocks: reading a national parameter in strict mode.

2. :data:`ValidationLevel.ENGINEERING` — *do I take responsibility for this
   calculation?*

   Answered by the engineer **of the firm using the software**, on this
   project, with their name and the date. Not a third party, and not an
   external certifier: the software does not replace the engineer, it gives
   them something to check and sign. What is required is that the signatory be
   authenticated, active, attached to the project's organisation, and hold a
   role carrying technical validation.

   Blocks: moving a calculation to ``validated``.

3. :data:`ValidationLevel.ISSUANCE` — *may this document leave the building?*

   Answered by the state machine: a deliverable reaches ``final`` only when a
   validation of level 2 is attached and frozen. ``is_final`` is derived from
   the state and never written directly.

   Blocks: emitting the final document.

Why they must not collapse into one
-----------------------------------
Level 1 is a property of the *country*; level 2 of the *project*; level 3 of
the *document*. A firm that has read its National Annexes still has to sign
each study. A signed study still has to be issued deliberately. And a
deliverable can be blocked at level 3 while levels 1 and 2 are complete, which
is a different situation from a study nobody has checked — the user must be
told which.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

__all__ = [
    "ValidationLevel",
    "TECHNICAL_VALIDATION_ROLES",
    "Validator",
    "validator_may_sign",
]


class ValidationLevel(str, Enum):
    """Which of the three gates is being spoken about."""

    #: The national value matches the published annex.
    NORMATIVE = "normative"
    #: A named engineer of the firm takes responsibility for the calculation.
    ENGINEERING = "engineering"
    #: The final document may be emitted.
    ISSUANCE = "issuance"

    @property
    def question(self) -> str:
        return {
            ValidationLevel.NORMATIVE: "cette valeur est-elle bien celle que le pays a adoptee ?",
            ValidationLevel.ENGINEERING: "qui prend la responsabilite de ce calcul ?",
            ValidationLevel.ISSUANCE: "ce document peut-il etre emis ?",
        }[self]

    @property
    def performed_by(self) -> str:
        return {
            ValidationLevel.NORMATIVE: (
                "un relecteur qui ouvre l'Annexe Nationale publiee a la page citee"
            ),
            ValidationLevel.ENGINEERING: (
                "l'ingenieur du bureau d'etudes qui utilise le logiciel, "
                "authentifie, actif et rattache au projet"
            ),
            ValidationLevel.ISSUANCE: (
                "la machine a etats, une fois la validation de niveau 2 attachee"
            ),
        }[self]


#: Roles that carry technical validation. Deliberately narrow: 'owner' and
#: 'admin' are administrative roles and a firm's business owner is not
#: necessarily its responsible engineer. A firm grants 'validating_engineer'
#: to whoever answers for the studies — that is the firm's decision to make,
#: and widening the set here would take it away from them silently.
TECHNICAL_VALIDATION_ROLES: frozenset[str] = frozenset({"validating_engineer"})


@dataclass(frozen=True, slots=True)
class Validator:
    """Who is signing, as the application knows them at signature time."""

    user_id: str
    #: Full name, printed in the note de calcul. An organisation name is not a
    #: signature: a person answers for a study, a legal entity does not read
    #: one.
    full_name: str
    role: str
    #: Organisation the signatory belongs to.
    org_id: str
    #: Whether the membership is still active. A former colleague's account
    #: must not be able to sign, even if the row survives for traceability.
    is_active: bool
    #: Professional registration, where the firm records one. Optional: no
    #: external certification is required by default.
    professional_id: str | None = None


def validator_may_sign(validator: Validator, project_org_id: str) -> tuple[bool, str]:
    """Whether *validator* may perform an ENGINEERING validation on a project.

    Returns ``(allowed, reason)``. The reason is written for the person who
    will read it in the interface, and says what to change.

    This mirrors the database trigger rather than replacing it: the guarantee
    lives in the schema, where the application cannot go around it. Here it is
    so the interface can refuse early, with a sentence rather than a constraint
    violation.
    """
    if not validator.full_name.strip():
        return False, (
            "la signature doit porter un nom de personne. Une raison sociale "
            "ne signe pas une etude: quelqu'un la lit et en repond."
        )
    if validator.org_id != project_org_id:
        return False, (
            "le signataire n'appartient pas a l'organisation du projet. La "
            "validation revient au bureau d'etudes qui realise l'etude."
        )
    if not validator.is_active:
        return False, (
            "le compte du signataire n'est plus actif dans l'organisation. Un "
            "acces revoque ne peut plus engager le bureau d'etudes."
        )
    if validator.role not in TECHNICAL_VALIDATION_ROLES:
        return False, (
            f"le role '{validator.role}' ne porte pas la validation technique. "
            f"Role(s) habilite(s): {', '.join(sorted(TECHNICAL_VALIDATION_ROLES))}. "
            "L'organisation attribue ce role a l'ingenieur qui repond de ses "
            "etudes."
        )
    return True, "signature autorisee"
