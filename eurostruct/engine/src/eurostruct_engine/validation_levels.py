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
from typing import Final

__all__ = [
    "ValidationLevel",
    "TECHNICAL_VALIDATION_ROLES",
    "PLATFORM_ROLES",
    "CAN_VALIDATE_NORMATIVE_REFERENCE",
    "NORMATIVE_MAINTENANCE_ROLES",
    "verifier_may_validate_reference",
    "ProjectValidatingEngineer",
    "Validator",
    "NormativeVerifier",
    "NormativeValidation",
    "validator_may_sign",
    "normative_validation_applies",
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

#: Roles belonging to the platform itself, never to a client firm. They are
#: refused outright at level 2, ahead of every other check.
#:
#: This is a product decision written into the code: the owner of EUROSTRUCT
#: must never be the technical validator of a study produced by a client's
#: engineering firm. Their account carries no professional liability for that
#: firm's work, and a system that let it sign would place liability where it
#: does not belong — silently, and by default, on whoever installed the
#: software.
#:
#: The organisation check below would catch most of these already. This set
#: catches the rest: a platform operator who has been added to a client
#: organisation for support purposes still may not sign its studies.
PLATFORM_ROLES: frozenset[str] = frozenset(
    {"platform_owner", "platform_admin", "superuser", "support"}
)


#: The one authorisation that lets someone confirm a value of the normative
#: reference. Deliberately its own name rather than a role: it grants exactly
#: this and nothing adjacent.
#:
#: « Sans organisation ni role » described what a normative verifier does NOT
#: need — a client firm, a project. It never meant that any identified person
#: may confirm the reference. The reference is shared by every tenant: a wrong
#: reading of ``gamma_C`` propagates to every Belgian study on the platform at
#: once, which is a far wider blast radius than any single project signature.
CAN_VALIDATE_NORMATIVE_REFERENCE: Final[str] = "can_validate_normative_reference"

#: Roles carrying that authorisation. Maintenance of the normative reference,
#: and strictly nothing else — holding it grants no access to any client
#: project and no ability to sign one.
NORMATIVE_MAINTENANCE_ROLES: frozenset[str] = frozenset(
    {"normative_maintainer", "normative_reviewer"}
)


@dataclass(frozen=True, slots=True)
class NormativeVerifier:
    """Level 1. Who read the published National Annex, and answers for it.

    Deliberately a *different type* from the level-2 signatory, not a flag on
    a shared one. The two answer different questions, and a single ``verified_by``
    field serving both is how a normative reading gets mistaken for a
    professional endorsement of a project.

    A normative verifier needs no organisation and no project: reading
    ``NBN EN 1992-1-1 ANB §3.1.6(1)P`` is true for every Belgian project or for
    none. What they need is a name and a date, because someone must answer for
    "I opened the annex at that page and this is what it says".
    """

    verifier_id: str
    #: Printed beside the value in the parameter report. A person, not a firm.
    full_name: str
    #: ISO date of the reading.
    verified_at: str
    #: Authorisations held. Confirming the reference requires
    #: :data:`CAN_VALIDATE_NORMATIVE_REFERENCE` to be among them.
    authorisations: frozenset[str] = frozenset()
    #: Whether the account is still active. A departed maintainer must not be
    #: able to confirm, even though past confirmations stay valid and readable.
    is_active: bool = True


def verifier_may_validate_reference(
    verifier: NormativeVerifier,
) -> tuple[bool, str]:
    """Whether *verifier* may confirm a value of the normative reference.

    Returns ``(allowed, reason)``.

    What this authorisation does **not** do, and the reason it is separate
    from every role in :data:`TECHNICAL_VALIDATION_ROLES`:

    * it never allows signing a project — that is level 2, and it belongs to
      the client firm's engineer;
    * it carries no responsibility for any client study;
    * it grants no access to project data.

    The asymmetry is deliberate. A project signature engages one study and one
    firm. A confirmation of the reference engages *every* study of that
    jurisdiction, on every tenant, at once — so the gate is narrower, not
    wider, than the one on signatures.
    """
    if not verifier.full_name.strip():
        return False, (
            "une lecture d'annexe se signe. Un identifiant technique ne repond "
            "de rien: il faut un nom de personne."
        )
    if not verifier.is_active:
        return False, (
            "le compte du relecteur n'est plus actif. Les confirmations "
            "passees restent valides et lisibles — elles ont ete faites — "
            "mais il ne peut plus en produire de nouvelles."
        )
    if CAN_VALIDATE_NORMATIVE_REFERENCE not in verifier.authorisations:
        return False, (
            f"autorisation '{CAN_VALIDATE_NORMATIVE_REFERENCE}' absente. "
            "Etre identifie ne suffit pas a confirmer le referentiel: une "
            "valeur nationale erronee se propage a TOUTES les etudes de la "
            "juridiction, sur tous les locataires, d'un seul coup. Cette "
            "autorisation se donne a la maintenance normative et a elle seule."
        )
    return True, "validation normative autorisee"


@dataclass(frozen=True, slots=True)
class NormativeValidation:
    """A level-1 validation, bound to ONE edition of ONE annex.

    The binding is the whole point. A reading of the December 2010 edition of
    ``NBN EN 1993-1-1 ANB`` says nothing about the 2018 edition: the verifier
    never saw it, and a new edition exists precisely because something changed.

    Carrying the validation across editions would let a value be presented as
    verified against a document nobody read. That failure has a name in this
    project — it is what the catalogue's ``superseded_copies`` machinery exists
    to prevent on the document side, and this is the same rule on the parameter
    side.
    """

    country_code: str
    standard_family: str
    part: str
    #: The edition READ. Not the entry, not the reference — the edition.
    edition: str
    parameter_name: str
    verifier: NormativeVerifier
    #: sha256 of the file that was on the verifier's screen.
    source_doc_id: str
    source_page: int


def normative_validation_applies(
    validation: NormativeValidation,
    *,
    country_code: str,
    standard_family: str,
    part: str,
    edition: str,
) -> tuple[bool, str]:
    """Whether *validation* covers this exact (country, standard, edition).

    Returns ``(applies, reason)``. Equality on all four, edition included:
    there is no inheritance, no "close enough", no most-recent-wins.
    """
    if validation.country_code != country_code:
        return False, (
            f"validation etablie pour {validation.country_code}, demandee pour "
            f"{country_code}. Un parametre national ne traverse pas une frontiere."
        )
    if (validation.standard_family, validation.part) != (standard_family, part):
        return False, (
            f"validation etablie pour {validation.standard_family}-{validation.part}, "
            f"demandee pour {standard_family}-{part}."
        )
    if validation.parameter_name and validation.edition != edition:
        return False, (
            f"validation etablie sur l'edition {validation.edition}, demandee pour "
            f"l'edition {edition}. Une validation normative ne s'herite JAMAIS "
            f"d'une edition a la suivante: {validation.verifier.full_name} a lu "
            f"{validation.edition}, pas {edition}. Une nouvelle edition existe "
            "parce que quelque chose a change; il faut la relire."
        )
    return True, "validation applicable"


@dataclass(frozen=True, slots=True)
class ProjectValidatingEngineer:
    """Level 2. Who signs the study, as the application knows them.

    The engineer **of the client firm**, on this project. Never the platform,
    never a third-party certifier: the software does not replace the engineer,
    it gives them something to check and sign.
    """

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


#: L'ancien nom, conserve pour ne pas casser les appelants. Le nouveau dit
#: lequel des trois niveaux il porte, ce que « Validator » ne disait pas.
Validator = ProjectValidatingEngineer


def validator_may_sign(
    validator: ProjectValidatingEngineer, project_org_id: str
) -> tuple[bool, str]:
    """Whether *validator* may perform an ENGINEERING validation on a project.

    Returns ``(allowed, reason)``. The reason is written for the person who
    will read it in the interface, and says what to change.

    This mirrors the database trigger rather than replacing it: the guarantee
    lives in the schema, where the application cannot go around it. Here it is
    so the interface can refuse early, with a sentence rather than a constraint
    violation.
    """
    if isinstance(validator, NormativeVerifier):  # pragma: no cover - garde de type
        return False, (
            "un verificateur normatif n'est pas un signataire de projet. Avoir "
            "lu l'Annexe Nationale ne fait prendre la responsabilite d'aucune "
            "etude: ce sont deux niveaux distincts, portes par deux personnes "
            "qui peuvent n'avoir aucun rapport."
        )
    if validator.role in PLATFORM_ROLES:
        return False, (
            f"le role '{validator.role}' appartient a la plateforme, pas au "
            "bureau d'etudes. L'exploitant du logiciel ne peut jamais valider "
            "techniquement l'etude d'un client: il n'en repond pas "
            "professionnellement. La validation appartient au bureau d'etudes "
            "qui realise l'etude et a son ingenieur responsable."
        )
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
