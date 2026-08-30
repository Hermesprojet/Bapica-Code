"""La projection SQL → domaine, éprouvée sans base.

POURQUOI SANS BASE
-------------------
Ce que ces cas vérifient — qu'une ligne modifiée ne redevient pas une
confirmation — ne dépend d'aucun pilote. Les mettre derrière un décor
PostgreSQL les rendrait facultatifs le jour où le décor n'est pas là, et une
garantie facultative n'en est pas une. Le contrat SQL, lui, s'éprouve
séparément contre un vrai serveur (``db/test/api_e2e.sh``).

COMMENT LA LIGNE EST FABRIQUÉE
-------------------------------
Par ``ligne_pour``, qui reproduit **ce que le déclencheur SQL écrit** :
``stack_snapshot`` est ``stack_payload::jsonb`` et ``evidence_items`` est
``evidence_payload -> 'items'`` (migration 0010, § « Les projections jsonb
sont DERIVEES, jamais recues »). Une ligne fabriquée autrement prouverait la
projection contre une base imaginaire.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from test_confirmation_domain import confirmation, revocation

from eurostruct_engine.ndp.projection import (
    ProjectionImpossible,
    confirmation_depuis_ligne,
    revocation_depuis_ligne,
)

PORTEE = {
    "grant_id": "11111111-1111-1111-1111-111111111111",
    "permission": "can_validate_normative_reference",
    "country_code": "BE", "standard_family": "EN 1992", "part": "1-1",
    "edition": "2010", "granted_by": None,
    "granted_at": "2026-08-01T00:00:00+00:00", "origin": "delegated",
    "resolved_at": "2026-08-15T00:00:00+00:00",
}


def ligne_pour(c) -> dict:
    """La ligne telle que PostgreSQL la détient après le déclencheur."""
    return {
        "id": c.confirmation_id,
        "country_code": c.country_code,
        "standard_family": c.standard_family,
        "part": c.part,
        "rule_id": c.rule_id,
        "stack_digest": c.stack.digest.digest,
        "normative_spec_digest": c.normative_spec.digest,
        "implementation_digest": c.implementation.digest,
        "evidence_digest": c.evidence.digest,
        "digest_algorithm": c.normative_spec.algorithm,
        "canonicalization_version": c.normative_spec.canonicalization_version,
        "normative_spec_payload": c.normative_spec.canonical_payload,
        "implementation_payload": c.implementation.canonical_payload,
        # DERIVEES DES PAYLOADS, comme le fait le declencheur.
        "stack_snapshot": json.loads(c.stack.digest.canonical_payload),
        "evidence_items": json.loads(c.evidence.canonical_payload)["items"],
        "statement": c.statement,
        "verifier_id": c.verifier_id,
        "verifier_name": c.verifier_name,
        "verified_at": c.verified_at,
        "authorisation_scope": dict(PORTEE),
        "idempotency_key": c.idempotency_key,
    }


def ligne_revocation(r) -> dict:
    return {
        "id": r.revocation_id,
        "confirmation_id": r.confirmation_id,
        "revoked_by": r.revoked_by,
        "revoked_by_name": r.revoked_by_name,
        "revoked_at": r.revoked_at,
        "authorisation_scope": dict(PORTEE),
        "reason": r.reason,
    }


# ---------------------------------------------------------------------------
# Aller-retour: la projection est l'inverse exact de ce que le serveur ecrit
# ---------------------------------------------------------------------------
def test_une_confirmation_traverse_la_base_sans_rien_perdre() -> None:
    origine = confirmation()
    relue = confirmation_depuis_ligne(ligne_pour(origine))

    # LE SUJET, qui est ce que le decompte a quatre yeux compare.
    assert relue.confirmation_subject_key == origine.confirmation_subject_key
    assert relue.reviewer_attestation_key == origine.reviewer_attestation_key

    # LES EMPREINTES, payload compris: une empreinte sans son payload ne dit
    # plus ce qui a ete signe.
    assert relue.normative_spec == origine.normative_spec
    assert relue.implementation == origine.implementation
    assert relue.stack == origine.stack
    assert relue.evidence == origine.evidence

    # CE QUE LE RELECTEUR A DIT, ET QUI L'A DIT.
    assert relue.statement == origine.statement
    assert relue.verifier_id == origine.verifier_id
    assert relue.verifier_name == origine.verifier_name
    assert relue.verified_at == origine.verified_at
    assert relue.idempotency_key == origine.idempotency_key
    assert len(relue.evidence_items) == len(origine.evidence_items)


def test_l_habilitation_relue_est_celle_que_le_serveur_a_figee() -> None:
    relue = confirmation_depuis_ligne(ligne_pour(confirmation()))
    assert relue.authorisations_at_signature == frozenset(
        {"can_validate_normative_reference"}
    )
    # Forme canonique: deux lectures de la meme portee donnent la meme chaine.
    assert relue.authorisation_scope_at_signature == json.dumps(
        PORTEE, sort_keys=True, separators=(",", ":"), default=str,
    )


def test_une_revocation_traverse_la_base_sans_rien_perdre() -> None:
    origine = revocation(confirmation())
    relue = revocation_depuis_ligne(ligne_revocation(origine))
    assert relue.revocation_id == origine.revocation_id
    assert relue.confirmation_id == origine.confirmation_id
    assert relue.revoked_by == origine.revoked_by
    assert relue.revoked_at == origine.revoked_at
    assert relue.reason == origine.reason


def test_une_auto_revocation_ne_porte_aucune_habilitation() -> None:
    """Retirer SA PROPRE lecture n'en demande aucune — et l'ensemble vide le dit.

    Le declencheur ecrit alors une portee sans ``permission``. Un ensemble
    vide doit se lire « aucune habilitation n'etait requise », pas « on n'a
    pas su lire »: c'est pour cela que la projection ne devine pas.
    """
    ligne = ligne_revocation(revocation(confirmation()))
    ligne["authorisation_scope"] = {
        "self_revocation": True, "verifier_id": "FICTIF-alice",
        "resolved_at": "2026-08-16T00:00:00+00:00",
    }
    assert revocation_depuis_ligne(ligne).authorisations_at_revocation == frozenset()


def test_le_jsonb_rendu_en_texte_est_accepte() -> None:
    """Tous les pilotes ne decodent pas ``jsonb``; celui qui ne le fait pas
    rend du texte, et une projection qui ne le prevoit pas echoue en
    production sur un pilote different de celui du poste de developpement."""
    ligne = ligne_pour(confirmation())
    ligne["stack_snapshot"] = json.dumps(ligne["stack_snapshot"])
    ligne["evidence_items"] = json.dumps(ligne["evidence_items"])
    ligne["authorisation_scope"] = json.dumps(ligne["authorisation_scope"])
    assert confirmation_depuis_ligne(ligne).confirmation_id


# ---------------------------------------------------------------------------
# Falsifications: une base modifiee ne redevient pas une confirmation
# ---------------------------------------------------------------------------
def test_un_payload_de_specification_retouche_est_refuse() -> None:
    """L'empreinte et son payload sont lus ENSEMBLE, et confrontes.

    Recalculer l'empreinte depuis le payload remplacerait la verification par
    une tautologie: elle passerait toujours.
    """
    ligne = ligne_pour(confirmation())
    origine = ligne["normative_spec_payload"]
    retouche = json.loads(origine)
    retouche["rule_id"] = retouche.get("rule_id", "") + "-retouche"
    ligne["normative_spec_payload"] = json.dumps(
        retouche, sort_keys=True, separators=(",", ":"),
    )
    # LA RETOUCHE DOIT AVOIR EU LIEU. Une premiere redaction remplacait
    # « 0.6 », absent de ce payload: le cas ne pouvait pas echouer, donc ne
    # protegeait rien.
    assert ligne["normative_spec_payload"] != origine
    with pytest.raises(Exception, match=r"empreinte|annoncee|calculee"):
        confirmation_depuis_ligne(ligne)


def test_une_empreinte_de_specification_retouchee_est_refusee() -> None:
    """La falsification symetrique: le hash change, le payload non."""
    ligne = ligne_pour(confirmation())
    ligne["normative_spec_digest"] = "0" * 64
    with pytest.raises(Exception, match=r"empreinte|annoncee|calculee"):
        confirmation_depuis_ligne(ligne)


def test_une_pile_substituee_est_refusee() -> None:
    """La colonne indexee et la pile signee doivent dire la meme pile."""
    ligne = ligne_pour(confirmation())
    instantane = dict(ligne["stack_snapshot"])
    composants = [dict(c) for c in instantane["components"]]
    composants[-1]["edition"] = "2018"
    instantane["components"] = composants
    ligne["stack_snapshot"] = instantane
    with pytest.raises(ProjectionImpossible, match="deux piles"):
        confirmation_depuis_ligne(ligne)


def test_un_dossier_de_preuve_retouche_est_refuse() -> None:
    """La citation change: le decompte a quatre yeux porte sur ce dossier."""
    ligne = ligne_pour(confirmation())
    elements = [dict(i) for i in ligne["evidence_items"]]
    elements[0]["quote"] = "texte que personne n'a lu"
    ligne["evidence_items"] = elements
    with pytest.raises(ProjectionImpossible, match="deux dossiers"):
        confirmation_depuis_ligne(ligne)


def test_une_page_imprimee_retouchee_est_refusee() -> None:
    """Le folio imprime EST dans l'empreinte; c'est ce qu'un ingenieur rouvre."""
    ligne = ligne_pour(confirmation())
    elements = [dict(i) for i in ligne["evidence_items"]]
    elements[0]["page_printed"] = elements[0]["page_printed"] + 1
    ligne["evidence_items"] = elements
    with pytest.raises(ProjectionImpossible, match="deux dossiers"):
        confirmation_depuis_ligne(ligne)


