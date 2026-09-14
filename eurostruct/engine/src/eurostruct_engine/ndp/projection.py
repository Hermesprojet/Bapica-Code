"""Des lignes SQL vers le domaine. Pure, sans pilote, et méfiante.

CE QUE CE MODULE EXISTE POUR EMPÊCHER
--------------------------------------
``PostgresConfirmationProvider.confirmations_for`` levait ``NotImplementedError``
avec ce commentaire :

    « Ne pas rendre un tuple vide: cela se lirait "aucune confirmation", ce
    qui est une REPONSE. »

L'avertissement visait juste, et il visait aussi ce module. Projeter une
ligne, ce n'est pas la recopier : c'est **affirmer** que ce qu'elle contient
est bien ce qui a été signé. Une projection qui fait confiance à ses colonnes
transforme une base modifiée en confirmation valide.

TROIS EMPREINTES, ET AUCUNE N'EST CRUE SUR PAROLE
--------------------------------------------------
La table conserve, à côté de chaque empreinte, le **payload canonique** qui l'a
produite. C'est ce qui rend la vérification possible dix ans plus tard — et
c'est ce qui la rend obligatoire ici :

``normative_spec``, ``implementation``
    :class:`~.canonical.Digest` **re-hache son payload à la construction**.
    Modifier le payload sans le hash, ou le hash sans le payload, est refusé
    sans que ce module ait à écrire un seul contrôle. On lui passe donc les
    **deux** colonnes, jamais une seule : recalculer l'empreinte depuis le
    payload détruirait la vérification en la remplaçant par une tautologie.

``stack``
    :class:`~.confirmation.NormativeStack` calcule son empreinte depuis sa
    structure. On la compare à la colonne ``stack_digest``, qui est ce que la
    recherche indexe : les deux doivent dire la même pile.

``evidence``
    Même chose, depuis les éléments de preuve.

CE QU'IL NE RECONSTITUE PAS, ET POURQUOI C'EST CORRECT
-------------------------------------------------------
``page_pdf`` n'est pas dans le payload de preuve : il en est **exclu**
délibérément (aide de navigation, il change avec le tirage du fichier). Il ne
peut donc pas être relu, et il vaut ``None``. Ce n'est pas une perte : c'est
la conséquence de ne hacher que ce qui fait autorité.

UNE VERSION DE CANONICALISATION INCONNUE EST UN REFUS
------------------------------------------------------
Réinterpréter avec la méthode d'aujourd'hui un payload produit par celle
d'hier, c'est comparer deux formes canoniques différentes et conclure à une
falsification — ou pire, ne rien conclure. On refuse en nommant la version.
"""
from __future__ import annotations

import json
from typing import Any

from .canonical import (
    CANONICALIZATION_VERSION,
    Digest,
    EvidenceItem,
)
from .confirmation import (
    ConfirmationDomainError,
    NormativeRuleConfirmation,
    NormativeRuleConfirmationRevocation,
    NormativeStack,
    NormativeStackComponent,
)

__all__ = [
    "COLONNES_CONFIRMATION",
    "COLONNES_REVOCATION",
    "ProjectionImpossible",
    "confirmation_depuis_ligne",
    "revocation_depuis_ligne",
]


class ProjectionImpossible(ConfirmationDomainError):
    """La ligne lue ne peut pas devenir une confirmation du domaine.

    C'est un refus, pas un avertissement : une confirmation qu'on ne sait pas
    reconstituer entièrement ne doit pas entrer dans un décompte à quatre yeux
    sous une forme approchée.
    """


#: L'ordre des colonnes du SELECT. Nommé ici plutôt que dans la requête pour
#: que la projection et la lecture ne puissent pas diverger — un `select *`
#: rendrait la position d'une colonne dépendante de l'ordre de la table.
COLONNES_CONFIRMATION: tuple[str, ...] = (
    "id", "country_code", "standard_family", "part", "rule_id",
    "stack_digest", "normative_spec_digest", "implementation_digest",
    "evidence_digest", "digest_algorithm", "canonicalization_version",
    "normative_spec_payload", "implementation_payload", "stack_snapshot",
    "evidence_items", "statement", "verifier_id", "verifier_name",
    "verified_at", "authorisation_scope", "idempotency_key",
)

COLONNES_REVOCATION: tuple[str, ...] = (
    "id", "confirmation_id", "revoked_by", "revoked_by_name", "revoked_at",
    "authorisation_scope", "reason",
)


