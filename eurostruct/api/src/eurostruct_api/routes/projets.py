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

from eurostruct_engine.build import BuildInconnu, identite_de_build
from eurostruct_engine.exceptions import EurostructEngineError
from eurostruct_engine.ndp.confirmation import ConfirmationDomainError
from eurostruct_engine.ndp.execution import identite_execution
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
from eurostruct_engine.schemas.ec2_verification import (
    Ec2BeamVerificationRequest,
    Ec2BeamVerificationResponse,
)
from eurostruct_engine.service import error_of, run_ec2_beam_flexure
from fastapi import APIRouter, Depends, HTTPException, Response

from ..dependances import ouvrir_atelier, provider_de_lecture
from ..note import MEDIA_TYPE, rendre_note
from ..note_verification import (
    est_note_de_verification,
    rendre_note_verification,
)
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

    # L'IDENTITE DE BUILD EST EXIGEE AVANT DE CALCULER, et le refus est un
    # 503. Ce n'est pas l'appelant qui est en faute: le service tourne sans
    # savoir quel code il execute, et la persistance ne peut pas mentir
    # la-dessus. Le calcul EXPLORATOIRE, lui, reste servi par
    # `/v1/calculations/...`: il ne pretend rien et ne survit a rien.
    try:
        build = identite_de_build()
    except BuildInconnu as cause:
        ouvert.fermer()
        raise HTTPException(
            status_code=503,
            detail={"error": "service_non_pret", "what": "identite de build",
                    "detail": str(cause)},
        ) from cause

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
                # UN REFUS N'A PAS D'INSTANTANE NDP: le moteur n'a rien
                # applique. L'identite le porte tel quel, si bien que deux
                # refus de meme requete sur le meme build se comparent.
                execution_identity=_identite(charge, None, build),
                engine_build=build,
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
            # L'IDENTITE EST CALCULEE SUR L'INSTANTANE REELLEMENT APPLIQUE,
            # pas sur l'etat d'aujourd'hui du referentiel: une confirmation
            # arrivee entre deux calculs change le resultat pour une requete
            # identique, et c'est exactement ce que l'identite doit distinguer.
            execution_identity=_identite(charge, corps_moteur.get("ndp"), build),
            engine_build=build,
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


