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
from fastapi import APIRouter, Depends, HTTPException

from ..dependances import provider_de_lecture

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


def _pays_inconnu(pays: str) -> dict[str, Any]:
    """Le même refus pour les deux routes. Un seul texte, une seule vérité."""
    return {
        "code": "COUNTRY_NOT_IN_REFERENTIAL",
        "message": (
            f"aucun referentiel national pour « {pays} ». Un pays absent n'est "
            "pas un pays sans exigences: c'est un pays que ce moteur ne sait "
            "pas encore traiter."
        ),
        "countries": available_countries(),
    }


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
        raise HTTPException(status_code=404, detail=_pays_inconnu(pays))

    jeu = load_parameter_set(pays, strict=strict, as_of=as_of)
    rapport = jeu.preflight(required_parameters(DesignSituation.PERSISTENT))
    corps: dict[str, Any] = rapport.to_dict()

    # CE COMPTE DECRIT LE DEPOT, PAS CETTE INSTANCE, et il porte desormais ce
    # nom-la. Il vient des fichiers versionnes: il dit « 0 confirme » parce que
    # le depot n'ecrit jamais ce statut, et il dirait la meme chose sur une
    # instance ou deux ingenieurs ont signe vingt fois. Pour l'etat REEL d'une
    # instance, voir `GET /v1/ndp/{country}/couverture`.
    comptes = _comptes(pays, jeu.as_of)
    corps["transcription"] = comptes
    #: Ancien nom, conserve pour les appelants existants. Il designe la meme
    #: chose — le depot — et c'est precisement ce que son nom ne disait pas.
    corps["referentiel"] = comptes

    # LE FAIT CENTRAL, ET IL SE DIT EXACTEMENT.
    #
    # Une rédaction antérieure annonçait `signable_possible = confirmed > 0`.
    # C'était faux de deux façons à la fois. **Une** valeur confirmée n'ouvre
    # pas un calcul qui en exige **huit** : le compte global ne dit rien des
    # paramètres que ce calcul-là demande. Et « signable » promettait bien
    # au-delà : signer exige une validation humaine, un circuit documentaire
    # et des garanties de commercialisation dont rien ici ne répond.
    #
    # On rend donc le verdict du **préflight** — tous les paramètres requis
    # sont-ils utilisables — sous un nom qui ne dit que cela.
    corps["strict_ndp_satisfied"] = bool(rapport.ok) and strict
    corps["action"] = (
        "Faire relever chaque valeur dans l'Annexe Nationale publiee, a la "
        "page citee, par un ingenieur nomme; la confirmation se fait ensuite "
        "par le chemin d'autorite (proposition, approbation par un second "
        "ingenieur, consommation). Un fichier du depot ne peut pas confirmer."
    )
    return corps


@routeur.get("/{country}/couverture")
def couverture_du_referentiel(
    country: str,
    as_of: date | None = None,
    lecture: Any = Depends(provider_de_lecture),
) -> dict[str, Any]:
    """Trois états, séparés : transcrit, décidé en base, utilisable ici.

    POURQUOI CETTE ROUTE EXISTE À CÔTÉ DES DEUX AUTRES
    ----------------------------------------------------
    ``GET /v1/ndp/{country}`` compte ce que les **fichiers du dépôt** portent.
    Ce compte dit « 0 confirmé » et le dira toujours : le dépôt n'écrit jamais
    ce statut, et il n'a pas à l'écrire. Il ne décrit donc aucune instance —
    ni celle où personne n'a signé, ni celle où deux ingénieurs ont signé les
    dix-neuf paramètres d'une vérification belge.

    Cette route-ci répond à la question qu'on se pose devant l'écran : **ce
    calcul-là peut-il partir, sur cette base-ci ?** Elle interroge le provider
    réel, paramètre par paramètre, et rend les trois faits séparément parce
    qu'ils appellent trois gestes différents :

    * transcrit mais pas décidé → il faut faire passer le paramètre par le
      chemin d'autorité, à quatre yeux ;
    * décidé mais pas utilisable → le dossier signé ne porte pas sur ce que le
      registre détient aujourd'hui (valeur, édition, document, code) ;
    * pas transcrit → il faut ouvrir l'Annexe Nationale publiée.

    SANS BASE, LA RÉPONSE EST « NON INTERROGÉE », PAS « ZÉRO ». Les deux
    appellent des gestes opposés — brancher une base, ou faire relire un
    paramètre — et les confondre envoie l'ingénieur au mauvais endroit.

    La liste des paramètres requis vient des **modules**
    (``required_parameters_for_beam``), jamais d'une énumération recopiée : un
    chapitre qui en réclame un de plus le fait apparaître ici sans que
    personne y pense.
    """
    from eurostruct_engine.ec2.beam_verification import (
        required_parameters_for_beam,
    )
    from eurostruct_engine.ndp import couverture_du_calcul

    pays = country.upper()
    if pays not in available_countries():
        raise HTTPException(status_code=404, detail=_pays_inconnu(pays))

    jeu = load_parameter_set(pays, strict=True, as_of=as_of)
    provider = getattr(lecture, "provider", None) if lecture else None
    try:
        couverture = couverture_du_calcul(
            jeu, required_parameters_for_beam(pays), provider=provider)
    finally:
        if lecture is not None:
            lecture.fermer()

    corps = couverture.to_dict()
    corps["calcul"] = "verification de poutre EC2 — cinq chapitres"
    corps["transcription"] = _comptes(pays, jeu.as_of)
    corps["action"] = _action_de_couverture(couverture)
    return corps