def _exige(ligne: dict[str, Any], colonne: str) -> Any:
    """Une colonne absente ou nulle est un refus, jamais un défaut."""
    if colonne not in ligne:
        raise ProjectionImpossible(
            f"colonne '{colonne}' absente de la ligne lue. La projection ne "
            "complete pas ce que la requete n'a pas demande."
        )
    valeur = ligne[colonne]
    if valeur is None:
        raise ProjectionImpossible(
            f"colonne '{colonne}' nulle. Une confirmation incomplete ne se "
            "reconstitue pas avec une valeur par defaut: la valeur par defaut "
            "n'a ete lue par personne."
        )
    return valeur


def _json(valeur: Any, quoi: str) -> Any:
    """``jsonb`` arrive décodé avec la plupart des pilotes, en texte avec d'autres."""
    if isinstance(valeur, str | bytes | bytearray):
        try:
            return json.loads(valeur)
        except ValueError as cause:
            raise ProjectionImpossible(
                f"{quoi}: le texte lu n'est pas du JSON ({cause})."
            ) from cause
    return valeur


def _version(ligne: dict[str, Any]) -> str:
    version = str(_exige(ligne, "canonicalization_version"))
    if version != CANONICALIZATION_VERSION:
        raise ProjectionImpossible(
            f"version de canonicalisation '{version}' lue, "
            f"'{CANONICALIZATION_VERSION}' connue de ce moteur. Reinterpreter "
            "un payload ancien avec la methode d'aujourd'hui comparerait deux "
            "formes canoniques differentes: le refus est la seule reponse qui "
            "ne mente pas."
        )
    return version


def _empreinte(ligne: dict[str, Any], payload: str, empreinte: str) -> Digest:
    """Les DEUX colonnes, jamais une seule. Voir l'en-tete du module."""
    return Digest(
        algorithm=str(_exige(ligne, "digest_algorithm")),
        canonicalization_version=_version(ligne),
        canonical_payload=str(_exige(ligne, payload)),
        digest=str(_exige(ligne, empreinte)),
    )


def _pile(ligne: dict[str, Any]) -> NormativeStack:
    """La pile, reconstruite depuis le snapshot, puis CONFRONTEE a sa colonne."""
    brut = _json(_exige(ligne, "stack_snapshot"), "stack_snapshot")
    if not isinstance(brut, dict):
        raise ProjectionImpossible(
            f"stack_snapshot: un objet est attendu, recu {type(brut).__name__}."
        )
    composants = brut.get("components")
    if not isinstance(composants, list) or not composants:
        raise ProjectionImpossible(
            "stack_snapshot ne porte aucun composant. Une pile sans etage "
            "n'atteste rien."
        )

    try:
        pile = NormativeStack(
            schema_version=str(brut["schema_version"]),
            country_code=str(brut["country_code"]),
            standard_family=str(brut["standard_family"]),
            part=str(brut["part"]),
            components=tuple(
                NormativeStackComponent(
                    role=str(c["role"]),
                    reference=str(c["reference"]),
                    edition=str(c["edition"]),
                    application_order=int(c["application_order"]),
                    document_digest=str(c["document_digest"]),
                )
                for c in composants
            ),
        )
    except KeyError as cause:
        raise ProjectionImpossible(
            f"stack_snapshot: composante {cause} absente. Les huit "
            "composantes de la pile sont toutes normatives."
        ) from cause
    except (TypeError, ValueError) as cause:
        raise ProjectionImpossible(
            f"stack_snapshot illisible: {cause}"
        ) from cause

    attendue = str(_exige(ligne, "stack_digest"))
    if pile.digest.digest != attendue:
        raise ProjectionImpossible(
            f"la pile reconstruite vaut {pile.digest.digest[:16]}... et la "
            f"colonne stack_digest annonce {attendue[:16]}.... La recherche "
            "et la signature designeraient deux piles."
        )
    return pile


def _preuves(ligne: dict[str, Any]) -> tuple[EvidenceItem, ...]:
    brut = _json(_exige(ligne, "evidence_items"), "evidence_items")
    if not isinstance(brut, list) or not brut:
        raise ProjectionImpossible(
            "evidence_items ne porte aucun element: confirmer sans dire ce "
            "qu'on a lu n'est pas une lecture d'annexe."
        )
    try:
        return tuple(
            EvidenceItem(
                document_digest=str(i["document_digest"]),
                document_role=str(i["document_role"]),
                reference=str(i["reference"]),
                edition=str(i["edition"]),
                clause=str(i["clause"]),
                page_printed=int(i["page_printed"]),
                quote=str(i["quote"]),
                # ABSENT DU PAYLOAD, DONC ABSENT ICI. `page_pdf` est exclu de
                # l'empreinte de preuve: il ne fait pas autorite et change
                # avec le tirage du fichier. Le reconstituer serait l'inventer.
                page_pdf=None,
            )
            for i in brut
        )
    except KeyError as cause:
        raise ProjectionImpossible(
            f"evidence_items: champ {cause} absent d'un element de preuve."
        ) from cause
    except (TypeError, ValueError) as cause:
        raise ProjectionImpossible(
            f"evidence_items illisible: {cause}"
        ) from cause


