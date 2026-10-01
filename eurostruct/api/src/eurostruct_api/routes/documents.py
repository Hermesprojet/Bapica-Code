"""Les pièces d'un projet : déposer, analyser, revoir, décider, reporter.

L'ORGANISATION VIENT DU PROJET, L'IDENTITÉ DU JETON, LE NOM DE L'ADHÉSION.
Aucune route n'accepte ``org_id``, ni nom de décideur, ni date, ni empreinte,
ni format : le format se constate sur les octets, l'empreinte se calcule, le
nom et la date sont posés par la base.

LE CORPS D'UN DÉPÔT EST LE FICHIER LUI-MÊME. Pas de formulaire multipart :
le navigateur envoie les octets tels quels (``fetch(url, {body: fichier})``),
la nature et le nom voyagent en paramètres. Le ``Content-Type`` annoncé n'est
pas lu — c'est celui que l'expéditeur choisit.

L'IDENTITÉ EST VÉRIFIÉE AVANT QUE LE CORPS NE SOIT LU. Un jeton faux n'obtient
pas qu'on reçoive 32 Mio pour lui répondre 401 ensuite ; et la connexion à la
base n'est ouverte qu'une fois le corps reçu, pour ne pas la retenir pendant
un téléversement lent.
"""

from __future__ import annotations

import unicodedata
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any

from eurostruct_engine.ndp.confirmation import ConfirmationDomainError
from eurostruct_engine.ndp.postgres_provider import AuthentificationRequise
from eurostruct_engine.schemas.documents import (
    DecisionExtraction,
    DocumentTeleverse,
    Extraction,
    ListeDocuments,
    ListeExtractions,
    Preremplissage,
    StructureDuDocument,
)
from eurostruct_extraction import FormatNonPrisEnCharge, detecter_format
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse

from .. import documents as service
from ..dependances import acteur_authentifie, ouvrir_atelier
from ..stockage import (
    TAILLE_MAX,
    ObjetIntrouvable,
    OctetsAlteres,
    StockageIndisponible,
    disposition_de_fichier,
    empreinte,
    stockage_configure,
)
from .livrables import (
    _EN_TETES_DOCUMENT,
    _indisponible,
    _magasin_du_livrable,
    _servir_en_verifiant,
)
from .projets import _jeton_de, _projet_de, _refus

routeur = APIRouter(prefix="/v1/projects", tags=["documents"])


async def corps_borne(requete: Request) -> bytes:
    """Le corps de la requête, refusé dès qu'il dépasse la borne du magasin.

    LA BORNE EST TENUE PENDANT LA LECTURE, pas après. Lire d'abord puis
    mesurer laisserait un client remplir la mémoire du service avec un corps
    annoncé petit et envoyé énorme.
    """
    annonce = requete.headers.get("content-length")
    if annonce and annonce.isdigit() and int(annonce) > TAILLE_MAX:
        raise _trop_gros()
    morceaux: list[bytes] = []
    total = 0
    async for morceau in requete.stream():
        total += len(morceau)
        if total > TAILLE_MAX:
            raise _trop_gros()
        morceaux.append(morceau)
    return b"".join(morceaux)


def _trop_gros() -> HTTPException:
    return HTTPException(
        status_code=413,
        detail={"error": "piece_trop_grosse", "what": "corps",
                "detail": (f"une piece deposee ne depasse pas {TAILLE_MAX // (1024 * 1024)} "
                           "Mio. Rien n'a ete depose.")})


def _nom_de_fichier(brut: str) -> str:
    """Le nom affiché : le dernier segment, sans caractère de contrôle.

    Il ne sert QU'À L'AFFICHAGE et au téléchargement — jamais au chemin de
    stockage, qui dérive de l'empreinte.
    """
    nom = PureWindowsPath(PurePosixPath(brut).name).name
    nom = "".join(c for c in nom if unicodedata.category(c)[0] != "C").strip()
    if not nom:
        raise HTTPException(
            status_code=422,
            detail={"error": "nom_de_fichier_invalide", "what": "filename",
                    "detail": "le nom de fichier est vide une fois nettoye."})
    return nom[:200]


