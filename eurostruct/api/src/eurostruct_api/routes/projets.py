"""L'atelier : des projets réels, et des calculs qui survivent au rechargement.

CE QUE CES ROUTES REMPLACENT
-----------------------------
``project_id: "DEMO-001"``, écrit en dur dans l'interface et transmis au moteur
comme un simple libellé de note. Un calcul lancé depuis l'écran vivait dans la
réponse HTTP et mourait avec elle : rechargement, plus rien. Les tables
``projects``, ``calculations``, ``results`` et ``verifications`` existaient
depuis la première migration et n'avaient jamais reçu une ligne par le chemin
produit.

D'OÙ VIENT L'ORGANISATION
--------------------------
Du jeton, puis de ``organization_members``. **Jamais du corps de la requête.**
Aucune route n'accepte ``org_id`` ; ``POST /v1/projects`` accepte un
``organization_id`` facultatif, que PostgreSQL confronte aux appartenances
avant d'en faire quoi que ce soit — c'est un choix parmi les organisations de
l'appelant, pas une affirmation qu'on croit.

L'isolation elle-même n'est pas vérifiée ici : elle est dans les primitives et
dans les politiques RLS. Une vérification applicative de plus donnerait deux
frontières, dont la plus faible finirait par décider.

CE QUE CES ROUTES NE DISENT JAMAIS
-----------------------------------
« Final », « signable », « validé ». Un calcul enregistré est un calcul
enregistré. La mention obligatoire — ce document doit être vérifié et signé par
un ingénieur habilité — accompagne un calcul relu comme elle accompagne un
calcul neuf, et aucun champ ne la contredit.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from eurostruct_engine.exceptions import EurostructEngineError
from eurostruct_engine.ndp.confirmation import ConfirmationDomainError
from eurostruct_engine.ndp.postgres_provider import AuthentificationRequise
from eurostruct_engine.schemas.atelier import (
    CalculDeProjetRequest,
    CalculEnregistre,
    CalculResume,
    HistoriqueCalculs,
    ListeProjets,
    Projet,
    ProjetCreation,
)
from eurostruct_engine.schemas.ec2_beam import Ec2BeamFlexureRequest
from eurostruct_engine.service import error_of, run_ec2_beam_flexure
from fastapi import APIRouter, Depends, HTTPException

from ..dependances import ouvrir_atelier, provider_de_lecture
from .calculs import MENTION_NON_SIGNABLE, MENTION_OBLIGATOIRE

routeur = APIRouter(prefix="/v1/projects", tags=["atelier"])


def _refus(cause: AuthentificationRequise | ConfirmationDomainError) -> HTTPException:
    """Traduit un refus CONNU. Une exception inattendue ne passe pas par ici.

    Même règle que sur le chemin d'autorité : ``psycopg2.OperationalError``
    porte la chaîne de connexion, mot de passe compris. Attraper ``Exception``
    pour en faire un 422 avec ``str(cause)`` ferait sortir cela au client, sous
    un code qui se lit « votre demande est refusée » — donc sans alerte.

    Le tri entre « PostgreSQL refuse exprès » et « PostgreSQL est cassé » se
    fait à la frontière du SQL, dans ``postgres_provider.RefusSqlTraduits``,
    sur le SQLSTATE que le serveur pose lui-même.
    """
    if isinstance(cause, AuthentificationRequise):
        return HTTPException(
            status_code=401,
            detail={"error": "authentification_refusee", "what": "jeton",
                    "detail": str(cause)},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return HTTPException(
        status_code=422,
        detail={"error": "atelier_refuse", "what": type(cause).__name__,
                "detail": str(cause)},
    )


def _empreinte_des_entrees(requete: Ec2BeamFlexureRequest) -> str:
    """L'empreinte de la requête EXACTE, canonicalisée avant d'être hachée.

    ``inputs_hash`` existe depuis la première migration et sert à dire « deux
    calculs de même empreinte doivent produire le même résultat ». Sans tri des
    clés, deux sérialisations des mêmes entrées donneraient deux empreintes, et
    la propriété ne dirait plus rien.
    """
    charge = json.dumps(requete.model_dump(mode="json"), sort_keys=True,
                        ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(charge.encode("utf-8")).hexdigest()


@routeur.get("", response_model=ListeProjets)
def lister(ouvert: Any = Depends(ouvrir_atelier)) -> ListeProjets:
    """Les projets des organisations de l'appelant.

    AUCUN PARAMÈTRE NE NOMME UNE ORGANISATION. « Mes projets » est une question
    dont la réponse est en base ; l'accepter en paramètre laisserait demander
    ceux d'un autre — les politiques l'en empêcheraient, mais la signature
    aurait déjà dit que la question se pose.
    """
    try:
        projets = ouvert.atelier.projets(_jeton_de(ouvert))
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        raise _refus(cause) from cause
    finally:
        ouvert.fermer()
    return ListeProjets(projects=[Projet(**p) for p in projets])


@routeur.post("", response_model=Projet, status_code=201)
def creer(corps: ProjetCreation,
          ouvert: Any = Depends(ouvrir_atelier)) -> Projet:
    """Crée un projet, dans une organisation de l'appelant.

    LA DATE DE RÉFÉRENCE RÉSOUT LE RÉFÉRENTIEL, et le fige. Sans elle,
    l'édition d'Annexe Nationale applicable dépendrait de la date à laquelle le
    calcul est lancé — c'est-à-dire du hasard. Aucune annexe en vigueur à cette
    date est un **refus nommé**, jamais « celle d'à côté » : inventer un
    référentiel est exactement ce que l'interdiction n° 2 ferme.

    LA RELECTURE SUIT LA CRÉATION, dans la même requête. Rendre l'identifiant
    seul obligerait l'écran à un second appel pour afficher le projet qu'il
    vient de créer, et à le construire de son côté en attendant — donc à
    afficher des champs que la base n'a pas confirmés.
    """
    jeton = _jeton_de(ouvert)
    try:
        identifiant = ouvert.atelier.creer_projet(
            jeton,
            name=corps.name,
            reference=corps.reference,
            country=corps.country.value if hasattr(corps.country, "value")
            else str(corps.country),
            region=corps.region,
            ndp_as_of=corps.ndp_as_of,
            organization_id=corps.organization_id,
        )
        cree = [p for p in ouvert.atelier.projets(jeton)
                if p["project_id"] == identifiant]
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        raise _refus(cause) from cause
    finally:
        ouvert.fermer()
    if not cree:
        # CRÉÉ PUIS INVISIBLE N'EST PAS UN SUCCÈS. Le cas signalerait une
        # politique de lecture plus étroite que la politique d'écriture, et
        # rendre l'identifiant seul laisserait l'écran pointer un projet que
        # son auteur ne peut pas ouvrir.
        raise HTTPException(
            status_code=422,
            detail={"error": "atelier_refuse", "what": "relecture",
                    "detail": ("le projet a ete cree et n'est pas relisible "
                               "par son auteur. On refuse plutot que "
                               "d'annoncer un projet inatteignable.")},
        )
    return Projet(**cree[0])


@routeur.post("/{project_id}/calculations/ec2/beam-flexure",
              response_model=CalculEnregistre, status_code=201)
def calculer_et_enregistrer(
    project_id: str,
    corps: CalculDeProjetRequest,
    ouvert: Any = Depends(ouvrir_atelier),
    lecture: Any = Depends(provider_de_lecture),
) -> CalculEnregistre:
    """Lance le calcul **dans le référentiel du projet**, puis l'enregistre.

    LE CONTEXTE NORMATIF NE VIENT PAS DU CORPS, ET C'EST LE CORRECTIF.
    ``CalculDeProjetRequest`` ne porte ni ``project_id``, ni ``country``, ni
    ``region``, ni ``as_of`` : les quatre sont lus **sur le projet**, chargé
    sous l'identité authentifiée, et la requête moteur est construite ici.

    Mesuré avant : un corps annonçant ``country=FR`` et ``as_of=2030-01-01``
    sur un projet belge daté de 2024 obtenait un **201**. Le moteur appliquait
    le référentiel français ; PostgreSQL écrivait ``ndp_as_of`` depuis le
    projet. La ligne enregistrée se contredisait elle-même, et c'est elle
    qu'un audit lit des années plus tard.

    LA GARANTIE N'EST PAS ICI, ELLE EST DOUBLÉE ICI.
    ``project_calculation_record`` confronte elle-même les quatre champs au
    projet et refuse l'écart (0019). Cette route ne peut pas produire une
    requête divergente ; la primitive garantit que la prochaine ne le pourra
    pas non plus.

    LE MOTEUR EST LE MÊME, ET IL N'EST PAS RÉÉCRIT. ``run_ec2_beam_flexure``
    est appelé exactement comme par la route exploratoire.

    UN REFUS EST ENREGISTRÉ COMME REFUS. Le mode strict qui refuse faute de
    paramètre national confirmé n'est pas une panne : c'est une réponse du
    moteur. Elle est écrite avec ``status='refused'`` et son motif structuré,
    puis rendue en **422**.
    """
    jeton = _jeton_de(ouvert)

    # LE PROJET D'ABORD, ET SOUS L'IDENTITE AUTHENTIFIEE. Il porte le
    # referentiel; le charger avant de calculer evite de faire tourner le
    # moteur pour un projet qu'on n'a pas le droit de lire.
    try:
        projet = _projet_de(ouvert, jeton, project_id)
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        ouvert.fermer()
        raise _refus(cause) from cause

    requete = _requete_moteur(projet, corps)
    empreinte = _empreinte_des_entrees(requete)
    strict = bool(corps.strict_ndp)

    # LE REFUS DU MOTEUR EST `EurostructEngineError`, PAS `ConfirmationDomain
    # Error`. Mesure d'un lot precedent: n'attraper que la seconde laissait le
    # refus strict traverser sans etre enregistre — un 422 parfaitement
    # correct, et un historique vide.
    refus: EurostructEngineError | None = None
    reponse = None
    try:
        reponse = run_ec2_beam_flexure(
            requete, provider=lecture.provider if lecture else None)
    except EurostructEngineError as cause:
        refus = cause
    finally:
        if lecture is not None:
            lecture.fermer()

    # LE CORPS ENREGISTRE EST L'OBJET MEME QUI A SERVI, pas une
    # reconstruction: `charge` sort de `requete`, apres l'appel au moteur.
    charge = requete.model_dump(mode="json")
    try:
        if refus is not None:
            # LE MOTIF ENREGISTRE EST CELUI QUE LE CLIENT RECOIT, octet pour
            # octet: `error_of` est la seule traduction, et elle sert aux deux.
            ouvert.atelier.enregistrer_calcul(
                jeton, project_id=project_id, status="refused",
                inputs_hash=empreinte, strict_ndp=strict,
                engine_version=_version_du_moteur(),
                request=charge,
                refusal=error_of(refus).model_dump(mode="json",
                                                   exclude_none=True),
            )
            # ENREGISTRE D'ABORD, RENDU ENSUITE. Rendre le 422 avant d'ecrire
            # perdrait la trace a la premiere deconnexion du client — et c'est
            # precisement sur un refus qu'un client abandonne.
            raise refus

        corps_moteur = reponse.model_dump(mode="json")
        identifiant = ouvert.atelier.enregistrer_calcul(
            jeton, project_id=project_id, status="succeeded",
            inputs_hash=empreinte, strict_ndp=strict,
            engine_version=corps_moteur["engine_version"],
            request=charge,
            ndp_snapshot=corps_moteur.get("ndp"),
            # `results.payload` PORTE LE DOCUMENT, `verifications` L'INDEX.
            # Les deux existent et aucun n'est redondant: la table rend « quels
            # calculs ne passent pas » interrogeable en SQL, le payload porte
            # la reference CITABLE de chaque clause, que la table n'a pas.
            result={
                "element": corps_moteur.get("element"),
                "result": corps_moteur.get("result"),
                "verification": corps_moteur.get("verification"),
            },
            journal=corps_moteur.get("journal"),
            verifications=_verifications_a_plat(corps_moteur.get("verification")),
        )
        relu = ouvert.atelier.rouvrir_calcul(
            jeton, project_id=project_id, calculation_id=identifiant)
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        raise _refus(cause) from cause
    finally:
        ouvert.fermer()
    return _en_calcul_enregistre(relu, strict)


@routeur.get("/{project_id}/calculations", response_model=HistoriqueCalculs)
def historique(project_id: str,
               ouvert: Any = Depends(ouvrir_atelier)) -> HistoriqueCalculs:
    """L'historique d'un projet, du plus récent au plus ancien.

    LES REFUS Y FIGURENT. Un historique qui ne montrerait que les calculs
    aboutis ferait croire qu'aucun n'a jamais été refusé — et c'est justement
    la trace qu'un audit cherche en premier.
    """
    try:
        lignes = ouvert.atelier.historique(_jeton_de(ouvert),
                                           project_id=project_id)
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        raise _refus(cause) from cause
    finally:
        ouvert.fermer()
    return HistoriqueCalculs(project_id=project_id,
                             calculations=[CalculResume(**l) for l in lignes])


@routeur.get("/{project_id}/calculations/{calculation_id}",
             response_model=CalculEnregistre)
def rouvrir(project_id: str, calculation_id: str,
            ouvert: Any = Depends(ouvrir_atelier)) -> CalculEnregistre:
    """Rouvre un calcul : les MÊMES entrées, les MÊMES résultats.

    RIEN N'EST RECALCULÉ ICI. Relancer le moteur à la relecture rendrait le
    résultat d'aujourd'hui pour un calcul d'hier — avec le code d'aujourd'hui,
    et l'état d'aujourd'hui du référentiel national. Ce qui est rendu est ce
    qui a été enregistré.
    """
    try:
        relu = ouvert.atelier.rouvrir_calcul(
            _jeton_de(ouvert), project_id=project_id,
            calculation_id=calculation_id)
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        raise _refus(cause) from cause
    finally:
        ouvert.fermer()
    return _en_calcul_enregistre(relu, bool(relu.get("strict_ndp")))


# ===========================================================================
# CE QUI SERT AUX CINQ, ET QUI N'EST PAS UNE ROUTE
# ===========================================================================
def _projet_de(ouvert: Any, jeton: str, project_id: str) -> dict[str, Any]:
    """Le projet, sous l'identité authentifiée. Ou un refus qui ne dit rien.

    IL PASSE PAR LA LISTE, ET C'EST VOULU. ``project_workspace_list()`` filtre
    déjà sur les appartenances : chercher le projet dedans donne le même refus
    — « introuvable » — qu'il n'existe pas ou qu'il appartienne à une autre
    organisation. Une lecture directe par identifiant demanderait une seconde
    primitive, donc une seconde règle de visibilité, et c'est toujours la plus
    faible qui finit par décider.
    """
    for p in ouvert.atelier.projets(jeton):
        if p["project_id"] == project_id:
            return p
    raise ConfirmationDomainError(
        "projet introuvable ou hors de vos organisations."
    )


def _requete_moteur(projet: dict[str, Any],
                    corps: CalculDeProjetRequest) -> Ec2BeamFlexureRequest:
    """La requête moteur : la matière vient du corps, le référentiel du projet.

    LES QUATRE CHAMPS NORMATIFS SONT ÉCRITS ICI, ET NULLE PART AILLEURS.
    ``project_id``, ``country``, ``region`` et ``as_of`` sortent du projet
    chargé en base. Aucun n'existe dans ``CalculDeProjetRequest`` : il n'y a
    donc aucun endroit d'où un client pourrait les faire venir.

    ``region`` VOYAGE TELLE QUELLE, ``None`` COMPRIS. La primitive compare la
    région de la requête à celle du projet avec ``is distinct from`` : les
    normaliser différemment ici ferait refuser des calculs corrects.
    """
    return Ec2BeamFlexureRequest(
        project_id=projet["project_id"],
        country=projet["country"],
        region=projet.get("region"),
        as_of=projet["ndp_as_of"],
        element=corps.element,
        strict_ndp=corps.strict_ndp,
        section=corps.section,
        materials=corps.materials,
        situation=corps.situation,
        M_Ed=corps.M_Ed,
        A_s_provided=corps.A_s_provided,
    )


def _jeton_de(ouvert: Any) -> str:
    """Le jeton porteur de la requête courante.

    LE JETON EST LA PREUVE, ET IL VA JUSQU'À POSTGRESQL. L'atelier ne prend
    pas d'``actor_id`` : il reçoit la preuve, l'authentificateur en tire
    l'identité, et l'unité de travail la pose dans la transaction. Passer un
    identifiant déjà extrait ferait perdre en route la seule chose qui
    l'authentifie.
    """
    return ouvert.jeton


def _version_du_moteur() -> str:
    from eurostruct_engine.version import ENGINE_VERSION

    return ENGINE_VERSION


def _verifications_a_plat(rapport: Any) -> list[dict[str, Any]]:
    """Le rapport de vérification, aplati en lignes de table.

    ``verifications`` est une table de LIGNES depuis la première migration —
    une par contrôle, avec son taux d'utilisation, son sollicitant et son
    résistant. Y déposer le rapport entier en JSON ferait exactement le
    stockage parallèle que ce lot existe pour éviter : l'index
    ``(status, utilisation desc)`` ne servirait plus à rien, et « quels calculs
    ne passent pas » redeviendrait une question sans réponse SQL.
    """
    if not rapport:
        return []
    controles = rapport.get("checks") if isinstance(rapport, dict) else None
    if not controles:
        return []
    lignes: list[dict[str, Any]] = []
    for c in controles:
        # LA CLAUSE EST UN OBJET, PAS UNE CHAINE. `CheckDTO.clause` est un
        # `ClauseDTO` — norme, clause, equation, reference citable. La
        # premiere redaction lisait `c["standard"]` et `c["clause"]` a plat:
        # le premier n'existe pas, et le second deposait un JSON entier dans
        # une colonne `text` censee porter « §6.1 ».
        clause = c.get("clause") if isinstance(c.get("clause"), dict) else {}
        lignes.append({
            "name": c.get("name") or "verification",
            "standard": clause.get("standard") or "",
            "clause": clause.get("clause") or "",
            "equation": clause.get("equation"),
            # L'INTERDICTION N° 9 S'APPLIQUE ICI AUSSI: aucune valeur n'est
            # arrondie en passant. `utilisation` traverse telle quelle.
            "utilisation": float(c.get("utilisation") or 0.0),
            "status": _statut_de_controle(c.get("status")),
            "acting": str(c.get("acting", "")),
            "resisting": str(c.get("resisting", "")),
            "detail": c.get("detail"),
            "remedy": c.get("remedy"),
        })
    return lignes


def _statut_de_controle(valeur: Any) -> str:
    """Le statut du moteur, projeté sur l'énumération ``check_status``.

    UN STATUT INCONNU N'EST PAS « PASS ». Il devient ``not_applicable``, qui ne
    prétend rien. Le ranger en « pass » ferait passer pour vérifié un contrôle
    dont on ne sait pas lire le résultat.
    """
    brut = str(getattr(valeur, "value", valeur) or "").strip().lower()
    return brut if brut in {"pass", "fail", "not_applicable"} else "not_applicable"


def _en_calcul_enregistre(relu: dict[str, Any], strict: bool) -> CalculEnregistre:
    """La forme de fil d'un calcul relu, avec ses deux mentions.

    ``notice`` ET ``mention`` NE DISENT PAS LA MÊME CHOSE, et les confondre
    serait une régression — ici comme sur la route exploratoire.

    ``notice``
        « ce document doit être vérifié et signé par un ingénieur habilité ».
        Vraie de **tout** calcul, y compris parfaitement strict : aucun
        logiciel ne signe une note.

    ``mention``
        « PROJET — NON SIGNABLE ». Bien plus forte, et **conditionnelle** : des
        paramètres nationaux non confirmés ont pu servir, donc ce calcul ne
        peut être signé du tout, par quelque ingénieur que ce soit.

    ELLE ACCOMPAGNE LE CALCUL RELU, pas seulement le calcul neuf. Un calcul
    exploratoire rouvert six mois plus tard reste exploratoire, et l'écran qui
    le rouvre doit le dire aussi fort que celui qui l'a lancé.
    """
    charge = dict(relu)
    charge["notice"] = MENTION_OBLIGATOIRE
    if not strict:
        charge["mention"] = MENTION_NON_SIGNABLE
    return CalculEnregistre(**charge)
