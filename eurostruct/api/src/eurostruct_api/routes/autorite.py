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
avec son message. On ne le retraduit pas en 200 avec un drapeau, et on ne le
maquille pas en 500.

TROIS ISSUES, ET PAS UNE DE PLUS
---------------------------------
* ``AuthentificationRequise`` -> **401**, avec ``WWW-Authenticate: Bearer`` ;
* ``ConfirmationDomainError`` -> **422**, avec le message contrôlé du domaine ;
* tout le reste -> il **remonte**, et le gestionnaire global rend un **500**
  générique avec un identifiant de corrélation.

La troisième ligne est le correctif. Ces routes attrapaient ``Exception`` et
rendaient ``str(cause)`` en 422 : le message d'une ``OperationalError`` porte
la chaîne de connexion — mot de passe compris — et celui d'une erreur SQL porte
le nom de la table et le fragment de requête. Tout cela partait au client, sous
un code qui se lit « votre demande est refusée » : aucune alerte, et le défaut
dure.

Le tri entre « PostgreSQL refuse exprès » et « PostgreSQL est cassé » ne se
fait pas ici — cette couche ne voit que des exceptions de pilote. Il se fait à
la frontière du SQL, dans ``postgres_provider.RefusSqlTraduits``, sur le
SQLSTATE que le serveur pose lui-même.
"""
from __future__ import annotations

import json
from typing import Any

from eurostruct_engine.ndp import available_countries, load_parameter_set
from eurostruct_engine.ndp.confirmation import ConfirmationDomainError
from eurostruct_engine.ndp.dossier import (
    CitationDeRevue,
    composer_dossier,
    empreintes_des_payloads,
)
from eurostruct_engine.ndp.postgres_provider import AuthentificationRequise
from eurostruct_engine.schemas.autorite import (
    AuthorityDecisionConsumed,
    AuthorityDecisionCreated,
    AuthorityDecisionRequest,
    AuthorityDecisionReview,
    AuthorityReviewDossier,
    AuthorityReviewDraftRequest,
    AuthorityReviewPackage,
)
from fastapi import APIRouter, Depends, HTTPException

from ..dependances import jeton_porteur, ouvrir_provider

routeur = APIRouter(prefix="/v1/authority", tags=["autorite"])

#: LES TROIS FORMES SONT GENEREES, PAS DECLAREES ICI.
#:
#: Elles vivaient dans ce module, que `export_contracts.py` ne lit pas: le
#: navigateur n'avait donc aucun type genere pour le chemin d'autorite, et tout
#: client devait recopier la forme en TypeScript. Une forme recopiee derive au
#: premier champ renomme — et ce champ-la decide qui peut confirmer une valeur
#: nationale.
ProposerRequete = AuthorityDecisionRequest
DecisionCreee = AuthorityDecisionCreated
DecisionConsommee = AuthorityDecisionConsumed


def _parametre_du_registre(pays: str, rule_id: str):
    """L'entrée du registre, ou un refus qui dit ce qui manque.

    Le mode **non strict** est délibéré : c'est justement le paramètre pas
    encore confirmé qu'on veut faire relire. Le charger en strict rendrait
    introuvable exactement ce que le parcours d'autorité existe pour débloquer.
    """
    if pays not in available_countries():
        raise HTTPException(
            status_code=404,
            detail={"error": "referentiel_absent", "what": pays,
                    "detail": (f"aucun referentiel national pour « {pays} ». "
                               "Un pays absent n'est pas un pays sans "
                               "exigences: c'est un pays que ce moteur ne sait "
                               "pas encore traiter.")},
        )
    parametre = load_parameter_set(pays, strict=False).find(rule_id)
    if parametre is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "parametre_absent", "what": rule_id,
                    "detail": (f"« {rule_id} » n'est pas dans le registre de "
                               f"{pays}. On ne compose pas un dossier de revue "
                               "pour un parametre qui n'existe pas.")},
        )
    return parametre


def _refus(cause: AuthentificationRequise | ConfirmationDomainError) -> HTTPException:
    """Traduit un refus CONNU. Une exception inattendue ne passe pas par ici.

    LES TROIS ROUTES TRANSFORMAIENT TOUTE EXCEPTION EN 422 AVEC ``str(cause)``.
    Le raisonnement — « un refus SQL reste un refus » — vaut pour
    ``ConfirmationDomainError``, dont le message est écrit pour être lu par
    l'ingénieur qu'il concerne. Il ne vaut pour rien d'autre.

    ``psycopg2.OperationalError`` porte la chaîne de connexion, **mot de passe
    compris** ; ``UndefinedTable`` porte le nom de la table et le fragment de
    requête. Tout cela partait au client, sous un code qui range le défaut dans
    « l'utilisateur a mal demandé » : aucune alerte, aucun tableau de bord, et
    le défaut dure.

    Cette fonction n'accepte donc plus que les deux refus qu'on sait nommer.
    Le reste remonte au gestionnaire global, qui rend un **500** générique avec
    un identifiant de corrélation.
    """
    if isinstance(cause, AuthentificationRequise):
        return HTTPException(
            status_code=401,
            detail={"error": "authentification_refusee",
                    "what": "jeton",
                    # Le message de l'authentificateur est écrit pour l'appelant
                    # (« signature invalide », « jeton expiré ») et ne cite
                    # aucun élément d'infrastructure.
                    "detail": str(cause)},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return HTTPException(
        status_code=422,
        detail={"error": "decision_refusee",
                "what": type(cause).__name__,
                "detail": str(cause)},
    )


@routeur.post("/review-packages", response_model=AuthorityReviewDossier)
def composer(corps: AuthorityReviewDraftRequest,
             _jeton: str = Depends(jeton_porteur)) -> AuthorityReviewDossier:
    """Compose le dossier d'un paramètre. **Le serveur seul le fabrique.**

    LE NAVIGATEUR NE CONSTRUIT AUCUNE EMPREINTE NORMATIVE. Il nomme le
    paramètre et fournit la matière humaine — ce que l'ingénieur a relevé dans
    l'annexe publiée — et reçoit les quatre payloads canoniques, leurs
    empreintes et le résumé à afficher. Le laisser canonicaliser lui-même
    ferait dépendre l'empreinte de la sérialisation d'un client, et ferait
    venir la **valeur** de l'écran plutôt que du registre.

    LE JETON EST EXIGE, MEME SANS ECRITURE. Un dossier nomme le document, la
    clause et le folio d'une annexe sous licence : ce n'est pas une donnée
    publique. Aucune connexion n'est ouverte pour autant — rien n'est écrit,
    et le registre est en mémoire.
    """
    parametre = _parametre_du_registre(corps.country_code.upper(), corps.rule_id)
    try:
        dossier = composer_dossier(
            parametre,
            statement=corps.statement,
            implementation_note=corps.implementation_note,
            effet=corps.effect,
            citations=tuple(
                CitationDeRevue(
                    document_digest=c.document_digest,
                    quote=c.quote,
                    page_printed=c.page_printed,
                    page_pdf=c.page_pdf,
                )
                for c in corps.citations
            ),
        )
    except ConfirmationDomainError as cause:
        raise _refus(cause) from cause
    return AuthorityReviewDossier(
        package=AuthorityReviewPackage(**dossier.payloads()),
        digests=dossier.empreintes(),
        summary=dossier.resume,
    )


@routeur.get("/decisions/{decision_id}", response_model=AuthorityDecisionReview)
def relire(decision_id: str,
           jeton: str = Depends(jeton_porteur),
           ouvert: Any = Depends(ouvrir_provider)) -> AuthorityDecisionReview:
    """Le dossier **gelé**, tel que la base le conserve. Pour le second regard.

    B n'a que l'identifiant : A s'est déconnecté, et son jeton est parti avec
    lui. Sans cette relecture, « B a approuvé » voudrait dire « B a cliqué sur
    un numéro » — exactement le quatre-yeux décoratif que le dispositif existe
    pour empêcher.

    LES EMPREINTES SONT RECALCULEES SUR CE QUI EST RELU, pas reprises d'un
    champ stocké. Une empreinte conservée à côté de son payload s'accorde avec
    lui par construction et ne prouve rien.
    """
    try:
        ligne = ouvert.provider.relire_decision(jeton, decision_id=decision_id)
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        raise _refus(cause) from cause
    finally:
        ouvert.fermer()

    brut = ligne.get("review_package")
    paquet = None
    empreintes: dict[str, str] = {}
    if brut is not None:
        # psycopg2 rend le `jsonb` déjà décodé; un pilote qui rendrait la
        # chaîne ne doit pas faire échouer la relecture pour autant.
        contenu = json.loads(brut) if isinstance(brut, str | bytes) else brut
        paquet = AuthorityReviewPackage(**contenu)
        empreintes = empreintes_des_payloads(
            normative_spec_payload=paquet.normative_spec_payload,
            implementation_payload=paquet.implementation_payload,
            evidence_payload=paquet.evidence_payload,
            stack_payload=paquet.stack_payload,
        )

    return AuthorityDecisionReview(
        decision_id=str(ligne["decision_id"]),
        state=str(ligne["state"]),
        subject_kind=ligne["subject_kind"],
        subject_id=ligne["subject_id"],
        org_id=str(ligne["org_id"]) if ligne.get("org_id") else None,
        country_code=ligne["country_code"],
        standard_family=ligne["standard_family"],
        part=ligne["part"],
        edition=ligne["edition"],
        permission=str(ligne["permission"]),
        reason=ligne["reason"],
        proposed_at=str(ligne["proposed_at"]),
        package=paquet,
        digests=empreintes,
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
            # LE DOSSIER PART SERIALISE, ET SANS AUCUNE EMPREINTE. Le serveur
            # recalcule les quatre empreintes sur les payloads: en accepter
            # une reviendrait a laisser annoncer un resume qui ne resume pas
            # ce qui sera stocke.
            review_package=(
                corps.review_package.model_dump_json(exclude_none=True)
                if corps.review_package is not None else None
            ),
        )
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        raise _refus(cause) from cause
    finally:
        # LA CONNEXION EST RENDUE SUR TOUS LES CHEMINS, celui de l'exception
        # inattendue compris. Une connexion non rendue ne se voit pas au
        # premier appel: elle se voit au millieme, quand le pool est vide et
        # que tout refuse.
        #
        # Aucun `except Exception` ici: une panne de pilote n'est pas un refus
        # de decision, et la faire passer pour tel a coute la chaine de
        # connexion en clair dans les reponses.
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
    finally:
        # Voir `proposer`: on ferme toujours, et on ne traduit que ce qu'on
        # sait nommer.
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
    finally:
        # Voir `proposer`: on ferme toujours, et on ne traduit que ce qu'on
        # sait nommer.
        ouvert.fermer()
    return DecisionConsommee(decision_id=decision_id, consumed=bool(ligne))