def _exiger_saisie(projet: dict[str, Any]) -> None:
    """Le précontrôle AVANT tout octet déposé (même raison que les livrables)."""
    if not projet.get("member_active", True):
        raise ConfirmationDomainError(
            "votre acces a cette organisation a ete revoque: il n'ouvre plus "
            "aucun geste.")
    role = str(projet.get("member_role") or "")
    if role not in service.SAISIE:
        raise ConfirmationDomainError(
            f"le role « {role} » ne depose pas de piece et ne decide pas des "
            "valeurs extraites. Ces gestes reviennent aux roles qui lancent un "
            "calcul: owner, admin, engineer, validating_engineer.")


def _document_relu(ouvert: Any, jeton: str, project_id: str, document_id: str):
    for ligne in ouvert.atelier.documents(jeton, project_id=project_id):
        if ligne["document_id"] == document_id:
            return service.en_document(ligne)
    raise ConfirmationDomainError(
        f"document {document_id}: introuvable dans ce projet a la relecture.")


def _analyser_et_enregistrer(ouvert: Any, jeton: str, document_id: str,
                             octets: bytes) -> int:
    """Analyse, puis UN enregistrement; un refus de la base devient un échec
    enregistré plutôt qu'un document « en attente » pour toujours."""
    analyse, resultat = service.analyser(octets)
    try:
        return service.create_extraction_records(ouvert, jeton, document_id,
                                                 analyse, resultat)
    except ConfirmationDomainError as cause:
        if isinstance(cause, AuthentificationRequise):
            raise
        service.enregistrer_echec(ouvert, jeton, document_id, str(cause))
        return 0


@routeur.post("/{project_id}/documents", response_model=DocumentTeleverse,
              status_code=201)
def deposer(
    project_id: str,
    response: Response,
    kind: str = Query(..., description="architect_drawing, formwork_drawing, cctp, other"),
    filename: str = Query(..., min_length=1, max_length=255),
    _acteur: str = Depends(acteur_authentifie),
    octets: bytes = Depends(corps_borne),
    ouvert: Any = Depends(ouvrir_atelier),
) -> DocumentTeleverse:
    """``uploadDocument()`` — puis l'analyse, dans la même requête.

    1. nature reçue, format constaté sur les octets (415 sinon) ;
    2. projet visible et capacité de saisie, AVANT tout dépôt ;
    3. dépôt, relecture, empreinte, inscription ;
    4. lecture et propositions, toutes ``proposed``.

    Les mêmes octets déjà déposés dans ce projet rendent le document existant
    (200), sans seconde ligne ni seconde analyse.
    """
    jeton = _jeton_de(ouvert)
    try:
        if kind not in service.NATURES:
            raise HTTPException(
                status_code=422,
                detail={"error": "nature_non_recue", "what": "kind",
                        "detail": (f"la nature « {kind} » n'est pas recue (plan "
                                   "d'architecte, plan de coffrage, cahier des "
                                   "charges, autre).")})
        nom = _nom_de_fichier(filename)
        try:
            detecte = detecter_format(octets)
        except FormatNonPrisEnCharge as cause:
            raise HTTPException(
                status_code=415,
                detail={"error": "format_non_pris_en_charge", "what": "fichier",
                        "detail": f"{cause} Rien n'a ete depose."}) from cause
        try:
            projet = _projet_de(ouvert, jeton, project_id)
            _exiger_saisie(projet)
        except (AuthentificationRequise, ConfirmationDomainError) as cause:
            raise _refus(cause) from cause
        try:
            magasin = stockage_configure()
            document_id, deja = service.upload_document(
                ouvert, jeton, projet, octets=octets, kind=kind, filename=nom,
                format_=detecte.format, media_type=detecte.type_media,
                extension=detecte.extension, magasin=magasin)
        except (StockageIndisponible, ObjetIntrouvable, OctetsAlteres) as cause:
            raise _indisponible(cause) from cause
        except (AuthentificationRequise, ConfirmationDomainError) as cause:
            raise _refus(cause) from cause

        try:
            crees = 0
            if not deja:
                crees = _analyser_et_enregistrer(ouvert, jeton, document_id, octets)
            else:
                response.status_code = 200
            document = _document_relu(ouvert, jeton, project_id, document_id)
        except (AuthentificationRequise, ConfirmationDomainError) as cause:
            raise _refus(cause) from cause
        return DocumentTeleverse(document=document, already_present=deja,
                                 extractions_created=crees,
                                 notice=service.AVIS_PROPOSITIONS)
    finally:
        ouvert.fermer()