def _action_de_couverture(couverture: Any) -> str:
    """Le geste suivant, nommé. Un état sans geste ne sert a personne."""
    if not couverture.base_interrogee:
        return (
            "aucune source de confirmation n'est branchee sur cette instance: "
            "le mode strict refusera quoi qu'il arrive. Configurer la base "
            "d'autorite (voir /ready), puis relancer ce diagnostic."
        )
    if couverture.prêt:
        return "les parametres requis sont confirmes: le mode strict peut partir."
    manquants = [p.key for p in couverture.parametres if not p.utilisable]
    jamais_decides = [p.key for p in couverture.parametres
                      if not p.utilisable and not p.decide_en_base]
    if jamais_decides:
        return (
            f"{len(manquants)} parametre(s) ne sont pas utilisables, dont "
            f"{len(jamais_decides)} sur lesquels aucune decision n'est "
            "enregistree. Les faire passer par le chemin d'autorite: un "
            "ingenieur propose depuis l'annexe publiee, un SECOND approuve, "
            "la decision est consommee."
        )
    return (
        f"{len(manquants)} parametre(s) portent une decision qui ne les ouvre "
        "pas: le dossier signe ne correspond plus a ce que le registre "
        "detient. Voir le motif de chacun, puis refaire passer le parametre "
        "par le chemin d'autorite."
    )


@routeur.get("/{country}/parameters")
def parametres_du_referentiel(
    country: str,
    as_of: date | None = None,
) -> dict[str, Any]:
    """Le plan de charge : **quels** paramètres, dans quel état, où les lire.

    POURQUOI CETTE ROUTE EXISTE À CÔTÉ DE LA PRÉCÉDENTE
    ----------------------------------------------------
    ``GET /v1/ndp/{country}`` dit « 0 sur 29 ». Il ne dit pas **lesquels**, et
    sa liste de blocages ne couvre que les huit paramètres dont le calcul de
    flexion a besoin. Or on ne planifie pas une campagne de relevé avec un
    compte : il faut la liste, avec pour chacun la clause, l'annexe, le folio
    imprimé et ce qui manque.

    ``usable_in_strict_mode`` est rendu **calculé par le domaine**, jamais
    recomposé ici : c'est la même propriété que le portillon consulte, et en
    écrire une seconde version créerait deux vérités.
    """
    pays = country.upper()
    if pays not in available_countries():
        raise HTTPException(status_code=404, detail=_pays_inconnu(pays))

    registre = load_country_registry(pays)
    a_la_date = as_of or date.today()

    parametres = []
    for annexe in registre.annexes:
        for parametre in annexe.parameters:
            if not parametre.is_in_force(a_la_date):
                continue
            fiche = parametre.to_dict()
            fiche["usable_in_strict_mode"] = parametre.usable_in_strict_mode
            # Ce qu'il RESTE A FAIRE, en un mot, plutot que de le faire
            # deduire du couple (statut, provenance) par chaque appelant.
            fiche["reste_a_faire"] = _reste_a_faire(parametre)
            parametres.append(fiche)

    parametres.sort(key=lambda f: (f["standard"], f["parameter_name"]))
    return {
        "country_code": pays,
        "as_of": a_la_date.isoformat(),
        "referentiel": _comptes(pays, a_la_date),
        "parameters": parametres,
    }


def _reste_a_faire(parametre: Any) -> str:
    """Ce qui manque, dit une fois, plutôt que déduit par chaque appelant."""
    if parametre.validation_status is ValidationStatus.NOT_REPRESENTABLE:
        return (
            "l'annexe fixe ce parametre sous une forme non scalaire; aucune "
            "relecture ne le debloque, c'est le module de calcul qui doit "
            "apprendre a evaluer l'expression"
        )
    if parametre.validation_status is ValidationStatus.DEPRECATED:
        return "valeur obsolete ou connue fausse; refusee dans TOUS les modes"
    if parametre.usable_in_strict_mode:
        return ""
    if not parametre.value_provenance.is_national:
        return (
            "le nombre ne vient pas de l'Annexe Nationale: le relever dans "
            "l'annexe publiee avant toute confirmation"
        )
    return (
        "relever la valeur dans l'annexe publiee, a la page citee, puis la "
        "faire confirmer par le chemin d'autorite"
    )
