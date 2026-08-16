"""Confirmation normative — modèle de domaine immuable (jalon 6.3a).

Ce module ne connaît **aucune base de données**. Il porte les objets et le
comportement ; le stockage viendra en 6.3b, le mode strict plus tard encore.

Ce qu'une confirmation est, et ce qu'elle n'est pas
----------------------------------------------------
Une confirmation atteste qu'une personne nommée a **lu une annexe nationale**
et reconnaît que telle règle transcrite dit bien ce que le document dit. C'est
une validation de **niveau 1**, normative.

Ce n'est **pas** une validation de projet. Aucun champ ne rattache une
confirmation à un client, à un bureau d'études ou à une étude : la lecture de
``NBN EN 1992-1-1 ANB §6.2.2`` est vraie pour tous les projets belges ou pour
aucun. Un ``project_id`` ici ferait glisser une lecture d'annexe vers un
engagement professionnel sur une étude, et le propriétaire de la plateforme
n'est le responsable technique d'aucun projet client.

Trois empreintes, trois échecs distincts
-----------------------------------------
Une confirmation porte les trois empreintes **complètes** (payload compris),
parce qu'elles ne se périment pas pour les mêmes raisons :

``normative_spec`` change
    le pays prescrit autre chose — il faut **rouvrir l'annexe** ;
``implementation`` change
    le code a changé sans que la prescription bouge — il faut **comprendre
    pourquoi le code a changé** ;
``evidence`` change
    la preuve a été retouchée après signature.

Les confondre ferait chercher un défaut de code là où il faut ouvrir un
document.

Immuabilité
-----------
Tout est ``frozen``. Une confirmation ne se modifie jamais : ni pour la
révoquer, ni pour la corriger. Une révocation est un **événement séparé** qui
la référence. Il n'existe volontairement aucun champ ``is_revoked`` sur la
confirmation — un booléen mutable sur un enregistrement signé est précisément
ce qu'une piste d'audit ne doit pas avoir.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import date, datetime
from enum import Enum
from typing import Any, ClassVar, Protocol, runtime_checkable

from ..exceptions import EurostructEngineError
from .canonical import Digest, EvidenceItem, digest_of

__all__ = [
    "FICTIONAL_PREFIX",
    "FORBIDDEN_FIELD_FRAGMENTS",
    "ConfirmationAssessment",
    "ConfirmationDomainError",
    "ConfirmationPolicy",
    "ConfirmationProvider",
    "ConfirmationStatus",
    "ConfirmationSubjectKey",
    "InMemoryConfirmationProvider",
    "NormativeContext",
    "NormativeRuleConfirmation",
    "NormativeRuleConfirmationRevocation",
    "NormativeStack",
    "NormativeStackComponent",
    "ReviewerAttestationKey",
    "assert_provider_is_usable_in_production",
    "assess_confirmations",
    "independent_regards",
]


class ConfirmationDomainError(EurostructEngineError):
    """Un invariant du modèle de confirmation est violé.

    Levée à la **construction**. Un objet de ce module n'existe pas dans un
    état invalide : il n'y a donc pas de chemin où un appelant oublierait de
    vérifier.
    """


# ---------------------------------------------------------------------------
# Garde-fous partagés
# ---------------------------------------------------------------------------
def _exige_texte(valeur: str, quoi: str) -> str:
    if not isinstance(valeur, str) or not valeur.strip():
        raise ConfirmationDomainError(
            f"{quoi}: une chaine non vide est requise. Une piste d'audit dont "
            "un champ est vide ne prouve rien."
        )
    return valeur


def _exige_tuple(valeur: Any, quoi: str) -> tuple:
    """``frozen=True`` gèle l'attribut, pas ce qu'il contient.

    Un champ déclaré ``tuple`` mais reçu en ``list`` resterait modifiable après
    construction, et l'objet se présenterait comme immuable en ne l'étant pas.
    """
    if not isinstance(valeur, tuple):
        raise ConfirmationDomainError(
            f"{quoi}: un tuple est requis, recu {type(valeur).__name__}. "
            "`frozen` gele l'attribut, pas le contenu d'une liste."
        )
    return valeur


def _exige_frozenset(valeur: Any, quoi: str) -> frozenset:
    if not isinstance(valeur, frozenset):
        raise ConfirmationDomainError(
            f"{quoi}: un frozenset est requis, recu {type(valeur).__name__}."
        )
    return valeur


def _exige_instant_date(valeur: Any, quoi: str) -> datetime:
    """Un horodatage **doit** porter son fuseau.

    « 14:00 » sans fuseau n'est pas un instant : c'est une heure murale, dont
    la signification dépend d'où était la machine. Une confirmation est datée
    pour dix ans, relue depuis un autre pays, parfois après un changement
    d'heure — et l'ordre entre deux confirmations doit rester déterminable.
    """
    if not isinstance(valeur, datetime):
        raise ConfirmationDomainError(
            f"{quoi}: un datetime est requis, recu {type(valeur).__name__}. "
            "Une chaine ISO se relit differemment selon la bibliotheque qui "
            "la lit."
        )
    if valeur.tzinfo is None or valeur.tzinfo.utcoffset(valeur) is None:
        raise ConfirmationDomainError(
            f"{quoi}: horodatage sans fuseau ({valeur.isoformat()}). Une heure "
            "murale n'est pas un instant: relue ailleurs, ou apres un "
            "changement d'heure, elle ne designe plus le meme moment et "
            "l'ordre entre deux confirmations devient indeterminable."
        )
    return valeur


#: Fragments interdits dans un nom de champ. Le modèle de niveau 1 ne doit
#: offrir **aucune prise** pour rattacher une confirmation à un client.
#: Vérifié structurellement par un test, sur chaque objet du module.
FORBIDDEN_FIELD_FRAGMENTS: frozenset[str] = frozenset({
    "project", "projet", "org_id", "organisation_id", "organization_id",
    "tenant", "client", "study", "etude", "dossier",
})


# ---------------------------------------------------------------------------
# La pile normative
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class NormativeStackComponent:
    """Un étage de la pile : base, corrigendum, amendement, annexe, règlement.

    ``application_order`` est **normatif** : un corrigendum appliqué après
    l'annexe ne donne pas le même texte qu'appliqué avant.
    """

    role: str
    reference: str
    edition: str
    application_order: int
    document_digest: str

    #: Les rôles que la pile connaît. Fermé délibérément : un rôle libre
    #: laisserait deux orthographes du même étage produire deux piles réputées
    #: différentes, donc deux confirmations incompatibles sans raison.
    ROLES: ClassVar[frozenset[str]] = frozenset({
        "base", "corrigendum", "amendement", "annexe", "reglement",
    })

    def __post_init__(self) -> None:
        if self.role not in self.ROLES:
            raise ConfirmationDomainError(
                f"role de pile '{self.role}' inconnu. Connus: "
                f"{sorted(self.ROLES)}."
            )
        _exige_texte(self.reference, "reference du composant")
        _exige_texte(self.edition, "edition du composant")
        _exige_texte(self.document_digest, "empreinte du document")
        if not isinstance(self.application_order, int) or isinstance(
            self.application_order, bool
        ):
            raise ConfirmationDomainError(
                "application_order: un entier est requis."
            )


@dataclass(frozen=True, slots=True)
class NormativeStack:
    """Snapshot **structuré** de la pile applicable, avec son empreinte.

    Structuré et non « tableau de chaînes » : dans un tableau, le sens d'un
    élément dépend de sa position, et personne ne s'en aperçoit quand la
    position change.

    ``digest`` est ``init=False`` : il est **calculé depuis la structure**, et
    un appelant ne peut donc pas fournir une empreinte qui ne correspond pas à
    ce qu'elle prétend résumer.
    """

    schema_version: str
    country_code: str
    standard_family: str
    part: str
    components: tuple[NormativeStackComponent, ...]
    digest: Digest = field(init=False, compare=True)

    SCHEMA_VERSION: ClassVar[str] = "esc-stack/1"

    def __post_init__(self) -> None:
        _exige_texte(self.schema_version, "schema_version de la pile")
        _exige_texte(self.country_code, "country_code de la pile")
        _exige_texte(self.standard_family, "standard_family de la pile")
        _exige_texte(self.part, "part de la pile")
        _exige_tuple(self.components, "components de la pile")
        if not self.components:
            raise ConfirmationDomainError(
                "une pile normative sans aucun composant n'atteste rien: au "
                "minimum la norme de base."
            )

        ordres = [c.application_order for c in self.components]
        if len(set(ordres)) != len(ordres):
            raise ConfirmationDomainError(
                f"deux composants portent le meme application_order {ordres}. "
                "L'ordre d'application est normatif: deux etages ex aequo "
                "rendent la pile ambigue."
            )
        if ordres != sorted(ordres):
            raise ConfirmationDomainError(
                f"les composants ne sont pas dans l'ordre d'application "
                f"{ordres}. Les ranger a la lecture masquerait une pile mal "
                "construite: on refuse a la construction."
            )

        object.__setattr__(self, "digest", digest_of({
            "kind": "normative_stack",
            "schema_version": self.schema_version,
            "country_code": self.country_code,
            "standard_family": self.standard_family,
            "part": self.part,
            "components": [
                {
                    "role": c.role,
                    "reference": c.reference,
                    "edition": c.edition,
                    "application_order": c.application_order,
                    "document_digest": c.document_digest,
                }
                for c in self.components
            ],
        }))

    @classmethod
    def of(
        cls, *, country_code: str, standard_family: str, part: str,
        components: tuple[NormativeStackComponent, ...],
    ) -> NormativeStack:
        """Construire avec la version de schéma courante."""
        return cls(
            schema_version=cls.SCHEMA_VERSION,
            country_code=country_code,
            standard_family=standard_family,
            part=part,
            components=components,
        )


@dataclass(frozen=True, slots=True)
class NormativeContext:
    """Ce que la **couche applicative** fournit au calcul.

    Le moteur ne le fabrique pas et ne consulte jamais le catalogue : il n'a ni
    la connaissance ni la légitimité de décider qu'une pile est applicable à un
    projet. Il reçoit la pile demandée et se contente de **comparer**.

    Ni ``project_id`` ni ``org_id`` : la pile applicable est une propriété de
    la juridiction et de la date, pas du client.
    """

    stack: NormativeStack
    as_of: date
    strict: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.stack, NormativeStack):
            raise ConfirmationDomainError(
                "le contexte doit porter une NormativeStack structuree."
            )
        if not isinstance(self.as_of, date) or isinstance(self.as_of, datetime):
            raise ConfirmationDomainError(
                "as_of: une date (sans heure) est requise. La pile applicable "
                "a un projet se determine au jour, pas a la seconde."
            )
        if not isinstance(self.strict, bool):
            raise ConfirmationDomainError("strict: un booleen est requis.")


# ---------------------------------------------------------------------------
# Les trois clés, et ce que chacune identifie
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class ConfirmationSubjectKey:
    """**L'objet exact** que deux vérificateurs doivent confirmer ensemble.

    Huit composantes, et aucune n'est décorative. Elles répondent chacune à une
    façon différente pour deux confirmations de **ne pas porter sur la même
    chose** :

    ``country_code``, ``standard_family``, ``part``, ``rule_id``
        de quelle règle on parle ;
    ``stack_digest``
        sous quelle pile — la même règle confirmée pour l'édition 2010 et pour
        l'édition 2018 fait **deux sujets**, tous deux légitimes ;
    ``normative_spec_digest``
        ce que le pays prescrit ;
    ``implementation_digest``
        quel code l'exécute ;
    ``evidence_digest``
        **quel dossier de preuve** a été lu. Deux relecteurs qui n'ont pas
        ouvert les mêmes pages n'ont pas exercé deux regards sur la même chose.

    Un tuple nommé plutôt qu'un tuple positionnel : c'est la même raison qui
    fait que :class:`NormativeStack` est structurée. Dans un tuple positionnel,
    le sens d'une composante dépend de sa place, et personne ne s'en aperçoit
    quand la place change.
    """

    country_code: str
    standard_family: str
    part: str
    rule_id: str
    stack_digest: str
    normative_spec_digest: str
    implementation_digest: str
    evidence_digest: str

    #: Ce que la clé DOIT contenir. Vérifié par un test : une clé de sujet à
    #: qui il manque une composante est exactement le défaut que ce correctif
    #: existe pour supprimer.
    REQUIRED_COMPONENTS: ClassVar[tuple[str, ...]] = (
        "country_code", "standard_family", "part", "rule_id", "stack_digest",
        "normative_spec_digest", "implementation_digest", "evidence_digest",
    )


@dataclass(frozen=True, slots=True)
class ReviewerAttestationKey:
    """**Le regard d'une personne** sur un sujet exact.

    ``confirmation_subject_key + verifier_id``. C'est l'unité du décompte à
    quatre yeux : deux lignes de même clé d'attestation sont **le même
    regard**, quel que soit leur nombre.

    La clé d'idempotence n'y entre pas, et c'est tout l'objet de la distinction
    : deux envois distincts d'une même lecture — un rejeu réseau, un
    double-clic — ne font pas deux relecteurs.
    """

    subject: ConfirmationSubjectKey
    verifier_id: str


# ---------------------------------------------------------------------------
# La confirmation
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class NormativeRuleConfirmation:
    """« J'ai ouvert l'annexe à cette page, et cette règle dit bien ceci. »

    Immuable, et sans aucun champ mutable — pas de ``is_revoked``. Se révoquer
    n'est pas se modifier : voir :class:`NormativeRuleConfirmationRevocation`.
    """

    confirmation_id: str

    # --- quelle règle, dans quelle pile -----------------------------------
    country_code: str
    standard_family: str
    part: str
    rule_id: str

    # --- les trois empreintes, payload conservé ---------------------------
    normative_spec: Digest
    implementation: Digest
    evidence: Digest

    # --- la pile attestée, structurée -------------------------------------
    stack: NormativeStack

    # --- qui, quand -------------------------------------------------------
    verifier_id: str
    #: Lisible dans dix ans. Une personne, pas un identifiant technique.
    verifier_name: str
    #: Instant **avec fuseau**. Voir :func:`_exige_instant_date`.
    verified_at: datetime

    #: Écrits par le serveur depuis la table des autorisations, JAMAIS fournis
    #: par l'appelant. C'est une **preuve d'audit**, pas un contrôle d'accès :
    #: un tableau fourni par l'acteur et vérifié pour sa seule présence
    #: laisserait cet acteur se déclarer lui-même autorisé.
    authorisations_at_signature: frozenset[str]
    authorisation_scope_at_signature: str

    # --- ce qui a été lu : le DOSSIER, partagé -----------------------------
    #: Le dossier canonique de preuve. Pour satisfaire le contrôle à quatre
    #: yeux, les deux vérificateurs doivent avoir reçu et confirmé **le même**
    #: : mêmes documents, mêmes empreintes, mêmes rôles documentaires, mêmes
    #: clauses, mêmes folios imprimés, mêmes citations normatives. C'est
    #: exactement ce que scelle ``evidence`` — et ``page_pdf``, simple aide de
    #: navigation, en est exclu.
    evidence_items: tuple[EvidenceItem, ...]

    # --- ce qu'il en dit : la DÉCLARATION, personnelle ---------------------
    #: Sa phrase, pas un gabarit pré-rempli qu'il aurait suffi de cocher.
    #:
    #: **Elle n'entre dans aucune clé et ne modifie aucune empreinte.** Deux
    #: relecteurs qui ont lu le même dossier et le commentent différemment ont
    #: bien exercé deux regards sur la même chose : faire dépendre le sujet de
    #: leur formulation rendrait le double contrôle inatteignable en pratique,
    #: puisque deux personnes n'écrivent jamais la même phrase.
    statement: str

    #: Clé d'idempotence **technique**, distincte de l'identité normative.
    #: Elle empêche qu'un envoi rejoué crée deux lignes ; elle ne dit rien du
    #: nombre de regards. Voir :meth:`normative_identity`.
    idempotency_key: str

    #: Audit seulement. N'ouvre aucun droit sur un projet et n'est lue par
    #: aucun contrôle.
    verifier_affiliation: str | None = None

    def __post_init__(self) -> None:
        for nom in ("confirmation_id", "country_code", "standard_family",
                    "part", "rule_id", "verifier_id", "verifier_name",
                    "authorisation_scope_at_signature", "idempotency_key"):
            _exige_texte(getattr(self, nom), nom)

        for nom in ("normative_spec", "implementation", "evidence"):
            valeur = getattr(self, nom)
            if not isinstance(valeur, Digest):
                raise ConfirmationDomainError(
                    f"{nom}: un Digest complet est requis, recu "
                    f"{type(valeur).__name__}. Une empreinte reduite a sa "
                    "chaine perd son payload, donc ce qui a ete signe."
                )

        if not isinstance(self.stack, NormativeStack):
            raise ConfirmationDomainError(
                "stack: un snapshot structure est requis."
            )
        _exige_instant_date(self.verified_at, "verified_at")
        _exige_frozenset(
            self.authorisations_at_signature, "authorisations_at_signature"
        )
        _exige_tuple(self.evidence_items, "evidence_items")
        if not self.evidence_items:
            raise ConfirmationDomainError(
                "aucun element de preuve. Confirmer sans dire ce qu'on a lu "
                "n'est pas une lecture d'annexe."
            )
        _exige_texte(self.statement, "statement")

        if self.stack.country_code != self.country_code:
            raise ConfirmationDomainError(
                f"la confirmation dit '{self.country_code}' et sa pile "
                f"'{self.stack.country_code}'. Une confirmation atteste une "
                "pile: les deux ne peuvent pas designer deux juridictions."
            )

    @property
    def confirmation_subject_key(self) -> ConfirmationSubjectKey:
        """**L'objet exact** que deux vérificateurs doivent confirmer ensemble."""
        return ConfirmationSubjectKey(
            country_code=self.country_code,
            standard_family=self.standard_family,
            part=self.part,
            rule_id=self.rule_id,
            stack_digest=self.stack.digest.digest,
            normative_spec_digest=self.normative_spec.digest,
            implementation_digest=self.implementation.digest,
            evidence_digest=self.evidence.digest,
        )

    @property
    def reviewer_attestation_key(self) -> ReviewerAttestationKey:
        """**Le regard d'une personne** sur ce sujet exact.

        C'est la clé du décompte à quatre yeux : deux lignes de même clé
        d'attestation sont le même regard, quel que soit leur nombre et quelles
        que soient leurs clés d'idempotence.
        """
        return ReviewerAttestationKey(
            subject=self.confirmation_subject_key, verifier_id=self.verifier_id,
        )