@routeur.get("/{project_id}/calculations/{calculation_id}/note.html")
def note_html(project_id: str, calculation_id: str,
              ouvert: Any = Depends(ouvrir_atelier)) -> Response:
    """La note de calcul, rendue **depuis les données gelées**.

    RIEN N'EST RECALCULÉ, NI ICI NI DANS LE NAVIGATEUR. Chaque nombre affiché
    a été produit par le moteur au moment du calcul et écrit en base. Relancer
    le moteur donnerait les nombres d'aujourd'hui sous la date d'hier ;
    recalculer un taux de travail dans cette route créerait une seconde
    vérité, non éprouvée, et c'est celle-là que le lecteur croirait puisqu'elle
    est imprimée.

    LE DOCUMENT EST AUTONOME. Aucun script, aucune ressource externe, aucune
    police distante : il s'ouvre hors ligne dans dix ans, et sa relecture ne
    signale rien à personne.

    L'ISOLATION EST CELLE DE LA RÉOUVERTURE, et pour cause : c'est le même
    chemin. Le projet est chargé sous l'identité authentifiée, le calcul est
    relu par la primitive qui filtre déjà sur les appartenances. Une seconde
    règle de visibilité écrite ici serait une de trop.

    UN CALCUL SANS RÉSULTAT N'A PAS DE NOTE, et le refus le dit. Rendre un
    document vide ferait passer pour une note ce qui n'est qu'un refus
    enregistré — que l'historique, lui, montre déjà tel quel.
    """
    jeton = _jeton_de(ouvert)
    try:
        projet = _projet_de(ouvert, jeton, project_id)
        calcul = ouvert.atelier.rouvrir_calcul(
            jeton, project_id=project_id, calculation_id=calculation_id)
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        raise _refus(cause) from cause
    finally:
        ouvert.fermer()

    if not (calcul.get("result") or {}).get("result"):
        raise HTTPException(
            status_code=422,
            detail={"error": "atelier_refuse", "what": "note",
                    "detail": ("ce calcul n'a produit aucun resultat: il a ete "
                               "refuse par le moteur, et son motif figure dans "
                               "l'historique. Une note vide ferait passer un "
                               "refus pour un document.")},
        )

    strict = bool(calcul.get("strict_ndp"))
    # LE COMPOSEUR EST CHOISI SUR LA STRUCTURE DE LA LIGNE, PAS SUR UN DRAPEAU.
    # Une etude a cinq sections se reconnait a ses sections; un drapeau pose a
    # cote peut mentir sur ce que la ligne contient, la structure non. La note
    # de flexion garde ainsi son contrat et ses octets.
    composer = (rendre_note_verification if est_note_de_verification(calcul)
                else rendre_note)
    document = composer(
        projet, calcul,
        notice=MENTION_OBLIGATOIRE,
        mention=None if strict else MENTION_NON_SIGNABLE,
    )
    return Response(
        content=document, media_type=MEDIA_TYPE,
        headers={
            # LE NOM DU FICHIER PORTE LE REPERE ET L'IDENTIFIANT. Deux notes
            # du meme projet telechargees le meme jour ne doivent pas
            # s'ecraser dans le dossier de l'ingenieur.
            "Content-Disposition":
                'attachment; filename="note-'
                f'{_nom_de_fichier(calcul)}.html"',
            # LE DOCUMENT NE S'EXECUTE PAS, ET LE SERVEUR LE DIT AUSSI.
            # `rendre_note` n'emet aucun script; cette politique le garantit
            # meme si quelqu'un en introduisait un demain.
            "Content-Security-Policy":
                "default-src 'none'; style-src 'unsafe-inline'; "
                "img-src 'none'; script-src 'none'; base-uri 'none'; "
                "form-action 'none'",
            "X-Content-Type-Options": "nosniff",
        },
    )


# ===========================================================================
# CE QUI SERT AUX CINQ, ET QUI N'EST PAS UNE ROUTE
# ===========================================================================
def _nom_de_fichier(calcul: dict[str, Any]) -> str:
    """Un nom de fichier sûr, dérivé du repère et de l'identifiant.

    ON NE MET PAS LE NOM DU PROJET DEDANS. Il est saisi par un humain, il peut
    contenir n'importe quoi, et un nom de fichier est interprété par le système
    de fichiers du destinataire. Le repère est filtré, l'identifiant est un
    uuid : les deux sont sûrs par construction.
    """
    repere = "".join(
        c for c in str((calcul.get("request") or {}).get("element") or "")
        if c.isalnum() or c in "-_")[:40]
    identifiant = "".join(c for c in str(calcul.get("calculation_id") or "")
                          if c.isalnum() or c == "-")[:36]
    return f"{repere or 'calcul'}-{identifiant or 'sans-identifiant'}"
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


def _identite(charge: dict[str, Any], ndp: Any, build: str) -> str:
    """L'identité de cette exécution : requête, référentiel appliqué, build.

    ELLE PASSE PAR LA CANONICALISATION DU DÉPÔT — ``digest_of`` — comme les
    quatre empreintes du dossier de revue. Un second mécanisme dériverait au
    premier réglage changé, et ce serait toujours le plus faible qui servirait
    ici.
    """
    from eurostruct_engine.version import ENGINE_NAME, ENGINE_VERSION

    return identite_execution(
        request=charge, ndp_snapshot=ndp,
        engine_name=ENGINE_NAME, engine_version=ENGINE_VERSION,
        build_sha=build,
    ).digest


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


