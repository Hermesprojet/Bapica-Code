"""Les livrables d'un projet : produire, relire, faire relire, attester, émettre.

CE QUE CES ROUTES RENDENT ATTEIGNABLE
--------------------------------------
La machine à états ``draft → review → validated → final`` existe en base
depuis longtemps, avec ses transitions interdites, sa chaîne de révisions, son
journal, et l'exigence qu'un signataire soit membre **actif** et porteur du
rôle de validation. Rien n'y accédait. C'était un escalier dans un mur sans
porte : écrit, éprouvé, et inutilisable.

CE QUE LE NAVIGATEUR NE DÉCIDE JAMAIS
---------------------------------------
Ni l'organisation, ni le rôle de l'appelant, ni son nom, ni son numéro
d'inscription, ni la version du moteur, ni le build, ni l'identité
d'exécution, ni l'empreinte des octets, ni le chemin de stockage. Chacune de
ces valeurs est **dérivée côté serveur** — du jeton, de l'adhésion, ou des
colonnes gelées du calcul. Un corps qui en porterait une reçoit un 422 :
``Strict`` refuse les champs supplémentaires, pour que le client sache que sa
valeur n'a aucun effet plutôt que de le croire.

LES OCTETS SONT DÉPOSÉS AVANT D'ÊTRE ENREGISTRÉS, ET RELUS AVANT DE L'ÊTRE
---------------------------------------------------------------------------
L'ordre est le seul qui ne mente jamais : produire, déposer, **relire**,
vérifier l'empreinte, puis enregistrer. Une ligne écrite d'abord promettrait
un document introuvable si l'écriture échouait ensuite. L'ordre inverse ne
laisse au pire qu'un objet que personne ne référence.

CE QUE LE PRODUIT ENREGISTRE, ET COMMENT IL LE NOMME
------------------------------------------------------
Une **attestation métier authentifiée** : un membre actif, nommé, porteur du
rôle ``validating_engineer``, atteste avoir relu ce calcul-là, avec ses
entrées, son instantané normatif, son identité d'exécution, son build et
l'empreinte des octets. Ce n'est pas une signature électronique qualifiée, et
aucun écran ne l'appelle ainsi.
"""
from __future__ import annotations

from typing import Any

from eurostruct_engine.ndp.confirmation import ConfirmationDomainError
from eurostruct_engine.ndp.postgres_provider import AuthentificationRequise
from eurostruct_engine.schemas.atelier import (
    AttestationDemande,
    ListeLivrables,
    Livrable,
    LivrableCreation,
    LivrableDetail,
    RetourAuBrouillon,
)
from fastapi import APIRouter, Depends, HTTPException, Response

from ..dependances import ouvrir_atelier
from ..note import MEDIA_TYPE, rendre_note
from ..stockage import (
    ObjetIntrouvable,
    OctetsAlteres,
    StockageIndisponible,
    chemin_de_livrable,
    empreinte,
    stockage_configure,
)
from .calculs import MENTION_NON_SIGNABLE, MENTION_OBLIGATOIRE
from .projets import _jeton_de, _projet_de, _refus

routeur = APIRouter(prefix="/v1/projects", tags=["livrables"])

#: LA SEULE NATURE DE DOCUMENT QUE LE PRODUIT SAIT REELLEMENT PRODUIRE.
#:
#: `deliverable_kind` en enumere neuf, toutes attendues plus tard — PDF, DXF,
#: IFC, tableur. Offrir le choix a l'ecran ferait promettre huit livrables
#: qu'aucune route ne produit.
GENRE = "calculation_note_html"