@dataclass(frozen=True, slots=True)
class NormativeRuleConfirmationRevocation:
    """Le retrait d'une confirmation — un **événement séparé et immuable**.

    Elle référence une confirmation ; elle ne la modifie jamais. La
    confirmation révoquée reste lisible, comme un livrable final erroné le
    reste : ce qui a été signé a été signé, et l'effacer effacerait la preuve
    de l'erreur.

    On n'exige d'elle **ni pages lues ni citation** : révoquer, ce n'est pas
    relire l'annexe. On exige un **motif**, parce qu'une révocation sans raison
    ne se distingue pas d'une erreur de manipulation.
    """

    revocation_id: str
    confirmation_id: str
    revoked_by: str
    revoked_by_name: str
    revoked_at: datetime
    #: Écrit par le serveur, comme pour la confirmation.
    authorisations_at_revocation: frozenset[str]
    reason: str

    def __post_init__(self) -> None:
        for nom in ("revocation_id", "confirmation_id", "revoked_by",
                    "revoked_by_name"):
            _exige_texte(getattr(self, nom), nom)
        _exige_instant_date(self.revoked_at, "revoked_at")
        _exige_frozenset(
            self.authorisations_at_revocation, "authorisations_at_revocation"
        )
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ConfirmationDomainError(
                "motif de revocation obligatoire. Retirer une confirmation "
                "sans dire pourquoi ne se distingue pas d'une fausse "
                "manoeuvre, et laisse le prochain relecteur sans point de "
                "depart."
            )