# =====================================================================
# LA VÉRIFICATION COMPLÈTE — les cinq sections, persistées
# =====================================================================
#
# ELLE NE REMPLACE PAS LA FLEXION SIMPLE, ET C'EST DÉLIBÉRÉ. La route
# `/calculations/ec2/beam-flexure` garde son contrat et ses résultats
# bit-à-bit : un client qui ne vérifie qu'une flexion n'a pas à fournir des
# étriers, un fluage et une classe d'exposition qu'il n'a pas.
#
# CE QUE CETTE ROUTE AJOUTE À LA PRÉCÉDENTE
# -------------------------------------------
# Un PRÉFLIGHT qui parle AVANT le moteur. En mode strict, il réunit les
# bloquants des cinq modules en une seule réponse et refuse sans rien écrire.
# Échouer cinq fois de suite n'apprend rien à personne ; écrire une ligne pour
# un calcul qu'on n'a pas tenté serait pire.


def _quantite(dto: Any) -> Any:
    """Un ``QuantityDTO`` en grandeur du moteur."""
    from eurostruct_engine.units import Q_

    return Q_(dto.value, dto.unit)


def _entree_moteur(corps: Any) -> Any:
    """Le corps HTTP en entrée gelée du moteur.

    AUCUNE GRANDEUR DÉRIVÉE N'EST CONSTRUITE ICI. `A_s`, `A_sw` et l'entraxe
    sont calculés par l'orchestrateur depuis les barres, les branches et le
    modèle géométrique partagé. Les fabriquer ici en ferait une seconde
    source.
    """
    from eurostruct_engine.ec2 import ExposureClass, StructuralSystem
    from eurostruct_engine.ec2.beam_verification import (
        BeamGeometry,
        BeamVerificationInput,
        LongitudinalBars,
        TransverseLinks,
    )

    g = corps.geometry
    return BeamVerificationInput(
        element=corps.element,
        geometry=BeamGeometry(
            b=_quantite(g.b), h=_quantite(g.h), d=_quantite(g.d),
            l_eff=_quantite(g.l_eff)),
        concrete_grade=corps.materials.concrete_grade,
        steel_grade=corps.materials.steel_grade,
        M_Ed=_quantite(corps.M_Ed), V_Ed=_quantite(corps.V_Ed),
        M_char=_quantite(corps.M_char), M_qp=_quantite(corps.M_qp),
        phi_creep=corps.phi_creep,
        exposure_class=ExposureClass(corps.exposure_class),
        system=StructuralSystem(corps.structural_system),
        supports_brittle_partitions=corps.supports_brittle_partitions,
        bars=LongitudinalBars(count=corps.bars.count,
                              diameter=_quantite(corps.bars.diameter)),
        links=TransverseLinks(legs=corps.links.legs,
                              diameter=_quantite(corps.links.diameter),
                              spacing=_quantite(corps.links.spacing)),
        cot_theta=corps.cot_theta,
        cover=_quantite(corps.cover),
        anchorage_available=_quantite(corps.anchorage_available),
        bond_condition=corps.bond_condition,
        b_eff_over_b_w=corps.b_eff_over_b_w,
    )


#: LA CORRESPONDANCE DES STATUTS, ET ELLE EST LE VERROU DE LA FINALISATION.
#:
#: `project_calculation_is_publishable` n'accepte que `succeeded`. Une étude
#: rouge ou incomplète enregistrée « succeeded » deviendrait donc publiable —
#: c'est exactement ce qu'il ne faut pas. Seul `passed` y a droit ; tout le
#: reste se conserve pour diagnostic sous un statut qui ferme la porte.
_STATUT_SQL = {"passed": "succeeded", "failed": "failed",
               "incomplete": "failed"}

#: LA TABLE `verifications` EST UN INDEX, PAS LA VERITE.
#:
#: Son enum `check_status` ne connait que trois valeurs — `pass`, `fail`,
#: `not_applicable` — la ou une section en a quatre. La correspondance est donc
#: NECESSAIREMENT plus grossiere que le resultat, et c'est acceptable a une
#: condition: aucun etat non satisfait ne doit devenir `pass`.
#:
#: `additional_analysis_required` va donc a `not_applicable` et non a `fail`:
#: la dispense de fleche non acquise ne dit rien sur la conformite de la
#: poutre, et l'ecrire `fail` en base ferait lire « poutre non conforme » a
#: toute requete SQL. `results.payload` porte, lui, le statut exact des quatre.
_STATUT_CHECK_SQL = {
    "passed": "pass",
    "failed": "fail",
    "additional_analysis_required": "not_applicable",
    "not_evaluated": "not_applicable",
}