def _habilitation(portee: Any, quoi: str) -> tuple[frozenset[str], str]:
    """Ce que le SERVEUR a fige au moment de la signature. Audit seulement.

    Deux formes, et ce module n'en invente aucune :

    * une portee resolue depuis une habilitation porte ``permission`` ;
    * une auto-revocation porte ``self_revocation`` et **aucune** permission,
      parce que retirer sa propre lecture n'en demande aucune.

    L'ensemble vide dit donc « aucune habilitation n'etait requise », ce qui
    est exact — et non « on n'a pas su lire ».
    """
    portee = _json(portee, quoi)
    if not isinstance(portee, dict):
        raise ProjectionImpossible(
            f"{quoi}: un objet est attendu, recu {type(portee).__name__}."
        )
    permission = portee.get("permission")
    permissions = frozenset({str(permission)}) if permission else frozenset()
    # Forme canonique et stable: c'est un instantane d'audit, il doit se
    # comparer d'une lecture a l'autre sans dependre de l'ordre des cles.
    return permissions, json.dumps(
        portee, sort_keys=True, separators=(",", ":"), default=str,
    )


def confirmation_depuis_ligne(ligne: dict[str, Any]) -> NormativeRuleConfirmation:
    """Une ligne de ``normative_rule_confirmations`` vers le domaine."""
    pile = _pile(ligne)
    preuves = _preuves(ligne)
    permissions, portee = _habilitation(
        _exige(ligne, "authorisation_scope"), "authorisation_scope",
    )

    confirmation = NormativeRuleConfirmation(
        confirmation_id=str(_exige(ligne, "id")),
        country_code=str(_exige(ligne, "country_code")),
        standard_family=str(_exige(ligne, "standard_family")),
        part=str(_exige(ligne, "part")),
        rule_id=str(_exige(ligne, "rule_id")),
        normative_spec=_empreinte(
            ligne, "normative_spec_payload", "normative_spec_digest",
        ),
        implementation=_empreinte(
            ligne, "implementation_payload", "implementation_digest",
        ),
        stack=pile,
        verifier_id=str(_exige(ligne, "verifier_id")),
        verifier_name=str(_exige(ligne, "verifier_name")),
        verified_at=_exige(ligne, "verified_at"),
        authorisations_at_signature=permissions,
        authorisation_scope_at_signature=portee,
        evidence_items=preuves,
        statement=str(_exige(ligne, "statement")),
        idempotency_key=str(_exige(ligne, "idempotency_key")),
    )

    # `evidence` est calcule par le domaine depuis les elements. La colonne
    # est ce que la recherche indexe. Les deux doivent dire le meme dossier.
    attendu = str(_exige(ligne, "evidence_digest"))
    if confirmation.evidence.digest != attendu:
        raise ProjectionImpossible(
            f"le dossier reconstruit vaut {confirmation.evidence.digest[:16]}"
            f"... et la colonne evidence_digest annonce {attendu[:16]}.... Le "
            "decompte a quatre yeux se fait sur cette empreinte: deux valeurs "
            "differentes, c'est deux dossiers."
        )
    return confirmation


def revocation_depuis_ligne(
    ligne: dict[str, Any],
) -> NormativeRuleConfirmationRevocation:
    """Une ligne de ``normative_rule_confirmation_revocations`` vers le domaine."""
    permissions, _ = _habilitation(
        _exige(ligne, "authorisation_scope"), "authorisation_scope",
    )
    return NormativeRuleConfirmationRevocation(
        revocation_id=str(_exige(ligne, "id")),
        confirmation_id=str(_exige(ligne, "confirmation_id")),
        revoked_by=str(_exige(ligne, "revoked_by")),
        revoked_by_name=str(_exige(ligne, "revoked_by_name")),
        revoked_at=_exige(ligne, "revoked_at"),
        authorisations_at_revocation=permissions,
        reason=str(_exige(ligne, "reason")),
    )