# ---------------------------------------------------------------------------
# Politique de confirmation
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class ConfirmationPolicy:
    """Combien de **regards indépendants** une règle exige.

    Versionnée, et volontairement hors du schéma de stockage : le nombre exigé
    est une décision qui peut changer, et une contrainte d'unicité SQL qui la
    trancherait en silence serait très difficile à défaire ensuite.

    « Indépendants » se compte en ``verifier_id`` **distincts**, jamais en
    lignes : deux envois de la même personne ne font pas deux relecteurs.
    """

    policy_version: str
    minimum_independent_confirmations: int

    #: La politique de production : **quatre yeux**. Une valeur nationale
    #: erronée se propage à toutes les études de la juridiction d'un seul
    #: coup ; le double contrôle est l'usage en bureau d'études.
    PRODUCTION_VERSION: ClassVar[str] = "esc-policy/1"
    PRODUCTION_MINIMUM: ClassVar[int] = 2

    def __post_init__(self) -> None:
        _exige_texte(self.policy_version, "policy_version")
        if (not isinstance(self.minimum_independent_confirmations, int)
                or isinstance(self.minimum_independent_confirmations, bool)
                or self.minimum_independent_confirmations < 1):
            raise ConfirmationDomainError(
                "minimum_independent_confirmations: un entier >= 1 est requis. "
                "Zero rendrait toute regle confirmee sans que personne ne "
                "l'ait lue."
            )

    @classmethod
    def production(cls) -> ConfirmationPolicy:
        return cls(
            policy_version=cls.PRODUCTION_VERSION,
            minimum_independent_confirmations=cls.PRODUCTION_MINIMUM,
        )

    def is_satisfied_by(self, regards: int) -> bool:
        return regards >= self.minimum_independent_confirmations


