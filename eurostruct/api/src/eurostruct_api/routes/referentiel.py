"""L'état du référentiel national. Ce que le produit peut, et ne peut pas.

POURQUOI CETTE ROUTE EXISTE
----------------------------
La réponse la plus fréquente de ce produit aujourd'hui est un **refus** : en
mode strict, aucun pays n'a de valeur nationale confirmée, et le calcul ne peut
pas aboutir. Jusqu'ici, la seule façon de l'apprendre était de **tenter un
calcul** et de lire le 422.

C'est une mauvaise façon de poser la question. « Où en est la Belgique ? » est
une question de bureau d'études, pas de projet : elle se pose avant qu'aucune
poutre ne soit saisie, elle porte sur le référentiel entier et non sur les huit
paramètres d'un calcul, et sa réponse sert à toutes les études du pays.

CE QUE CETTE ROUTE NE FAIT PAS
-------------------------------
Elle ne calcule rien et ne confirme rien. Elle **compte**, et le compte vient
du registre — jamais d'un total écrit à la main quelque part, qui se
désynchroniserait le jour où une annexe est transcrite.

Elle n'expose aucune donnée de locataire : le référentiel national est le même
pour tout le monde. Elle n'exige donc pas d'identité, comme le calcul lui-même.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from eurostruct_engine.basis import DesignSituation
from eurostruct_engine.ec2.beam_flexure import required_parameters
from eurostruct_engine.ndp import (
    ValidationStatus,
    available_countries,
    load_country_registry,
    load_parameter_set,
)
from fastapi import APIRouter, HTTPException

routeur = APIRouter(prefix="/v1/ndp", tags=["referentiel"])


def _comptes(country: str, a_la_date: date) -> dict[str, int]:
    """Combien de paramètres, dans quel état. Compté, jamais recopié.

    On ne compte que les paramètres **en vigueur à la date de référence**. Le
    registre conserve les éditions successives d'une annexe: les additionner
    donnerait un total qui grossit à chaque nouvelle édition sans qu'aucune
    valeur n'ait été relevée — un chiffre qui monte alors que rien n'avance.

    Mesuré le 30/08/2026 : aucun pays ne porte encore deux éditions du même
    paramètre, si bien que ce filtre ne retire rien aujourd'hui — 29 en vigueur
    sur 29 détenus, pour les quatre pays. Il est écrit maintenant parce que le
    jour où une seconde édition arrive, personne ne relira ce compte.
    """
    registre = load_country_registry(country)
    comptes = {statut.value: 0 for statut in ValidationStatus}
    total = 0
    for annexe in registre.annexes:
        for parametre in annexe.parameters:
            if not parametre.is_in_force(a_la_date):
                continue
            comptes[parametre.validation_status.value] += 1
            total += 1
    comptes["total"] = total
    return comptes


@routeur.get("/countries")
def pays_disponibles() -> dict[str, Any]:
    """Les pays pour lesquels un référentiel existe. Pas ceux qu'on vise."""
    return {"countries": available_countries()}


@routeur.get("/{country}")
def etat_du_referentiel(
    country: str,
    strict: bool = True,
    as_of: date | None = None,
) -> dict[str, Any]:
    """L'état du référentiel d'un pays, et ce qui bloque le calcul EC2 flexion.

    ``strict`` vaut ``true`` par défaut, comme dans le contrat de calcul. Le
    passer à ``false`` montre ce qui bloquerait **même** un calcul exploratoire
    — une valeur obsolète ou non représentable bloque dans tous les modes.
    """
    pays = country.upper()
    if pays not in available_countries():
        raise HTTPException(
            status_code=404,
            detail={
                "code": "COUNTRY_NOT_IN_REFERENTIAL",
                "message": (
                    f"aucun referentiel national pour « {pays} ». Un pays "
                    "absent n'est pas un pays sans exigences: c'est un pays "
                    "que ce moteur ne sait pas encore traiter."
                ),
                "countries": available_countries(),
            },
        )

    jeu = load_parameter_set(pays, strict=strict, as_of=as_of)
    rapport = jeu.preflight(required_parameters(DesignSituation.PERSISTENT))
    corps: dict[str, Any] = rapport.to_dict()

    comptes = _comptes(pays, jeu.as_of)
    corps["referentiel"] = comptes
    # LE FAIT CENTRAL, ECRIT SANS DETOUR. Zero valeur confirmee veut dire
    # qu'aucune note signable ne peut sortir de ce pays, quel que soit le
    # projet — et c'est ce qu'un chef de projet doit lire en premier.
    corps["signable_possible"] = comptes[ValidationStatus.CONFIRMED.value] > 0
    corps["action"] = (
        "Faire relever chaque valeur dans l'Annexe Nationale publiee, a la "
        "page citee, par un ingenieur nomme; la confirmation se fait ensuite "
        "par le chemin d'autorite (proposition, approbation par un second "
        "ingenieur, consommation). Un fichier du depot ne peut pas confirmer."
    )
    return corps