def _ligne_de_section(section: Any) -> dict[str, Any]:
    """Une section, aplatie en ligne de la table `verifications`.

    La table exige `standard` et `clause` NON NULS, et elle a raison: « quels
    calculs ne passent pas, et sur quelle clause » doit rester une question
    SQL. `basis` porte les deux — « EN 1992-1-1 §6.1 » — et se coupe au
    premier « § ».

    INTERDICTION N° 9: `utilisation` traverse telle quelle, sans arrondi. Une
    section non evaluee n'en a pas; 0.0 est alors le seul remplissage possible
    d'une colonne non nulle, et le STATUT `not_applicable` a cote empeche de le
    lire comme « rien ne sollicite cette section ».
    """
    base = section.basis or ""
    norme, _, clause = base.partition("§")
    return {
        "name": section.title,
        "standard": norme.strip() or "EN 1992-1-1",
        "clause": ("§" + clause).strip() if clause else base,
        "equation": None,
        "utilisation": float(section.utilisation or 0.0),
        "status": _STATUT_CHECK_SQL[section.status],
        "acting": "",
        "resisting": "",
        "detail": section.reason,
        "remedy": section.remedy,
    }


def _reponse_de_verification(etude: Any, *, calculation_id: str,
                             build: str, identite: str) -> Any:
    from eurostruct_engine.schemas.common import QuantityDTO
    from eurostruct_engine.schemas.ec2_verification import (
        Ec2BeamVerificationResponse,
        SectionOutcomeDTO,
    )
    from eurostruct_engine.units import fmt

    largeur, unite = fmt(etude.bar_spacing).split(" ", 1)
    return Ec2BeamVerificationResponse(
        calculation_id=calculation_id,
        element=etude.element,
        status=etude.status,
        sections=tuple(
            SectionOutcomeDTO(
                key=s.key, title=s.title, basis=s.basis, status=s.status,
                utilisation=s.utilisation, remedy=s.remedy, reason=s.reason)
            for s in etude.sections),
        strict_ndp=etude.strict_ndp,
        country=etude.country,
        region=etude.region,
        ndp_as_of=etude.ndp_as_of.isoformat(),
        preflight_ready=etude.preflight_ready,
        is_exploratory=etude.is_exploratory,
        may_be_finalised=etude.may_be_finalised,
        requires_additional_analysis=etude.requires_additional_analysis,
        engineering_inputs_hash=etude.engineering_inputs_hash,
        ndp_snapshot_id=etude.ndp_snapshot_id,
        calculation_fingerprint=etude.calculation_fingerprint,
        engine_version=etude.engine_version,
        engine_build_sha=build,
        execution_identity=identite,
        max_utilisation=etude.max_utilisation,
        bar_spacing=QuantityDTO(value=float(largeur.replace(",", ".")),
                                unit=unite),
        notice=MENTION_OBLIGATOIRE,
        # LA MENTION SUIT L'ÉTUDE, PAS LE BOUTON. Une étude exploratoire la
        # porte dans la réponse elle-même : un autre client qui en tire une
        # note doit la reproduire.
        mention=None if etude.may_be_finalised else MENTION_NON_SIGNABLE,
        inputs=etude.inputs.to_dict(),
    )


@routeur.post("/{project_id}/beam-verifications",
              response_model=Ec2BeamVerificationResponse, status_code=201)