class ConfirmationStatus(str, Enum):
    """L'état d'une règle **relativement à un contexte**, jamais en soi.

    La nouveauté d'un document ne périme rien : une confirmation de l'édition
    2010 reste pleinement valide pour un calcul dont la pile demandée *est*
    celle de 2010.
    """

    #: Aucune confirmation pour cette règle.
    ABSENT = "absent"
    #: Les empreintes concordent et la politique est satisfaite.
    VALID_FOR_CONTEXT = "valid_for_context"
    #: Le pays prescrit autre chose — il faut rouvrir l'annexe.
    SPEC_MISMATCH = "spec_mismatch"
    #: La prescription n'a pas bougé, le code si.
    IMPLEMENTATION_MISMATCH = "implementation_mismatch"
    #: La confirmation atteste une AUTRE pile. Elle reste valide en soi, pour
    #: les calculs qui demandent cette pile-là.
    STACK_MISMATCH = "stack_mismatch"
    #: Des attestations concordent sur la règle, la pile, la prescription et le
    #: code — mais **pas sur le dossier de preuve lu**. Elles restent conservées
    #: individuellement et ne s'additionnent pas : deux relecteurs qui n'ont pas
    #: ouvert les mêmes pages n'ont pas exercé deux regards sur la même chose.
    EVIDENCE_MISMATCH = "evidence_mismatch"
    #: Toutes les confirmations concordantes ont été révoquées.
    REVOKED = "revoked"
    #: L'état intermédiaire: des confirmations valides, mais pas assez de
    #: regards indépendants. Un premier relecteur a signé, le second manque.
    INSUFFICIENT_INDEPENDENT_CONFIRMATIONS = "insufficient_independent_confirmations"


