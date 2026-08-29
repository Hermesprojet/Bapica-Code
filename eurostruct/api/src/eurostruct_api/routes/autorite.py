"""Les trois primitives du quatre-yeux, sous identité vérifiée.

AUCUN CORPS DE REQUÊTE NE NOMME UN ACTEUR
------------------------------------------
``ProposerRequete`` porte le SUJET de la décision et sa portée. Il ne porte ni
proposant, ni approbateur, ni ``actor_id`` : ces trois-là sortent du jeton, et
un champ qui les accepterait rendrait la vérification décorative — il
suffirait de mentir dans le corps.

C'est aussi pour cela que ``approuver`` et ``consommer`` ne prennent qu'un
identifiant de décision. L'identité de celui qui approuve est celle du jeton
présenté ; PostgreSQL refuse ensuite que ce soit la même que le proposant, par
contrainte de table et non par vérification applicative.

CE QUE CETTE COUCHE NE RATTRAPE PAS
------------------------------------
Un refus du domaine (``ConfirmationDomainError``) reste un refus : **422**,
avec le message de PostgreSQL. On ne le retraduit pas en 200 avec un drapeau,
et on ne le maquille pas en 500.
"""
from __future__ import annotations

from typing import Any

from eurostruct_engine.ndp.confirmation import ConfirmationDomainError
from eurostruct_engine.ndp.postgres_provider import AuthentificationRequise
from eurostruct_engine.schemas.common import Strict
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field

from ..dependances import jeton_porteur, ouvrir_provider

routeur = APIRouter(prefix="/v1/authority", tags=["autorite"])


class ProposerRequete(Strict):
    """Ce sur quoi la décision porte. Jamais qui la propose."""

    subject_kind: str = Field(description="Nature du sujet, ex. « ndp_parameter ».")
    subject_id: str = Field(description="Identifiant du sujet.")
    org_id: str | None = Field(default=None)
    country_code: str = Field(min_length=2, max_length=2)
    standard_family: str
    part: str
    edition: str
    permission: str
    reason: str = Field(description="Motif lisible. Une donnee, pas une preuve.")


class DecisionCreee(Strict):
    decision_id: str


class DecisionConsommee(Strict):
    decision_id: str
    consumed: bool


def _refus(cause: Exception) -> HTTPException:
    """Traduit un refus du domaine en 422, une auth manquante en 401."""
    if isinstance(cause, AuthentificationRequise):
        return HTTPException(
            status_code=401,
            detail={"error": "authentification_refusee",
                    "what": "jeton",
                    "detail": str(cause)},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return HTTPException(
        status_code=422,
        detail={"error": "decision_refusee",
                "what": type(cause).__name__,
                "detail": str(cause)},
    )


@routeur.post("/decisions", response_model=DecisionCreee, status_code=201)
def proposer(corps: ProposerRequete,
             jeton: str = Depends(jeton_porteur),
             ouvert: Any = Depends(ouvrir_provider)) -> DecisionCreee:
    """Propose une décision. Le proposant est le porteur du jeton."""
    try:
        decision_id = ouvert.provider.proposer_decision(
            jeton,
            subject_kind=corps.subject_kind,
            subject_id=corps.subject_id,
            org_id=corps.org_id,
            country_code=corps.country_code,
            standard_family=corps.standard_family,
            part=corps.part,
            edition=corps.edition,
            permission=corps.permission,
            reason=corps.reason,
        )
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        raise _refus(cause) from cause
    except Exception as cause:  # noqa: BLE001 — un refus SQL reste un refus
        raise _refus(cause) from cause
    finally:
        ouvert.fermer()
    if not decision_id:
        # PAS DE 201 VIDE. Une decision sans identifiant n'a pas ete creee.
        raise HTTPException(
            status_code=422,
            detail={"error": "decision_refusee", "what": "decision_id",
                    "detail": "la primitive n'a rendu aucun identifiant."},
        )
    return DecisionCreee(decision_id=decision_id)


@routeur.post("/decisions/{decision_id}/approval", status_code=204)
def approuver(decision_id: str,
              jeton: str = Depends(jeton_porteur),
              ouvert: Any = Depends(ouvrir_provider)) -> None:
    """Approuve. L'approbateur est le porteur du jeton, et lui seul.

    PostgreSQL refuse que ce soit le proposant. Cette couche ne le vérifie pas
    une seconde fois : deux vérifications concurrentes, c'est une de trop, et
    c'est toujours la plus faible qui finit par décider.
    """
    try:
        ouvert.provider.approuver_decision(jeton, decision_id=decision_id)
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        raise _refus(cause) from cause
    except Exception as cause:  # noqa: BLE001
        raise _refus(cause) from cause
    finally:
        ouvert.fermer()


@routeur.post("/decisions/{decision_id}/consumption",
              response_model=DecisionConsommee)
def consommer(decision_id: str,
              jeton: str = Depends(jeton_porteur),
              ouvert: Any = Depends(ouvrir_provider)) -> DecisionConsommee:
    """Consomme une décision approuvée. Une seule fois : le rejeu est refusé."""
    try:
        ligne = ouvert.provider.consommer_decision(jeton, decision_id=decision_id)
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        raise _refus(cause) from cause
    except Exception as cause:  # noqa: BLE001
        raise _refus(cause) from cause
    finally:
        ouvert.fermer()
    return DecisionConsommee(decision_id=decision_id, consumed=bool(ligne))