def test_une_version_de_canonicalisation_inconnue_est_refusee() -> None:
    ligne = ligne_pour(confirmation())
    ligne["canonicalization_version"] = "esc-canon/2"
    with pytest.raises(ProjectionImpossible, match="canonicalisation"):
        confirmation_depuis_ligne(ligne)


@pytest.mark.parametrize("colonne", [
    "statement", "verifier_name", "idempotency_key", "stack_snapshot",
    "evidence_items", "authorisation_scope", "normative_spec_payload",
])
def test_une_colonne_nulle_est_un_refus_pas_un_defaut(colonne: str) -> None:
    """Une valeur par defaut n'a ete lue par personne."""
    ligne = ligne_pour(confirmation())
    ligne[colonne] = None
    with pytest.raises(ProjectionImpossible, match=colonne):
        confirmation_depuis_ligne(ligne)


def test_une_colonne_absente_est_un_refus() -> None:
    ligne = ligne_pour(confirmation())
    del ligne["verifier_id"]
    with pytest.raises(ProjectionImpossible, match="verifier_id"):
        confirmation_depuis_ligne(ligne)


def test_un_dossier_vide_est_refuse() -> None:
    ligne = ligne_pour(confirmation())
    ligne["evidence_items"] = []
    with pytest.raises(ProjectionImpossible, match="aucun element"):
        confirmation_depuis_ligne(ligne)


def test_un_horodatage_sans_fuseau_est_refuse() -> None:
    """Un instant sans fuseau n'est pas un instant: il en designe autant qu'il
    y a de fuseaux, et une confirmation est datee."""
    ligne = ligne_pour(confirmation())
    ligne["verified_at"] = datetime(2026, 8, 15, 12, 0, 0)
    with pytest.raises(Exception, match="fuseau"):
        confirmation_depuis_ligne(ligne)
    # Le meme instant, avec son fuseau, passe.
    ligne["verified_at"] = datetime(2026, 8, 15, 12, 0, 0, tzinfo=UTC)
    assert confirmation_depuis_ligne(ligne).verified_at.tzinfo is not None