@dataclass(frozen=True, slots=True)
class ConfirmationAssessment:
    """Le résultat d'une évaluation, avec de quoi agir dessus.

    Porte les ``verifier_id`` retenus, et pas seulement leur nombre : « il en
    manque un » et « il en manque un, et voici qui a déjà signé » ne coûtent
    pas le même temps à celui qui doit trouver le second relecteur.
    """

    status: ConfirmationStatus
    regards: frozenset[str]
    policy: ConfirmationPolicy
    reason: str

    @property
    def is_confirmed(self) -> bool:
        return self.status is ConfirmationStatus.VALID_FOR_CONTEXT


def independent_regards(
    confirmations: tuple[NormativeRuleConfirmation, ...],
    revocations: tuple[NormativeRuleConfirmationRevocation, ...],
) -> frozenset[str]:
    """Les ``verifier_id`` distincts dont l'attestation est **active**.

    Un ensemble, pas un compte : deux lignes de la même personne s'y fondent
    d'elles-mêmes, sans qu'aucun appelant ait à y penser.

    **Refuse un ensemble hétérogène.** Additionner des attestations qui ne
    portent pas sur le même ``confirmation_subject_key`` est exactement ce que
    ce modèle doit rendre impossible : deux regards sur deux sujets différents
    ne font pas un double contrôle. Un appelant qui veut trier par sujet doit
    le faire avant, et :func:`assess_confirmations` s'en charge.

    Une révocation retire **l'attestation ciblée** et elle seule.
    """
    revoquees = {r.confirmation_id for r in revocations}
    actives = [c for c in confirmations if c.confirmation_id not in revoquees]

    sujets = {c.confirmation_subject_key for c in actives}
    if len(sujets) > 1:
        raise ConfirmationDomainError(
            f"{len(sujets)} sujets distincts dans le meme decompte. Des "
            "attestations qui ne portent pas sur le meme "
            "confirmation_subject_key ne s'additionnent pas: deux regards sur "
            "deux sujets differents ne font pas un double controle."
        )
    return frozenset(c.verifier_id for c in actives)