#: LES EN-TETES QUI FERMENT LE DOCUMENT SERVI.
#:
#: Le meme jeu que la note de calcul, et pour la meme raison: une note est un
#: document qu'on s'envoie. `default-src 'none'` empeche tout chargement
#: exterieur si un jour une balise passait; `nosniff` empeche un navigateur de
#: requalifier le type.
_EN_TETES_DOCUMENT = {
    "Content-Security-Policy": (
        "default-src 'none'; style-src 'unsafe-inline'; img-src 'none'; "
        "script-src 'none'; base-uri 'none'; form-action 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
}


def _indisponible(cause: StockageIndisponible | ObjetIntrouvable
                  | OctetsAlteres) -> HTTPException:
    """Un magasin absent ou incohérent est un 503, jamais un 422.

    LA DISTINCTION COMPTE POUR L'APPELANT. Un 422 se lit « votre demande est
    refusée » et invite à la corriger ; il n'y a rien à corriger dans une
    demande parfaitement formée que le service ne peut pas tenir. Un client
    qui reçoit 503 réessaie ou alerte ; un client qui reçoit 422 abandonne.
    """
    return HTTPException(
        status_code=503,
        detail={"error": "stockage_indisponible",
                "what": type(cause).__name__, "detail": str(cause)},
    )


def _mentions(strict: bool) -> tuple[str, str | None]:
    """La mention obligatoire, et le filigrane quand il s'applique.

    ``notice`` accompagne **tout** document : aucun logiciel ne signe une note.
    ``mention`` — « PROJET — NON SIGNABLE » — s'y ajoute quand des paramètres
    nationaux non confirmés ont pu servir ; elle dit « pas signable du tout »,
    là où la première dit « pas encore signé ».
    """
    return MENTION_OBLIGATOIRE, None if strict else MENTION_NON_SIGNABLE


def _detail(brut: dict[str, Any]) -> LivrableDetail:
    charge = dict(brut)
    # LE FILIGRANE ENREGISTRE DIT DEJA SI DES PARAMETRES NON CONFIRMES ONT PU
    # SERVIR: il a ete calcule au moment ou les octets ont ete produits, et il
    # est fige avec eux. Le recalculer depuis l'etat d'aujourd'hui ferait dire
    # a un vieux document ce qui est vrai maintenant.
    charge["notice"] = MENTION_OBLIGATOIRE
    charge["mention"] = brut.get("watermark") or None
    return LivrableDetail(**charge)


def _octets_du_document(ouvert: Any, jeton: str, projet: dict[str, Any],
                        calculation_id: str) -> tuple[bytes, str | None]:
    """Produit les octets du livrable **depuis les données gelées**.

    LE MOTEUR N'EST PAS RELANCÉ. Le calcul est relu tel qu'il a été écrit —
    entrées, résultats, journal, vérifications, instantané normatif — et le
    document est composé à partir de cela seulement. Relancer le moteur
    donnerait les nombres d'aujourd'hui sous la date d'hier, et personne ne
    verrait la différence sur le document.
    """
    calcul = ouvert.atelier.rouvrir_calcul(
        jeton, project_id=projet["project_id"], calculation_id=calculation_id)

    if not (calcul.get("result") or {}).get("result"):
        raise ConfirmationDomainError(
            "ce calcul n'a produit aucun resultat: il a ete refuse par le "
            "moteur, et son motif figure dans l'historique. Un livrable se "
            "lirait comme une conclusion, et il n'y en a pas."
        )

    notice, mention = _mentions(bool(calcul.get("strict_ndp")))
    document = rendre_note(projet, calcul, notice=notice, mention=mention)
    return document.encode("utf-8"), mention


def _nom_de_fichier(projet: dict[str, Any], calcul_id: str) -> str:
    """Un nom lisible, composé de caractères sûrs uniquement.

    IL NE SERT PAS À CONSTRUIRE LE CHEMIN DE STOCKAGE, qui dérive de
    l'empreinte. Il n'apparaît que dans ``Content-Disposition``, et le
    filtrage ci-dessous suffit à ce qu'un nom de projet hostile n'y injecte
    rien.
    """
    reference = "".join(
        c for c in str(projet.get("reference") or projet.get("name") or "")
        if c.isalnum() or c in "-_")[:40]
    court = "".join(c for c in calcul_id if c.isalnum() or c == "-")[:36]
    return f"note-{reference or 'projet'}-{court or 'calcul'}.html"


def _creer(ouvert: Any, corps: LivrableCreation, project_id: str,
           supersedes_id: str | None) -> LivrableDetail:
    """Le geste complet : produire, déposer, relire, vérifier, enregistrer.

    LA RELECTURE AVANT ENREGISTREMENT EST LE CŒUR DE CETTE FONCTION. Elle
    transforme « on a demandé au magasin d'écrire » en « les octets sont là,
    et ce sont les bons ». Sans elle, un magasin qui accepte silencieusement
    et perd le contenu — disque plein, quota, montage en lecture seule mal
    diagnostiqué — laisserait une ligne parfaitement formée devant un
    document introuvable.
    """
    jeton = _jeton_de(ouvert)
    try:
        magasin = stockage_configure()
    except StockageIndisponible as cause:
        raise _indisponible(cause) from cause

    try:
        projet = _projet_de(ouvert, jeton, project_id)
        octets, filigrane = _octets_du_document(
            ouvert, jeton, projet, corps.calculation_id)
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        ouvert.fermer()
        raise _refus(cause) from cause

    sha = empreinte(octets)
    try:
        chemin = chemin_de_livrable(
            org_id=projet["organization_id"], project_id=project_id,
            sha256=sha, extension="html")
        magasin.deposer(chemin, octets)
        relus = magasin.lire(chemin)
        if empreinte(relus) != sha or len(relus) != len(octets):
            raise OctetsAlteres(
                f"les octets relus depuis « {chemin} » ne portent pas "
                "l'empreinte deposee. Aucune ligne n'est enregistree: elle "
                "promettrait un document qu'on ne sait pas relire."
            )
    except (StockageIndisponible, ObjetIntrouvable, OctetsAlteres) as cause:
        ouvert.fermer()
        raise _indisponible(cause) from cause

    try:
        livrable_id = ouvert.atelier.creer_livrable(
            jeton, project_id=project_id, calculation_id=corps.calculation_id,
            kind=GENRE, filename=_nom_de_fichier(projet, corps.calculation_id),
            media_type=MEDIA_TYPE, storage_backend=magasin.nom,
            storage_path=chemin, sha256=sha, size_bytes=len(octets),
            watermark=filigrane, supersedes_id=supersedes_id)
        return _detail(ouvert.atelier.relire_livrable(
            jeton, project_id=project_id, deliverable_id=livrable_id))
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        raise _refus(cause) from cause
    finally:
        ouvert.fermer()


@routeur.post("/{project_id}/deliverables", response_model=LivrableDetail,
              status_code=201)
def creer(project_id: str, corps: LivrableCreation,
          ouvert: Any = Depends(ouvrir_atelier)) -> LivrableDetail:
    """Crée un brouillon depuis un calcul enregistré.

    LE DOCUMENT EST COMPOSÉ ICI, PAS DANS LE NAVIGATEUR. Le client n'envoie
    qu'un identifiant de calcul ; tout le reste — contenu, nom, empreinte,
    taille, contexte normatif, version du moteur, build, identité d'exécution
    — est produit ou dérivé côté serveur.
    """
    return _creer(ouvert, corps, project_id, supersedes_id=None)


@routeur.post("/{project_id}/deliverables/{deliverable_id}/revision",
              response_model=LivrableDetail, status_code=201)
def reviser(project_id: str, deliverable_id: str, corps: LivrableCreation,
            ouvert: Any = Depends(ouvrir_atelier)) -> LivrableDetail:
    """Émet l'indice suivant, qui remplace celui-ci.

    C'EST LE SEUL MOYEN DE CORRIGER APRÈS ATTESTATION. Un livrable validé ou
    émis ne se modifie plus : la base le refuse, et c'est la seule façon
    qu'une attestation garde un sens. Corriger, c'est publier l'indice
    suivant, qui référence celui qu'il remplace.
    """
    return _creer(ouvert, corps, project_id, supersedes_id=deliverable_id)


@routeur.get("/{project_id}/deliverables", response_model=ListeLivrables)
def lister(project_id: str,
           ouvert: Any = Depends(ouvrir_atelier)) -> ListeLivrables:
    """Les livrables du projet, du plus récent au plus ancien."""
    try:
        lignes = ouvert.atelier.livrables(_jeton_de(ouvert),
                                          project_id=project_id)
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        raise _refus(cause) from cause
    finally:
        ouvert.fermer()
    return ListeLivrables(deliverables=[Livrable(**ligne) for ligne in lignes])


@routeur.get("/{project_id}/deliverables/{deliverable_id}",
             response_model=LivrableDetail)
def relire(project_id: str, deliverable_id: str,
           ouvert: Any = Depends(ouvrir_atelier)) -> LivrableDetail:
    """Un livrable, son contexte figé, son attestation et son historique."""
    try:
        brut = ouvert.atelier.relire_livrable(
            _jeton_de(ouvert), project_id=project_id,
            deliverable_id=deliverable_id)
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        raise _refus(cause) from cause
    finally:
        ouvert.fermer()
    return _detail(brut)


@routeur.get("/{project_id}/deliverables/{deliverable_id}/download")
def telecharger(project_id: str, deliverable_id: str,
                ouvert: Any = Depends(ouvrir_atelier)) -> Response:
    """Les octets **exacts** qui ont été enregistrés.

    RIEN N'EST RECOMPOSÉ. Le document n'est pas rendu à nouveau depuis le
    calcul : il est lu dans le magasin. Un rendu recomposé changerait au
    premier correctif de gabarit, et l'empreinte attestée ne désignerait plus
    rien.

    L'EMPREINTE EST REVÉRIFIÉE SUR CE QU'ON SERT. C'est le seul moment où l'on
    peut encore attraper une altération — corruption de disque, restauration
    partielle, écrasement — et un document altéré qui s'affiche est pire qu'un
    document absent, parce qu'on le lit.
    """
    jeton = _jeton_de(ouvert)
    try:
        localisation = ouvert.atelier.octets_du_livrable(
            jeton, project_id=project_id, deliverable_id=deliverable_id)
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        raise _refus(cause) from cause
    finally:
        ouvert.fermer()

    try:
        magasin = stockage_configure()
        if magasin.nom != localisation["storage_backend"]:
            raise StockageIndisponible(
                f"le livrable a ete depose dans le magasin "
                f"« {localisation['storage_backend']} » et le service est "
                f"configure avec « {magasin.nom} ». On refuse plutot que de "
                "servir des octets venus d'ailleurs."
            )
        octets = magasin.lire(localisation["storage_path"])
        if empreinte(octets) != localisation["sha256"]:
            raise OctetsAlteres(
                "les octets stockes ne portent plus l'empreinte enregistree. "
                "Le document a ete altere depuis son depot: on refuse de le "
                "servir."
            )
    except (StockageIndisponible, ObjetIntrouvable, OctetsAlteres) as cause:
        raise _indisponible(cause) from cause

    return Response(
        content=octets, media_type=localisation["media_type"],
        headers={
            "Content-Disposition":
                f'attachment; filename="{localisation["filename"]}"',
            **_EN_TETES_DOCUMENT,
        },
    )


def _transition(ouvert: Any, project_id: str, deliverable_id: str,
                to_state: str, reason: str | None) -> LivrableDetail:
    jeton = _jeton_de(ouvert)
    try:
        ouvert.atelier.transition_livrable(
            jeton, project_id=project_id, deliverable_id=deliverable_id,
            to_state=to_state, reason=reason)
        return _detail(ouvert.atelier.relire_livrable(
            jeton, project_id=project_id, deliverable_id=deliverable_id))
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        raise _refus(cause) from cause
    finally:
        ouvert.fermer()


@routeur.post("/{project_id}/deliverables/{deliverable_id}/review",
              response_model=LivrableDetail)
def soumettre(project_id: str, deliverable_id: str,
              ouvert: Any = Depends(ouvrir_atelier)) -> LivrableDetail:
    """Soumet le brouillon à la relecture. Il reste non opposable."""
    return _transition(ouvert, project_id, deliverable_id, "review", None)


@routeur.post("/{project_id}/deliverables/{deliverable_id}/draft",
              response_model=LivrableDetail)
def renvoyer(project_id: str, deliverable_id: str, corps: RetourAuBrouillon,
             ouvert: Any = Depends(ouvrir_atelier)) -> LivrableDetail:
    """Renvoie la pièce au brouillon, **avec le motif**.

    LE MOTIF EST EXIGÉ ICI ET EN BASE. Celui qui reprend le document doit
    savoir ce qui lui est reproché ; un retour muet est une décision qu'on ne
    peut pas relire six mois plus tard.
    """
    return _transition(ouvert, project_id, deliverable_id, "draft",
                       corps.reason)


@routeur.post("/{project_id}/deliverables/{deliverable_id}/validation",
              response_model=LivrableDetail)
def attester(project_id: str, deliverable_id: str, corps: AttestationDemande,
             ouvert: Any = Depends(ouvrir_atelier)) -> LivrableDetail:
    """Enregistre l'**attestation métier authentifiée**, et valide la pièce.

    CE N'EST PAS UNE SIGNATURE ÉLECTRONIQUE QUALIFIÉE, et le produit ne
    l'appelle jamais ainsi. Ce qui est enregistré : un membre actif de
    l'organisation du projet, nommé par son adhésion, porteur du rôle
    ``validating_engineer``, atteste avoir relu ce calcul-là.

    L'APPELANT N'ENVOIE QUE SON TEXTE. Nom, rôle et numéro d'inscription
    sortent de ``organization_members`` sous l'identité du jeton — PostgreSQL
    les dérive et les fige, et les accepter ici laisserait attester sous le
    nom de quelqu'un d'autre.

    UN CALCUL EXPLORATOIRE NE SE VALIDE PAS. Un calcul mené en mode non strict
    a pu employer des paramètres nationaux non confirmés ; attester le
    contraire ferait porter une signature humaine sur des nombres qu'aucune
    Annexe Nationale ne soutient. La base refuse, et le message le dit.
    """
    jeton = _jeton_de(ouvert)
    try:
        ouvert.atelier.attester_livrable(
            jeton, project_id=project_id, deliverable_id=deliverable_id,
            statement=corps.statement, reservations=corps.reservations)
        return _detail(ouvert.atelier.relire_livrable(
            jeton, project_id=project_id, deliverable_id=deliverable_id))
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        raise _refus(cause) from cause
    finally:
        ouvert.fermer()


@routeur.post("/{project_id}/deliverables/{deliverable_id}/final",
              response_model=LivrableDetail)
def emettre(project_id: str, deliverable_id: str,
            ouvert: Any = Depends(ouvrir_atelier)) -> LivrableDetail:
    """Émet le livrable. Impossible sans attestation nominative préalable.

    SÉPARÉE DE L'ATTESTATION, ET DÉLIBÉRÉMENT. Valider, c'est répondre du
    calcul ; émettre, c'est mettre le document en circulation. Les fondre
    ferait de toute relecture une publication.
    """
    jeton = _jeton_de(ouvert)
    try:
        ouvert.atelier.emettre_livrable(
            jeton, project_id=project_id, deliverable_id=deliverable_id)
        return _detail(ouvert.atelier.relire_livrable(
            jeton, project_id=project_id, deliverable_id=deliverable_id))
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        raise _refus(cause) from cause
    finally:
        ouvert.fermer()