def verifier_poutre_completement(
    project_id: str,
    corps: Ec2BeamVerificationRequest,
    ouvert: Any = Depends(ouvrir_atelier),
    lecture: Any = Depends(provider_de_lecture),
) -> Any:
    """Les cinq vérifications, dans le référentiel du projet, puis enregistrées.

    L'ORDRE EST LA GARANTIE, ET IL EST LE SUJET DE CETTE ROUTE

    1. le **projet** d'abord, sous l'identité authentifiée : il porte le
       référentiel, et le charger avant de calculer évite de faire tourner le
       moteur pour un dossier qu'on n'a pas le droit de lire ;
    2. l'**identité de build**, sans laquelle la persistance ne pourrait pas
       dire quel code a produit la ligne ;
    3. le **préflight**, en mode strict — et il parle AVANT le moteur. Il rend
       les bloquants des CINQ modules en une seule réponse, et **rien n'est
       écrit** : il n'y a pas de calcul à enregistrer, pas même un refus,
       parce qu'aucun calcul n'a été tenté ;
    4. le **moteur**, dont un refus d'entrée incohérente est un 422 sans
       écriture non plus : une saisie fausse ne devient pas un dossier ;
    5. la **persistance**, en un seul appel de primitive.

    LE PROVIDER VIENT DU COMPOSITION ROOT, JAMAIS DU CORPS. ``provider_de_
    lecture`` le construit depuis l'état authentifié de l'application. Un corps
    qui pourrait le nommer laisserait choisir qui atteste.
    """
    from eurostruct_engine.ec2.beam_verification import (
        resolve_beam_context,
        verify_beam,
    )
    
    jeton = _jeton_de(ouvert)
    try:
        projet = _projet_de(ouvert, jeton, project_id)
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        ouvert.fermer()
        if lecture is not None:
            lecture.fermer()
        raise _refus(cause) from cause

    try:
        build = identite_de_build()
    except BuildInconnu as cause:
        ouvert.fermer()
        if lecture is not None:
            lecture.fermer()
        raise HTTPException(
            status_code=503,
            detail={"error": "service_non_pret", "what": "identite de build",
                    "detail": str(cause)},
        ) from cause

    from datetime import date as _date

    pays = projet["country"]
    region = projet.get("region")
    as_of = _date.fromisoformat(projet["ndp_as_of"])
    strict = bool(corps.strict_ndp)

    try:
        # --- 3. LE REFERENTIEL EST RESOLU UNE FOIS, ET UNE SEULE ----------
        #
        # `resolve_beam_context` applique les confirmations du provider et rend
        # LE jeu sur lequel tout ce qui suit travaille: le preflight, les cinq
        # modules, l'instantane normatif, l'identite d'execution et la
        # persistance.
        #
        # LA REDACTION PRECEDENTE PERDAIT CE TRAVAIL. Elle appelait
        # `preflight_beam(provider=)` puis rechargeait le referentiel BRUT par
        # `load_parameter_set`: le jeu resolu etait jete entre le preflight et
        # le moteur. Le defaut est silencieux et grave — un preflight strict
        # « pret » suivi d'un calcul strict qui refuse, sur le meme dossier, a
        # la meme seconde. Aucun ecran ne permet de diagnostiquer cela.
        contexte = resolve_beam_context(
            country=pays, region=region, as_of=as_of, strict=strict,
            provider=lecture.provider if lecture else None)

        if strict and not contexte.preflight.ready:
            # ZÉRO ÉCRITURE. Aucun calcul n'a été tenté: il n'y a rien à
            # enregistrer, et une ligne « refused » laisserait croire que
            # le moteur a répondu.
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "referentiel_incomplet",
                    "what": "preflight strict",
                    "detail": (
                        "le mode strict exige des paramètres nationaux "
                        "confirmés; ceux-ci ne le sont pas. Aucun calcul "
                        "n'a été lancé et rien n'a été enregistré."),
                    "blocking": [b.to_dict()
                                 for b in contexte.preflight.blocking],
                    "provider_identity": contexte.preflight.provider_identity,
                },
            )

        entree = _entree_moteur(corps)

        # --- 4. LE MOTEUR -------------------------------------------------
        #
        # LE CONTEXTE NORMATIF EST GELE AVEC LES ENTREES, et les quatre champs
        # viennent du PROJET — jamais du corps, qui n'a pas le droit de les
        # porter. La charge enregistree se lit donc seule: dix ans plus tard,
        # un auditeur y trouve le dossier, le pays, la region et la date
        # d'annexe qui ont reellement servi.
        #
        # `project_calculation_record` (0019) confronte ces quatre champs au
        # projet et refuse l'ecart. Mesure du 01/09: sans eux, la primitive a
        # refuse — « la requete porte le projet "(absent)" » — et elle avait
        # raison. La garantie n'est donc pas ici, elle est DOUBLEE ici.
        charge = {
            "project_id": project_id,
            "country": pays,
            "region": region,
            "as_of": as_of.isoformat(),
            **corps.model_dump(mode="json"),
        }

        # UNE SEULE IDENTITE D'EXECUTION, CALCULEE ICI ET NULLE PART AILLEURS.
        # Elle se calcule APRES la resolution du referentiel et AVANT
        # l'execution, si bien qu'une seule valeur circule: le moteur la
        # recoit, la base l'enregistre, la reponse la rend, la note la cite.
        # La rediger deux fois — une avec `ndp=None`, une avec l'instantane —
        # donnait deux valeurs pour une meme execution, et une note qui cite la
        # premiere ne se rattache a aucune ligne.
        identite = contexte.execution_identity(charge, engine_build=build)

        try:
            etude = verify_beam(entree, params=contexte.parameters,
                                execution_identity=identite)
        except EurostructEngineError as cause:
            # UNE SAISIE FAUSSE NE DEVIENT PAS UN DOSSIER. Contrairement à la
            # flexion — qui enregistre son refus parce que le moteur a
            # répondu — un refus de COHÉRENCE porte sur ce que l'appelant a
            # envoyé, pas sur le référentiel. Il n'y a rien à conserver.
            raise HTTPException(
                status_code=422,
                detail={"error": "entree_incoherente",
                        "what": type(cause).__name__,
                        "detail": str(cause)},
            ) from cause

        # --- 5. LA PERSISTANCE, EN UN SEUL APPEL --------------------------
        calcul_id = ouvert.atelier.enregistrer_calcul(
            jeton, project_id=project_id,
            status=_STATUT_SQL[etude.status],
            # LA COLONNE `inputs_hash` EST DOCUMENTEE COMME L'EMPREINTE DE LA
            # TOTALITE DES ENTREES: on y depose donc `calculation_fingerprint`,
            # qui couvre la technique ET le contexte normatif. Y mettre la
            # seule empreinte technique ferait partager la colonne a deux
            # etudes menees sous des annexes differentes — et la colonne
            # mentirait sur ce qu'elle porte.
            inputs_hash=etude.calculation_fingerprint,
            strict_ndp=etude.strict_ndp,
            engine_version=etude.engine_version,
            request=charge,
            ndp_snapshot=etude.ndp_summary,
            execution_identity=identite,
            engine_build=build,
            # LA FORME DU PAYLOAD EST CELLE DU DEPOT, PAS UNE NOUVELLE.
            # `results.payload` porte `{"result": ..., "verification": ...}`
            # depuis la route de flexion, et la composition d'un livrable lit
            # `payload["result"]`. Mesure du 01/09: en deposant l'etude a plat,
            # la creation d'un brouillon repondait « ce calcul n'a produit
            # aucun resultat » — elle cherchait une cle absente.
            result={"result": etude.to_dict(),
                    "verification": {
                        "passed": etude.status == "passed",
                        "max_utilisation": etude.max_utilisation,
                        "checks": [_ligne_de_section(s)
                                   for s in etude.sections]}},
            # LES CINQ JOURNAUX, DANS L'ORDRE DES CHAPITRES. `0019` refuse un
            # calcul « succeeded » sans journal, et elle a raison: c'est lui
            # qui rend chaque nombre cliquable. Une section non evaluee n'en a
            # pas — elle n'a pas tourne — et son absence se lit telle quelle.
            journal={"sections": [
                {"key": s.key, "title": s.title,
                 "journal": (s.design.journal.to_dict()
                             if s.design is not None else None)}
                for s in etude.sections]},
            verifications=[_ligne_de_section(s) for s in etude.sections],
        )
    finally:
        if lecture is not None:
            lecture.fermer()
        ouvert.fermer()

    return _reponse_de_verification(etude, calculation_id=calcul_id,
                                    build=build, identite=identite)