def assess_confirmations(
    *,
    confirmations: tuple[NormativeRuleConfirmation, ...],
    revocations: tuple[NormativeRuleConfirmationRevocation, ...],
    context: NormativeContext,
    normative_spec: Digest,
    implementation: Digest,
    policy: ConfirmationPolicy,
) -> ConfirmationAssessment:
    """Confronter des attestations a un contexte, a des empreintes, entre elles.

    Fonction **pure**, sans base et sans effet de bord. Elle n'est branchee sur
    rien : le mode strict la consommera plus tard. Les empreintes attendues
    sont passees en arguments plutot que deduites d'une regle, pour que ce
    module ne depende pas du registre des regles.

    Il n'y a **pas** d'``evidence`` en argument, et ce n'est pas un oubli : le
    dossier de preuve n'est pas quelque chose que l'appelant *demande*, c'est
    ce que les verificateurs *attestent*. Il ne se compare donc pas a une
    valeur attendue mais **entre attestations**.

    Ordre des controles
    -------------------
    1. **pile** — une confirmation faite sur une autre edition n'a aucune
       raison de porter les memes empreintes. Annoncer ``SPEC_MISMATCH``
       enverrait chercher un defaut de transcription la ou il n'y a qu'un
       ecart d'edition, et la confirmation reste pleinement valide pour les
       calculs qui demandent *sa* pile.
    2. **specification** — si le pays prescrit autre chose, l'ecart de code
       n'en est que la consequence. Annoncer ``IMPLEMENTATION_MISMATCH``
       enverrait lire un diff quand il faut ouvrir l'annexe.
    3. **implementation** — si le code a change, le dossier de preuve porte
       sur une regle qui n'existe plus sous cette forme ; comparer les
       dossiers avant le code ferait discuter des pages lues alors que le
       sujet lui-meme a bouge.
    4. **revocation** — placee ici, et non apres la preuve : une attestation
       retiree ne doit pas creer un desaccord de dossier qui n'existe plus.
       Deux attestations aux preuves divergentes dont l'une est revoquee
       laissent **un** regard, pas un ``EVIDENCE_MISMATCH``.
    5. **dossier de preuve** — le premier controle qui compare les
       attestations *entre elles* et non au contexte. Les trois premiers
       disent « ceci ne concerne pas ce que vous demandez » ; celui-ci dit
       « celles-ci concernent bien votre sujet, mais pas le meme dossier ».
    6. **nombre de verificateurs distincts** — en dernier, parce qu'un
       decompte n'a de sens qu'une fois etabli que l'on compte des regards sur
       **le meme** ``confirmation_subject_key``.

    L'ecart avec l'ordre suggere (preuve avant revocation) est delibere et
    porte sur le point 4 ; sa justification est ci-dessus.
    """
    if not confirmations:
        return ConfirmationAssessment(
            ConfirmationStatus.ABSENT, frozenset(), policy,
            "aucune confirmation pour cette regle.",
        )

    # --- 1. pile ----------------------------------------------------------
    attendu = context.stack.digest.digest
    meme_pile = tuple(
        c for c in confirmations if c.stack.digest.digest == attendu
    )
    if not meme_pile:
        piles = sorted({c.stack.digest.digest[:16] for c in confirmations})
        return ConfirmationAssessment(
            ConfirmationStatus.STACK_MISMATCH, frozenset(), policy,
            f"confirmation(s) faite(s) sur une autre pile ({', '.join(piles)}) "
            f"que celle demandee ({attendu[:16]}). Elles restent valides pour "
            "les calculs qui demandent cette pile-la: il faut une relecture "
            "pour l'edition demandee, pas une correction de code.",
        )

    # --- 2. specification normative ---------------------------------------
    meme_spec = tuple(c for c in meme_pile if c.normative_spec == normative_spec)
    if not meme_spec:
        return ConfirmationAssessment(
            ConfirmationStatus.SPEC_MISMATCH, frozenset(), policy,
            "la specification normative de la regle a change depuis la "
            "confirmation. Il faut rouvrir l'annexe.",
        )

    # --- 3. implementation -------------------------------------------------
    meme_impl = tuple(c for c in meme_spec if c.implementation == implementation)
    if not meme_impl:
        return ConfirmationAssessment(
            ConfirmationStatus.IMPLEMENTATION_MISMATCH, frozenset(), policy,
            "la specification n'a pas bouge mais le CODE qui l'execute si. "
            "Il faut comprendre pourquoi avant de reconfirmer.",
        )

    # --- 4. revocation -----------------------------------------------------
    revoquees = {r.confirmation_id for r in revocations}
    actives = tuple(c for c in meme_impl if c.confirmation_id not in revoquees)
    if not actives:
        return ConfirmationAssessment(
            ConfirmationStatus.REVOKED, frozenset(), policy,
            f"les {len(meme_impl)} attestation(s) concordantes ont ete "
            "revoquees.",
        )

    # --- 5. dossier de preuve ----------------------------------------------
    # Regrouper par sujet COMPLET. A ce stade les sept premieres composantes de
    # la cle sont deja communes; ne reste que le dossier de preuve pour les
    # separer — et c'est bien lui qui decide si deux regards portent sur la
    # meme chose.
    par_sujet: dict[ConfirmationSubjectKey, set[str]] = {}
    for c in actives:
        par_sujet.setdefault(c.confirmation_subject_key, set()).add(c.verifier_id)

    # Le meilleur groupe: celui qui reunit le plus de regards independants. Un
    # groupe qui satisfait a lui seul la politique est un double controle
    # complet sur un dossier partage; les autres attestations restent
    # conservees, simplement non additionnees. Le second critere de tri rend
    # le choix DETERMINISTE en cas d'egalite.
    meilleur, ids = max(
        par_sujet.items(), key=lambda kv: (len(kv[1]), kv[0].evidence_digest),
    )
    regards = frozenset(ids)

    if not policy.is_satisfied_by(len(regards)) and len(par_sujet) > 1:
        dossiers = sorted(k.evidence_digest[:16] for k in par_sujet)
        return ConfirmationAssessment(
            ConfirmationStatus.EVIDENCE_MISMATCH, regards, policy,
            f"{len(par_sujet)} dossiers de preuve distincts "
            f"({', '.join(dossiers)}) pour la meme regle, la meme pile et le "
            "meme code. Deux relecteurs qui n'ont pas ouvert les memes pages "
            "n'ont pas exerce deux regards sur la meme chose: ces attestations "
            "sont conservees mais ne s'additionnent pas.",
        )

    # --- 6. nombre de regards independants ---------------------------------
    if not policy.is_satisfied_by(len(regards)):
        manquants = policy.minimum_independent_confirmations - len(regards)
        return ConfirmationAssessment(
            ConfirmationStatus.INSUFFICIENT_INDEPENDENT_CONFIRMATIONS,
            regards, policy,
            f"{len(regards)} regard(s) independant(s), "
            f"{policy.minimum_independent_confirmations} exige(s) par "
            f"{policy.policy_version}: il en manque {manquants}. "
            f"Ont deja signe: {', '.join(sorted(regards))}.",
        )

    return ConfirmationAssessment(
        ConfirmationStatus.VALID_FOR_CONTEXT, regards, policy,
        f"{len(regards)} regard(s) independant(s) sur le meme sujet: meme "
        f"pile, memes empreintes, meme dossier de preuve "
        f"({meilleur.evidence_digest[:16]}).",
    )


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------
@runtime_checkable
class ConfirmationProvider(Protocol):
    """D'où viennent les confirmations — le moteur l'ignore.

    Le provider est la **frontière**. Le moteur ne vérifie pas qu'un
    vérificateur était autorisé : il consomme des confirmations dont le
    provider garantit qu'elles ont été produites sous contrôle. Le provider
    PostgreSQL le garantira par un trigger ; le provider mémoire ne produit que
    du fictif.
    """

    @property
    def provider_identity(self) -> str:
        """Inscrit dans la trace du calcul : on doit savoir qui a répondu."""
        ...

    @property
    def is_fictional(self) -> bool:
        """Vrai pour un provider de test. Un provider réel répond ``False``."""
        ...

    def confirmations_for(
        self, rule_id: str,
    ) -> tuple[NormativeRuleConfirmation, ...]:
        ...

    def revocations_for(
        self, rule_id: str,
    ) -> tuple[NormativeRuleConfirmationRevocation, ...]:
        """Les révocations visant les confirmations de *rule_id*.

        Demandées **avec** les confirmations et non déduites d'un champ porté
        par elles : il n'existe pas de ``is_revoked`` à lire.
        """
        ...