@routeur.get("/{project_id}/documents", response_model=ListeDocuments)
def lister(project_id: str, ouvert: Any = Depends(ouvrir_atelier)) -> ListeDocuments:
    try:
        lignes = ouvert.atelier.documents(_jeton_de(ouvert), project_id=project_id)
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        raise _refus(cause) from cause
    finally:
        ouvert.fermer()
    return ListeDocuments(project_id=project_id,
                          documents=[service.en_document(ligne) for ligne in lignes])


@routeur.get("/{project_id}/documents/{document_id}/structure",
             response_model=StructureDuDocument)
def structure(project_id: str, document_id: str,
              ouvert: Any = Depends(ouvrir_atelier)) -> StructureDuDocument:
    """Le modèle structurel reconstruit depuis la géométrie d'un DXF.

    Poteaux, voiles, poutres, travées et leurs appuis, dalles, grille, cotes
    rattachées, et ce qui n'a pas pu être résolu — tel qu'enregistré avec
    l'analyse. Un document sans modèle (PDF, DXF sans géométrie lue) répond
    404 : il n'y a rien à montrer, et rien n'est reconstruit à la demande.
    """
    try:
        lignes = ouvert.atelier.documents(_jeton_de(ouvert), project_id=project_id)
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        raise _refus(cause) from cause
    finally:
        ouvert.fermer()
    ligne = next((x for x in lignes if x["document_id"] == document_id), None)
    if ligne is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "document_introuvable", "what": "document_id",
                    "detail": "document introuvable dans ce projet."})
    lu = service.en_structure(project_id, ligne)
    if lu is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "structure_absente", "what": "document_id",
                    "detail": ("ce document n'a pas de modele structurel: seule la "
                               "geometrie d'un DXF en donne un.")})
    return lu


@routeur.get("/{project_id}/documents/{document_id}/download")
def telecharger(project_id: str, document_id: str,
                ouvert: Any = Depends(ouvrir_atelier)) -> Response:
    """Les octets EXACTS déposés, empreinte revérifiée au fil de la lecture."""
    try:
        localisation = ouvert.atelier.octets_du_document(
            _jeton_de(ouvert), project_id=project_id, document_id=document_id)
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        raise _refus(cause) from cause
    finally:
        ouvert.fermer()
    try:
        magasin = _magasin_du_livrable(localisation)
        flux = magasin.lire_en_flux(localisation["storage_path"])
        premier = next(flux, b"")
    except (StockageIndisponible, ObjetIntrouvable, OctetsAlteres) as cause:
        raise _indisponible(cause) from cause
    return StreamingResponse(
        _servir_en_verifiant(premier, flux, localisation["sha256"]),
        media_type=localisation["mime_type"],
        headers={"Content-Disposition": disposition_de_fichier(localisation["filename"]),
                 **_EN_TETES_DOCUMENT})


@routeur.post("/{project_id}/documents/{document_id}/analysis",
              response_model=DocumentTeleverse)