@routeur.get("/{project_id}/beam-verifications/{calculation_id}",
             response_model=Ec2BeamVerificationResponse)
def rouvrir_verification(
    project_id: str, calculation_id: str,
    ouvert: Any = Depends(ouvrir_atelier),
) -> Any:
    """Rouvre une étude complète : les MÊMES entrées, les MÊMES verdicts.

    RIEN N'EST RECALCULÉ. Relancer les cinq modules à la relecture rendrait le
    résultat d'aujourd'hui pour une étude d'hier — avec le code d'aujourd'hui
    et l'état d'aujourd'hui du référentiel. Ce qui est rendu est ce que
    `results.payload` porte, tel que l'orchestrateur l'a écrit.

    UNE ÉTUDE EXPLORATOIRE ROUVERTE RESTE EXPLORATOIRE, et la réponse le dit
    aussi fort qu'au premier jour: `mention` est reconstruite depuis
    `may_be_finalised`, pas depuis un drapeau que la relecture pourrait
    perdre.
    """
    try:
        relu = ouvert.atelier.rouvrir_calcul(
            _jeton_de(ouvert), project_id=project_id,
            calculation_id=calculation_id)
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        raise _refus(cause) from cause
    finally:
        ouvert.fermer()

    charge = (relu.get("result") or {}).get("result") or {}
    if not charge.get("sections"):
        raise HTTPException(
            status_code=404,
            detail={"error": "pas_une_verification_complete",
                    "what": "calcul",
                    "detail": ("ce calcul n'est pas une vérification complète "
                               "à cinq sections.")},
        )
    return _reponse_relue(relu, charge)