#: Préfixe obligatoire de toute identité manipulée par le provider mémoire.
#: Visible à l'œil nu dans un journal : une confirmation fictive ne doit jamais
#: pouvoir être prise pour une vraie, même de loin.
FICTIONAL_PREFIX = "FICTIF-"


def assert_provider_is_usable_in_production(provider: ConfirmationProvider) -> None:
    """Refuser un provider fictif là où de vraies règles seraient confirmées.

    Le crochet existe **dès maintenant**, avant la machinerie de sélection
    (6.3b) : c'est la garantie « aucun fichier éditable du dépôt ne peut rendre
    une règle réelle ``strict-ready`` », et elle doit exister avant qu'un
    chemin de sélection puisse l'oublier.
    """
    if provider.is_fictional:
        raise ConfirmationDomainError(
            f"provider fictif '{provider.provider_identity}' refuse hors des "
            "tests. Une confirmation fictive rendrait une regle REELLE "
            "confirmee, pour toute une juridiction, sans que personne n'ait "
            "lu l'annexe."
        )


@dataclass(frozen=True, slots=True)
class InMemoryConfirmationProvider:
    """Provider de **tests**, explicitement fictif. Jamais de production.

    Trois propriétés en font un objet de test et rien d'autre :

    1. son identité porte ``FICTIF`` en toutes lettres ;
    2. ``is_fictional`` vaut ``True``, ce que
       :func:`assert_provider_is_usable_in_production` refuse ;
    3. il **refuse à la construction** toute confirmation dont le vérificateur
       n'est pas marqué fictif — il ne peut donc pas contenir une confirmation
       belge réelle, même par erreur de copier-coller.

    Immuable lui aussi : ``with_confirmations`` rend un **nouveau** provider
    plutôt que de muter celui-ci. Un jeu de fixtures qu'un test précédent
    aurait complété en place serait une dépendance d'ordre entre tests.
    """

    confirmations: tuple[NormativeRuleConfirmation, ...] = ()
    revocations: tuple[NormativeRuleConfirmationRevocation, ...] = ()

    IDENTITY: ClassVar[str] = "in-memory://FICTIF-tests-uniquement"

    def __post_init__(self) -> None:
        _exige_tuple(self.confirmations, "confirmations du provider memoire")
        _exige_tuple(self.revocations, "revocations du provider memoire")

        for c in self.confirmations:
            if not c.verifier_id.startswith(FICTIONAL_PREFIX):
                raise ConfirmationDomainError(
                    f"provider memoire: verifier_id '{c.verifier_id}' n'est "
                    f"pas marque '{FICTIONAL_PREFIX}'. Ce provider ne peut pas "
                    "detenir une confirmation reelle: c'est ce qui empeche "
                    "qu'un jeu de fixtures rende une regle reelle confirmee."
                )

        vues: set[str] = set()
        for c in self.confirmations:
            if c.idempotency_key in vues:
                raise ConfirmationDomainError(
                    f"cle d'idempotence '{c.idempotency_key}' presente deux "
                    "fois. Elle empeche qu'un envoi rejoue cree deux lignes; "
                    "elle ne dit rien du nombre de regards, qui se compte en "
                    "verifier_id distincts."
                )
            vues.add(c.idempotency_key)

        for r in self.revocations:
            if not r.revoked_by.startswith(FICTIONAL_PREFIX):
                raise ConfirmationDomainError(
                    f"provider memoire: revoked_by '{r.revoked_by}' n'est pas "
                    f"marque '{FICTIONAL_PREFIX}'."
                )

    @property
    def provider_identity(self) -> str:
        return self.IDENTITY

    @property
    def is_fictional(self) -> bool:
        return True

    def confirmations_for(
        self, rule_id: str,
    ) -> tuple[NormativeRuleConfirmation, ...]:
        return tuple(c for c in self.confirmations if c.rule_id == rule_id)

    def revocations_for(
        self, rule_id: str,
    ) -> tuple[NormativeRuleConfirmationRevocation, ...]:
        vises = {c.confirmation_id for c in self.confirmations_for(rule_id)}
        return tuple(r for r in self.revocations if r.confirmation_id in vises)

    def with_confirmations(
        self, *nouvelles: NormativeRuleConfirmation,
    ) -> InMemoryConfirmationProvider:
        return InMemoryConfirmationProvider(
            confirmations=self.confirmations + nouvelles,
            revocations=self.revocations,
        )

    def with_revocations(
        self, *nouvelles: NormativeRuleConfirmationRevocation,
    ) -> InMemoryConfirmationProvider:
        return InMemoryConfirmationProvider(
            confirmations=self.confirmations,
            revocations=self.revocations + nouvelles,
        )


#: Les objets de domaine dont aucun champ ne doit rattacher une confirmation à
#: un client. Énumérés ici pour que le test structurel les parcoure tous, et
#: qu'un objet ajouté plus tard sans y figurer se voie.
DOMAIN_OBJECTS: tuple[type, ...] = (
    ConfirmationSubjectKey,
    ReviewerAttestationKey,
    NormativeStackComponent,
    NormativeStack,
    NormativeContext,
    NormativeRuleConfirmation,
    NormativeRuleConfirmationRevocation,
    ConfirmationPolicy,
    ConfirmationAssessment,
    InMemoryConfirmationProvider,
)


def field_names(objet: type) -> tuple[str, ...]:
    """Noms de champs d'un objet de domaine, pour les contrôles structurels."""
    return tuple(f.name for f in fields(objet))