def analyser_a_nouveau(project_id: str, document_id: str,
                       ouvert: Any = Depends(ouvrir_atelier)) -> DocumentTeleverse:
    """Une nouvelle analyse, tant qu'AUCUNE proposition n'existe.

    Après un échec, un DWG non lu ou une lecture sans résultat. La base
    refuse si des propositions existent: elles et leurs décisions restent la
    trace de ce qui a été lu.
    """
    jeton = _jeton_de(ouvert)
    try:
        try:
            localisation = ouvert.atelier.octets_du_document(
                jeton, project_id=project_id, document_id=document_id)
        except (AuthentificationRequise, ConfirmationDomainError) as cause:
            raise _refus(cause) from cause
        try:
            magasin = _magasin_du_livrable(localisation)
            octets = magasin.lire(localisation["storage_path"])
        except (StockageIndisponible, ObjetIntrouvable) as cause:
            raise _indisponible(cause) from cause
        if empreinte(octets) != localisation["sha256"]:
            raise _indisponible(OctetsAlteres(
                "les octets stockes ne portent plus l'empreinte enregistree: "
                "aucune analyse n'est faite sur un document altere."))
        try:
            analyse, resultat = service.analyser(octets)
            crees = service.create_extraction_records(
                ouvert, jeton, document_id, analyse, resultat)
            document = _document_relu(ouvert, jeton, project_id, document_id)
        except (AuthentificationRequise, ConfirmationDomainError) as cause:
            raise _refus(cause) from cause
        return DocumentTeleverse(document=document, already_present=True,
                                 extractions_created=crees,
                                 notice=service.AVIS_PROPOSITIONS)
    finally:
        ouvert.fermer()


@routeur.get("/{project_id}/extractions", response_model=ListeExtractions)
def lister_extractions(
    project_id: str,
    document_id: str | None = Query(default=None),
    status: str | None = Query(default=None,
                               description="proposed, confirmed, corrected, rejected"),
    ouvert: Any = Depends(ouvrir_atelier),
) -> ListeExtractions:
    try:
        lignes = ouvert.atelier.extractions(
            _jeton_de(ouvert), project_id=project_id, document_id=document_id)
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        raise _refus(cause) from cause
    finally:
        ouvert.fermer()
    if status is not None:
        lignes = [ligne for ligne in lignes if ligne["status"] == status]
    return ListeExtractions(project_id=project_id,
                            extractions=[service.en_extraction(x) for x in lignes],
                            notice=service.AVIS_PROPOSITIONS)


@routeur.post("/{project_id}/extractions/{extraction_id}/decision",
              response_model=Extraction)
def decider(project_id: str, extraction_id: str, corps: DecisionExtraction,
            ouvert: Any = Depends(ouvrir_atelier)) -> Extraction:
    """``confirmExtraction()``. Le nom et la date sont posés par la base."""
    jeton = _jeton_de(ouvert)
    try:
        service.confirm_extraction(
            ouvert, jeton, project_id=project_id, extraction_id=extraction_id,
            decision=corps.decision, final_value=corps.final_value, note=corps.note)
        lignes = ouvert.atelier.extractions(jeton, project_id=project_id,
                                            ids=[extraction_id])
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        raise _refus(cause) from cause
    finally:
        ouvert.fermer()
    if not lignes:
        raise _refus(ConfirmationDomainError(
            "la decision est enregistree mais la proposition est introuvable a "
            "la relecture."))
    return service.en_extraction(lignes[0])


@routeur.get("/{project_id}/extractions/prefill", response_model=Preremplissage)
def preremplir(project_id: str,
               element: str | None = Query(default=None, max_length=100),
               ouvert: Any = Depends(ouvrir_atelier)) -> Preremplissage:
    """Les valeurs DÉCIDÉES pour l'étude, dans l'unité de chaque champ."""
    try:
        lignes = ouvert.atelier.extractions(_jeton_de(ouvert), project_id=project_id)
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        raise _refus(cause) from cause
    finally:
        ouvert.fermer()
    return service.preremplissage(project_id, lignes, element)