def _reponse_relue(relu: dict[str, Any], charge: dict[str, Any]) -> Any:
    """La réponse reconstruite depuis la ligne enregistrée, sans recalcul."""
    from eurostruct_engine.schemas.common import QuantityDTO
    from eurostruct_engine.schemas.ec2_verification import (
        Ec2BeamVerificationResponse,
        SectionOutcomeDTO,
    )

    largeur, unite = str(charge.get("bar_spacing", "0 mm")).split(" ", 1)
    return Ec2BeamVerificationResponse(
        calculation_id=str(relu["calculation_id"]),
        element=charge.get("element", ""),
        status=charge.get("status", ""),
        sections=tuple(SectionOutcomeDTO(**s) for s in charge["sections"]),
        strict_ndp=bool(relu.get("strict_ndp")),
        country=charge.get("country", ""),
        region=charge.get("region"),
        ndp_as_of=charge.get("ndp_as_of") or "",
        preflight_ready=bool(charge.get("preflight_ready")),
        is_exploratory=bool(charge.get("is_exploratory")),
        may_be_finalised=bool(charge.get("may_be_finalised")),
        requires_additional_analysis=bool(
            charge.get("requires_additional_analysis")),
        engineering_inputs_hash=charge.get("engineering_inputs_hash", ""),
        ndp_snapshot_id=charge.get("ndp_snapshot_id", ""),
        calculation_fingerprint=charge.get("calculation_fingerprint", ""),
        engine_version=charge.get("engine_version", ""),
        engine_build_sha=str(relu.get("engine_build_sha") or ""),
        execution_identity=str(relu.get("execution_identity") or ""),
        max_utilisation=float(charge.get("max_utilisation") or 0.0),
        bar_spacing=QuantityDTO(value=float(largeur.replace(",", ".")),
                                unit=unite),
        notice=MENTION_OBLIGATOIRE,
        mention=(None if charge.get("may_be_finalised")
                 else MENTION_NON_SIGNABLE),
        inputs=charge.get("inputs") or {},
    )
