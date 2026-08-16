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

import json
from dataclasses import dataclass, field, fields
from datetime import date, datetime
from enum import Enum
from typing import Any, ClassVar, Protocol, runtime_checkable

from ..exceptions import EurostructEngineError
from .canonical import (
    CANONICALIZATION_VERSION,
    Digest,
    EvidenceItem,
    digest_of,
    evidence_digest,
)

__all__ = [
    "FICTIONAL_PREFIX",
    "FORBIDDEN_FIELD_FRAGMENTS",
    "ConfirmationAssessment",
    "ConfirmationDomainError",
    "ConfirmationPolicy",
    "ConfirmationProvider",
    "ConfirmationStatus",
    "ConfirmationSubjectKey",
    "ExcludedAttestation",
    "ExclusionCause",
    "InMemoryConfirmationProvider",
    "NormativeContext",
    "NormativeReviewPackage",
    "NormativeRuleConfirmation",
    "NormativeRuleConfirmationRevocation",
    "NormativeStack",
    "NormativeStackComponent",
    "RequiredSource",
    "ReviewerAttestationKey",
    "assert_provider_is_usable_in_production",
    "assess_confirmations",
    "independent_regards",
    "required_sources",
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
# Le dossier presente aux verificateurs
# ---------------------------------------------------------------------------
@dataclass(frozen=True, slots=True)
class RequiredSource:
    """Une source normative que la specification declare utiliser.

    **Une source, pas un document.** La distinction n'est pas theorique : le
    corps de l'EN 1992-1-1 et le corrigendum AC:2008 sont relies dans le meme
    PDF belge et portent donc le **meme ``document_digest``**, tout en etant
    deux couches normatives distinctes. Une couverture calculee sur les seuls
    documents laissait une preuve unique satisfaire les deux — et c'etait le
    cas jusqu'a ce correctif.

    Extraite du payload canonique de ``normative_spec_digest``, jamais saisie a
    la main.
    """

    document_digest: str
    reference: str
    #: Couche normative : base | corrigendum | amendement | annexe | reglement.
    #: Meme vocabulaire que ``EvidenceItem.document_role``, sans quoi la
    #: correspondance ne pourrait pas etre etablie.
    role: str
    clause: str
    #: Comparee **seulement si la source en declare une**. Les couches
    #: d'expression n'en portent pas dans le payload ; l'autorite normative si.
    edition: str | None = None
    #: Conserve pour l'affichage et pour la garde d'ambiguite ci-dessous, mais
    #: **hors cle de correspondance** : ``EvidenceItem`` n'a pas de champ ou
    #: l'exprimer. Voir :meth:`match_key`.
    expression_label: str | None = None
    #: Prose decrivant ce que la couche a fait. **Jamais** dans la cle : deux
    #: sources qui ne differeraient que par cette phrase seraient la meme
    #: source lue deux fois, et exiger d'une preuve qu'elle la reproduise
    #: n'aurait aucun sens.
    effect: str = ""

    @property
    def match_key(self) -> tuple[str, str, str, str, str | None]:
        """Ce qui identifie la source pour la correspondance avec une preuve.

        ``(document_digest, reference, role, clause, edition)``.

        ``expression_label`` en est **absent a regret** : il identifie bien
        *quelle formule* dans une clause, mais ``EvidenceItem`` n'a aucun champ
        pour l'exprimer, et lui en ajouter un changerait ``evidence_digest``,
        donc la canonicalisation. Plutot que d'ignorer le probleme en silence,
        :class:`NormativeReviewPackage` **refuse** un jeu de sources dont deux
        partageraient cette cle en differant par leur label.
        """
        return (self.document_digest, self.reference, self.role, self.clause,
                self.edition)

    def matches(self, item: EvidenceItem) -> bool:
        """Cette preuve porte-t-elle bien sur **cette** source structuree ?

        Le systeme ne juge pas si la citation est intellectuellement correcte —
        c'est le travail du verificateur. Il empeche seulement qu'elle soit
        rattachee a une autre source que celle qu'elle nomme.
        """
        if item.document_digest != self.document_digest:
            return False
        if item.reference != self.reference:
            return False
        if item.document_role != self.role:
            return False
        if item.clause != self.clause:
            return False
        return not (self.edition is not None and item.edition != self.edition)


#: Role attribue a l'autorite normative. Le payload de specification ne
#: l'enregistre pas : ``NormativeAuthority`` porte pays, reference, edition,
#: clause et effet, mais aucune couche. Pour les six regles belges c'est
#: toujours l'annexe nationale, d'ou ce choix.
#:
#: La limite est reelle et signalee: une autorite qui serait un reglement (un
#: arrete royal, par exemple) exigerait que le payload enregistre son role. Le
#: mode d'echec est franc — la preuve ne correspondrait a aucune source et le
#: paquet serait refuse — jamais silencieux.
_AUTHORITY_ROLE = "annexe"


def required_sources(normative_spec: Digest) -> tuple[RequiredSource, ...]:
    """Les sources que la specification declare, lues dans son payload.

    C'est possible parce que ``normative_spec_digest`` conserve son payload
    canonique et qu'il porte, pour chaque couche et pour l'autorite normative,
    la reference, la clause **et** l'empreinte du document. Aucune verification
    n'est donc reportee a un jalon ulterieur.

    Refuse une version de canonicalisation inconnue plutot que de lire un
    payload dont la forme aurait change : deduire une couverture documentaire
    d'une structure qu'on interprete mal est pire que ne rien deduire.
    """
    payload = json.loads(normative_spec.canonical_payload)
    if payload.get("canonicalization_version") != CANONICALIZATION_VERSION:
        raise ConfirmationDomainError(
            f"payload de specification en version "
            f"{payload.get('canonicalization_version')!r}, attendu "
            f"{CANONICALIZATION_VERSION!r}. La couverture documentaire se lit "
            "dans une structure versionnee: l'interpreter au juge serait "
            "inventer une garantie."
        )

    sources: list[RequiredSource] = []
    for src in payload.get("expression_sources", ()):
        sources.append(RequiredSource(
            document_digest=src["document_digest"],
            reference=src["reference"],
            role=src["layer"],
            clause=src["clause"],
            edition=None,
            expression_label=src.get("expression_label"),
            effect=src.get("effect", ""),
        ))

    autorite = payload.get("normative_authority") or {}
    if autorite.get("document_digest"):
        sources.append(RequiredSource(
            document_digest=autorite["document_digest"],
            reference=autorite["reference"],
            role=_AUTHORITY_ROLE,
            clause=autorite["clause"],
            edition=autorite.get("edition"),
            expression_label=None,
            effect=autorite.get("effect", ""),
        ))

    # Dedoublonnage sur l'IDENTITE COMPLETE, pas sur la cle: deux entrees
    # rigoureusement identiques sont la meme source declaree deux fois.
    uniques: list[RequiredSource] = []
    for src in sources:
        if src not in uniques:
            uniques.append(src)
    return tuple(uniques)


@dataclass(frozen=True, slots=True)
class NormativeReviewPackage:
    """**Ce qui est presente aux verificateurs**, avant toute signature.

    L'objet que 6.3a2 ajoute, et la raison de l'ajouter : comparer les preuves
    seulement *entre* attestations demontre qu'elles sont d'accord, pas
    qu'elles portent sur le bon dossier. Deux verificateurs pouvaient confirmer
    ensemble le meme dossier **incomplet**.

    Les deux verificateurs recoivent **le meme paquet**. Leur confirmation en
    reference le ``subject_key`` et n'ajoute que ce qui leur est propre :
    identite, horodatage, autorisation, declaration personnelle, cle
    d'idempotence.

    ``evidence`` et ``subject_key`` sont ``init=False`` : **recalcules depuis
    le contenu**. Un appelant ne peut pas fournir une cle qui ne correspond pas
    a ce qu'elle pretend resumer, et c'est tout l'interet — une cle falsifiable
    ne prouverait rien de ce qui a ete presente.
    """

    package_version: str
    country_code: str
    standard_family: str
    part: str
    rule_id: str
    stack: NormativeStack
    normative_spec: Digest
    implementation: Digest
    evidence_items: tuple[EvidenceItem, ...]

    evidence: Digest = field(init=False)
    subject_key: ConfirmationSubjectKey = field(init=False)

    PACKAGE_VERSION: ClassVar[str] = "esc-review-package/1"

    def __post_init__(self) -> None:
        _exige_texte(self.package_version, "package_version")
        for nom in ("country_code", "standard_family", "part", "rule_id"):
            _exige_texte(getattr(self, nom), nom)
        if not isinstance(self.stack, NormativeStack):
            raise ConfirmationDomainError(
                "stack: un snapshot structure est requis."
            )
        for nom in ("normative_spec", "implementation"):
            if not isinstance(getattr(self, nom), Digest):
                raise ConfirmationDomainError(f"{nom}: un Digest est requis.")
        _exige_tuple(self.evidence_items, "evidence_items")
        if not self.evidence_items:
            raise ConfirmationDomainError(
                "un dossier de revue vide ne presente rien a verifier."
            )

        # --- concordance avec la pile -------------------------------------
        for nom in ("country_code", "standard_family", "part"):
            if getattr(self.stack, nom) != getattr(self, nom):
                raise ConfirmationDomainError(
                    f"{nom}: le paquet dit '{getattr(self, nom)}' et sa pile "
                    f"'{getattr(self.stack, nom)}'. Un dossier de revue "
                    "presente une regle DANS une pile: les deux ne peuvent pas "
                    "designer deux referentiels."
                )

        # --- concordance avec la specification ----------------------------
        payload = json.loads(self.normative_spec.canonical_payload)
        if payload.get("rule_id") != self.rule_id:
            raise ConfirmationDomainError(
                f"le paquet annonce la regle '{self.rule_id}' et porte "
                f"l'empreinte de '{payload.get('rule_id')}'. Presenter une "
                "regle sous le nom d'une autre est la confusion la plus "
                "couteuse a rattraper apres signature."
            )

        # --- couverture des SOURCES, dans les DEUX sens --------------------
        # Sur les sources structurees et non sur les seuls documents: le corps
        # de l'EN et son corrigendum sont relies dans le meme PDF belge et
        # partagent donc leur empreinte. Compter les documents laissait une
        # preuve unique satisfaire deux couches distinctes.
        exiges = required_sources(self.normative_spec)

        # Garde d'ambiguite: deux sources que la cle ne distingue pas mais qui
        # visent deux formules differentes. La cle ne peut pas porter le label
        # — EvidenceItem n'a pas de champ ou l'exprimer — donc on REFUSE plutot
        # que de laisser une preuve en couvrir deux au hasard.
        par_cle: dict[tuple, list[RequiredSource]] = {}
        for src in exiges:
            par_cle.setdefault(src.match_key, []).append(src)
        for cle, groupe in par_cle.items():
            labels = {g.expression_label for g in groupe}
            if len(labels) > 1:
                raise ConfirmationDomainError(
                    f"deux sources requises partagent la cle {cle[1]!r} "
                    f"/{cle[2]}/{cle[3]} mais visent des expressions "
                    f"differentes {sorted(map(str, labels))}. Une preuve ne "
                    "peut pas etre rattachee a l'une plutot qu'a l'autre: "
                    "EvidenceItem n'exprime pas le label. Refus explicite."
                )

        manquantes = [
            src for src in exiges
            if not any(src.matches(i) for i in self.evidence_items)
        ]
        if manquantes:
            details = "; ".join(
                f"{s.reference} ({s.role}, {s.clause}, "
                f"{s.document_digest[:16]})" for s in manquantes
            )
            raise ConfirmationDomainError(
                "dossier de revue INCOMPLET: aucune preuve pour "
                f"{len(manquantes)} source(s) declaree(s) par la "
                f"specification — {details}. C'est precisement le defaut que "
                "ce paquet existe pour empecher: deux verificateurs peuvent "
                "tres bien s'accorder sur un dossier auquel il manque une "
                "couche. Une preuve du corps de la norme ne couvre pas le "
                "corrigendum, meme relie dans le meme fichier."
            )

        orphelines = [
            i for i in self.evidence_items
            if not any(src.matches(i) for src in exiges)
        ]
        if orphelines:
            details = "; ".join(
                f"{i.reference} ({i.document_role}, {i.clause}, "
                f"{i.document_digest[:16]})" for i in orphelines
            )
            raise ConfirmationDomainError(
                f"le dossier contient {len(orphelines)} preuve(s) ne "
                f"correspondant a aucune source declaree — {details}. Une "
                "preuve doit nommer la source qu'elle atteste: bon document "
                "mais mauvaise clause, mauvais role ou mauvaise edition, c'est "
                "une preuve rattachee a autre chose que ce qu'elle prouve."
            )

        object.__setattr__(self, "evidence", evidence_digest(self.evidence_items))
        object.__setattr__(self, "subject_key", ConfirmationSubjectKey(
            country_code=self.country_code,
            standard_family=self.standard_family,
            part=self.part,
            rule_id=self.rule_id,
            stack_digest=self.stack.digest.digest,
            normative_spec_digest=self.normative_spec.digest,
            implementation_digest=self.implementation.digest,
            evidence_digest=self.evidence.digest,
        ))

    @classmethod
    def of(
        cls, *, country_code: str, standard_family: str, part: str,
        rule_id: str, stack: NormativeStack, normative_spec: Digest,
        implementation: Digest, evidence_items: tuple[EvidenceItem, ...],
    ) -> NormativeReviewPackage:
        """Construire avec la version de paquet courante."""
        return cls(
            package_version=cls.PACKAGE_VERSION,
            country_code=country_code, standard_family=standard_family,
            part=part, rule_id=rule_id, stack=stack,
            normative_spec=normative_spec, implementation=implementation,
            evidence_items=evidence_items,
        )

    @property
    def required_sources(self) -> tuple[RequiredSource, ...]:
        """Les documents que la specification declare — pour l'affichage."""
        return required_sources(self.normative_spec)


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

    #: **Recalculée** depuis ``evidence_items``, jamais fournie. Elle l'était,
    #: et rien n'obligeait alors les deux à concorder : une attestation pouvait
    #: annoncer l'empreinte du bon dossier tout en portant les pages d'un
    #: autre.
    evidence: Digest = field(init=False)

    #: Audit seulement. N'ouvre aucun droit sur un projet et n'est lue par
    #: aucun contrôle.
    verifier_affiliation: str | None = None

    def __post_init__(self) -> None:
        for nom in ("confirmation_id", "country_code", "standard_family",
                    "part", "rule_id", "verifier_id", "verifier_name",
                    "authorisation_scope_at_signature", "idempotency_key"):
            _exige_texte(getattr(self, nom), nom)

        for nom in ("normative_spec", "implementation"):
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

        object.__setattr__(
            self, "evidence", evidence_digest(self.evidence_items),
        )

    @classmethod
    def for_package(
        cls, package: NormativeReviewPackage, *, confirmation_id: str,
        verifier_id: str, verifier_name: str, verified_at: datetime,
        authorisations_at_signature: frozenset[str],
        authorisation_scope_at_signature: str, statement: str,
        idempotency_key: str, verifier_affiliation: str | None = None,
    ) -> NormativeRuleConfirmation:
        """Signer **le paquet qui a ete presente**, sans pouvoir en changer.

        Le sujet vient entierement du paquet ; l'appelant n'ajoute que ce qui
        lui est propre. C'est la voie normale : construire une confirmation
        champ par champ reste possible, mais rien ne garantit alors qu'elle
        porte sur ce que le verificateur a reellement vu.
        """
        return cls(
            confirmation_id=confirmation_id,
            country_code=package.country_code,
            standard_family=package.standard_family,
            part=package.part,
            rule_id=package.rule_id,
            normative_spec=package.normative_spec,
            implementation=package.implementation,
            stack=package.stack,
            evidence_items=package.evidence_items,
            verifier_id=verifier_id,
            verifier_name=verifier_name,
            verified_at=verified_at,
            authorisations_at_signature=authorisations_at_signature,
            authorisation_scope_at_signature=authorisation_scope_at_signature,
            statement=statement,
            idempotency_key=idempotency_key,
            verifier_affiliation=verifier_affiliation,
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
    """L'etat du **sujet attendu**, et de lui seul.

    Volontairement court. Depuis 6.3a2, l'evaluation part d'un
    :class:`NormativeReviewPackage` connu **independamment des attestations** :
    les facons de diverger ne sont donc plus des etats globaux mais des causes
    d'exclusion portees par chaque attestation (voir :class:`ExclusionCause`).

    Melanger les deux rendait le statut ambigu des qu'une attestation etrangere
    trainait dans le lot: « STACK_MISMATCH » ne disait pas si le sujet attendu
    etait confirme par ailleurs.
    """

    #: Aucune attestation ne porte sur le sujet attendu. C'est aussi ce que
    #: rend une evaluation sans aucune confirmation: le sujet attendu est connu
    #: quand meme, puisqu'il vient du paquet de revue.
    UNCONFIRMED = "unconfirmed"
    #: Des regards valides sur le sujet attendu, mais pas assez. Un premier
    #: relecteur a signe, le second manque.
    PARTIALLY_CONFIRMED = "partially_confirmed"
    #: La politique est satisfaite sur le sujet attendu exact.
    CONFIRMED = "confirmed"
    #: Des attestations portaient exactement sur le sujet attendu, et toutes
    #: ont ete revoquees. Distinct d'UNCONFIRMED: « personne n'a jamais signe »
    #: et « ce qui avait ete signe a ete retire » n'appellent pas la meme
    #: enquete.
    REVOKED = "revoked"


class ExclusionCause(str, Enum):
    """Pourquoi une attestation n'entre pas dans le decompte.

    Chaque cause est **portee par l'attestation**, jamais par le resultat
    global. Une attestation tierce divergente reste ainsi visible meme quand
    deux attestations exactes suffisent deja: la faire disparaitre du rapport
    parce que le compte est bon reviendrait a cacher qu'un relecteur a signe
    autre chose que ce qu'on lui presentait.
    """

    #: Autre regle, autre pays, autre norme ou autre partie. Jamais comptee, et
    #: ce n'est meme pas un desaccord: l'attestation parle d'autre chose.
    OTHER_SUBJECT = "other_subject"
    #: Autre pile. L'attestation reste pleinement valide pour les calculs qui
    #: demandent SA pile.
    STACK_MISMATCH = "stack_mismatch"
    #: Le pays prescrit autre chose que ce que le paquet presente.
    SPEC_MISMATCH = "spec_mismatch"
    #: Meme prescription, autre code.
    IMPLEMENTATION_MISMATCH = "implementation_mismatch"
    #: Meme regle, meme pile, meme code — mais pas le dossier presente. C'est
    #: la cause que 6.3a2 rend detectable: comparer les preuves entre
    #: attestations prouvait qu'elles etaient d'accord, pas qu'elles avaient lu
    #: le bon dossier.
    EVIDENCE_MISMATCH = "evidence_mismatch"
    #: Attestation exacte, mais retiree.
    REVOKED = "revoked"


@dataclass(frozen=True, slots=True)
class ExcludedAttestation:
    """Une attestation ecartee, avec son identifiant et la raison.

    Presente dans TOUT resultat, y compris ``CONFIRMED``.
    """

    confirmation_id: str
    verifier_id: str
    cause: ExclusionCause
    detail: str


@dataclass(frozen=True, slots=True)
class ConfirmationAssessment:
    """Le resultat d'une evaluation, avec de quoi agir dessus.

    Porte les ``verifier_id`` retenus, et pas seulement leur nombre : « il en
    manque un » et « il en manque un, et voici qui a deja signe » ne coutent
    pas le meme temps a celui qui doit trouver le second relecteur.
    """

    status: ConfirmationStatus
    subject: ConfirmationSubjectKey
    regards: frozenset[str]
    policy: ConfirmationPolicy
    reason: str
    excluded: tuple[ExcludedAttestation, ...] = ()

    @property
    def is_confirmed(self) -> bool:
        return self.status is ConfirmationStatus.CONFIRMED

    @property
    def has_divergent_attestations(self) -> bool:
        """Quelqu'un a signe autre chose que ce qui lui etait presente.

        Exposee separement du statut: rendre ce conflit bloquant pour le mode
        strict est une decision du branchement, pas du domaine. Le domaine se
        contente de la rendre impossible a manquer.
        """
        return any(
            e.cause is not ExclusionCause.REVOKED for e in self.excluded
        )


def independent_regards(
    confirmations: tuple[NormativeRuleConfirmation, ...],
    revocations: tuple[NormativeRuleConfirmationRevocation, ...],
) -> frozenset[str]:
    """Les ``verifier_id`` distincts dont l'attestation est **active**.

    Un ensemble, pas un compte : deux lignes de la meme personne s'y fondent
    d'elles-memes, sans qu'aucun appelant ait a y penser.

    **Refuse un ensemble heterogene.** Additionner des attestations qui ne
    portent pas sur le meme ``confirmation_subject_key`` est exactement ce que
    ce modele doit rendre impossible : deux regards sur deux sujets differents
    ne font pas un double controle. Un appelant qui veut trier par sujet doit
    le faire avant, et :func:`assess_confirmations` s'en charge.

    Une revocation retire **l'attestation ciblee** et elle seule.
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


def _cause_d_exclusion(
    c: NormativeRuleConfirmation,
    attendu: NormativeReviewPackage,
    revoquees: set[str],
) -> tuple[ExclusionCause, str] | None:
    """Pourquoi *c* n'entre pas dans le decompte, ou ``None`` si elle y entre.

    Ordre des controles, de la cause la plus large a la plus etroite:

    1. **sujet etranger** — autre regle, pays, norme ou partie. Ce n'est pas un
       desaccord, l'attestation parle d'autre chose.
    2. **pile** — une attestation faite sur une autre edition n'a aucune raison
       de porter les memes empreintes; annoncer un ecart de specification
       enverrait chercher un defaut de transcription la ou il n'y a qu'un ecart
       d'edition.
    3. **specification** — si le pays prescrit autre chose, l'ecart de code
       n'en est que la consequence.
    4. **implementation** — si le code a change, le dossier porte sur une regle
       qui n'existe plus sous cette forme.
    5. **dossier de preuve** — le relecteur a signe autre chose que ce qui lui
       etait presente.
    6. **revocation** — en dernier, et c'est un changement par rapport a
       6.3a1: la revocation y precedait la preuve, pour eviter qu'une
       attestation retiree ne produise un EVIDENCE_MISMATCH *global*. Ce risque
       a disparu avec le paquet attendu, puisque le statut ne depend plus que
       des attestations EXACTES. Diagnostiquer le desaccord de sujet avant le
       retrait dit desormais quelque chose de plus utile: pourquoi elle a
       probablement ete retiree.
    """
    a = attendu.subject_key
    k = c.confirmation_subject_key

    if (k.country_code, k.standard_family, k.part, k.rule_id) != (
        a.country_code, a.standard_family, a.part, a.rule_id
    ):
        return (ExclusionCause.OTHER_SUBJECT,
                f"atteste {k.country_code}/{k.standard_family}/{k.part}/"
                f"{k.rule_id}, attendu {a.country_code}/{a.standard_family}/"
                f"{a.part}/{a.rule_id}.")

    if k.stack_digest != a.stack_digest:
        return (ExclusionCause.STACK_MISMATCH,
                f"pile {k.stack_digest[:16]}, attendue {a.stack_digest[:16]}. "
                "L'attestation reste valide pour les calculs qui demandent sa "
                "pile: il faut une relecture pour l'edition attendue, pas une "
                "correction de code.")

    if k.normative_spec_digest != a.normative_spec_digest:
        return (ExclusionCause.SPEC_MISMATCH,
                f"specification {k.normative_spec_digest[:16]}, attendue "
                f"{a.normative_spec_digest[:16]}. Il faut rouvrir l'annexe.")

    if k.implementation_digest != a.implementation_digest:
        return (ExclusionCause.IMPLEMENTATION_MISMATCH,
                f"implementation {k.implementation_digest[:16]}, attendue "
                f"{a.implementation_digest[:16]}. La prescription n'a pas "
                "bouge mais le CODE qui l'execute si.")

    if k.evidence_digest != a.evidence_digest:
        return (ExclusionCause.EVIDENCE_MISMATCH,
                f"dossier de preuve {k.evidence_digest[:16]}, attendu "
                f"{a.evidence_digest[:16]}. Le relecteur a signe un autre "
                "dossier que celui qui lui etait presente: son accord avec un "
                "autre relecteur sur ce meme autre dossier ne vaut pas pour le "
                "paquet attendu.")

    if c.confirmation_id in revoquees:
        return (ExclusionCause.REVOKED, "attestation retiree.")

    return None


def assess_confirmations(
    *,
    expected: NormativeReviewPackage,
    confirmations: tuple[NormativeRuleConfirmation, ...],
    revocations: tuple[NormativeRuleConfirmationRevocation, ...],
    policy: ConfirmationPolicy,
) -> ConfirmationAssessment:
    """Confronter des attestations au **dossier qui devait leur etre presente**.

    Fonction **pure**, sans base et sans effet de bord. Elle n'est branchee sur
    rien : le mode strict la consommera plus tard.

    Ce que change 6.3a2
    -------------------
    L'ancienne signature recevait ``normative_spec`` et ``implementation`` mais
    **aucun sujet attendu** : ni ``rule_id``, ni dossier de preuve. Le dossier
    n'etait donc compare qu'*entre* attestations, ce qui demontrait leur accord
    mutuel et non leur exactitude. Deux verificateurs pouvaient confirmer
    ensemble le meme dossier **incomplet**, et le modele l'appelait CONFIRMED.

    Le sujet attendu vient desormais du :class:`NormativeReviewPackage`, connu
    **independamment des attestations**. Aucune valeur normative n'est deduite
    de la premiere confirmation recue — l'evaluation fonctionne d'ailleurs a
    l'identique avec zero confirmation.
    """
    if not isinstance(expected, NormativeReviewPackage):
        raise ConfirmationDomainError(
            "expected: un NormativeReviewPackage est requis. Le sujet attendu "
            "ne se deduit pas des attestations recues."
        )

    revoquees = {r.confirmation_id for r in revocations}
    retenues: list[NormativeRuleConfirmation] = []
    exclues: list[ExcludedAttestation] = []
    exacts = 0

    for c in confirmations:
        verdict = _cause_d_exclusion(c, expected, revoquees)
        if verdict is None:
            exacts += 1
            retenues.append(c)
            continue
        cause, detail = verdict
        if cause is ExclusionCause.REVOKED:
            exacts += 1
        exclues.append(ExcludedAttestation(
            confirmation_id=c.confirmation_id, verifier_id=c.verifier_id,
            cause=cause, detail=detail,
        ))

    # Ordre stable, independant de l'ordre d'arrivee: un rapport dont les
    # lignes changent de place d'une execution a l'autre est illisible en
    # comparaison, et c'est exactement ce qu'un audit fait.
    exclues.sort(key=lambda e: (e.cause.value, e.confirmation_id))

    regards = frozenset(c.verifier_id for c in retenues)
    sujet = expected.subject_key
    divergentes = [e for e in exclues if e.cause is not ExclusionCause.REVOKED]
    suffixe = (
        f" {len(divergentes)} attestation(s) divergente(s) signalee(s)."
        if divergentes else ""
    )

    if policy.is_satisfied_by(len(regards)):
        return ConfirmationAssessment(
            ConfirmationStatus.CONFIRMED, sujet, regards, policy,
            f"{len(regards)} regard(s) independant(s) sur le sujet attendu "
            f"exact.{suffixe}",
            tuple(exclues),
        )

    if regards:
        manquants = policy.minimum_independent_confirmations - len(regards)
        return ConfirmationAssessment(
            ConfirmationStatus.PARTIALLY_CONFIRMED, sujet, regards, policy,
            f"{len(regards)} regard(s) independant(s), "
            f"{policy.minimum_independent_confirmations} exige(s) par "
            f"{policy.policy_version}: il en manque {manquants}. "
            f"Ont deja signe: {', '.join(sorted(regards))}.{suffixe}",
            tuple(exclues),
        )

    if exacts:
        return ConfirmationAssessment(
            ConfirmationStatus.REVOKED, sujet, regards, policy,
            f"les {exacts} attestation(s) portant sur le sujet attendu ont "
            f"ete revoquees.{suffixe}",
            tuple(exclues),
        )

    return ConfirmationAssessment(
        ConfirmationStatus.UNCONFIRMED, sujet, regards, policy,
        f"aucune attestation ne porte sur le sujet attendu "
        f"({sujet.rule_id}, pile {sujet.stack_digest[:16]}, dossier "
        f"{sujet.evidence_digest[:16]}).{suffixe}",
        tuple(exclues),
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
    RequiredSource,
    NormativeReviewPackage,
    ExcludedAttestation,
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
