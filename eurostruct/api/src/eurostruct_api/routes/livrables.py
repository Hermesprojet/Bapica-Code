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

import hashlib
import io
import json
import zipfile
from typing import Any

from eurostruct_engine.drawing.beam_section import rendre_dxf
from eurostruct_engine.drawing.svg import MEDIA_TYPE_SVG, rendre_svg
from eurostruct_engine.exceptions import ReinforcementNotVerified
from eurostruct_engine.ndp.confirmation import ConfirmationDomainError
from eurostruct_engine.ndp.postgres_provider import AuthentificationRequise
from eurostruct_engine.schemas.atelier import (
    AttestationDemande,
    EmissionDemande,
    ListeLivrables,
    Livrable,
    LivrableCreation,
    LivrableDetail,
    RetourAuBrouillon,
)
from eurostruct_engine.schemas.ec2_beam import (
    Ec2BeamFlexureRequest,
    Ec2BeamSectionRequest,
)
from eurostruct_engine.service import verify_and_model_beam_section
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse

from ..attestation import rendre_attestation_pdf
from ..dependances import ouvrir_atelier, provider_de_lecture
from ..note import (
    MEDIA_TYPE,
    MEDIA_TYPE_DXF,
    MEDIA_TYPE_PDF,
    rendre_note,
    rendre_note_pdf,
)
from ..pdf import CaractereNonRepresentable
from ..stockage import (
    ObjetIntrouvable,
    OctetsAlteres,
    StockageIndisponible,
    chemin_de_livrable,
    disposition_de_fichier,
    empreinte,
    stockage_configure,
)
from .calculs import MENTION_NON_SIGNABLE, MENTION_OBLIGATOIRE
from .projets import _jeton_de, _projet_de, _refus

routeur = APIRouter(prefix="/v1/projects", tags=["livrables"])

#: LES NATURES DE DOCUMENT QUE LE PRODUIT SAIT REELLEMENT PRODUIRE.
#:
#: `deliverable_kind` en enumere neuf, les autres attendues plus tard — DXF,
#: IFC, tableur. Offrir le choix a l'ecran ferait promettre des livrables
#: qu'aucune route ne produit.
GENRE = "calculation_note_html"

#: FORME DEMANDEE -> (genre enregistre, type de media, extension du chemin).
#:
#: LES TROIS SE DECIDENT ENSEMBLE, ET C'EST DELIBERE. Les laisser diverger
#: donnerait une ligne annoncant un PDF devant un objet HTML: le
#: telechargement servirait l'un en promettant l'autre, et l'empreinte
#: enregistree ne dirait pas laquelle des deux est vraie.
_FORMES: dict[str, tuple[str, str, str]] = {
    "html": (GENRE, MEDIA_TYPE, "html"),
    "pdf": ("calculation_note_pdf", MEDIA_TYPE_PDF, "pdf"),
    "dxf": ("rebar_drawing_dxf", MEDIA_TYPE_DXF, "dxf"),
}

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


def _detail(brut: dict[str, Any],
            document_emis: str | None = None) -> LivrableDetail:
    """La projection d'une ligne relue vers le contrat rendu au client.

    `LivrableDetail` EST GELE, et c'est voulu: une reponse qu'on peut retoucher
    apres coup finit par dire autre chose que ce qui a ete lu. Le document
    emis est donc passe ICI, a la construction, et non ecrit sur l'objet.
    """
    charge = dict(brut)
    charge["issued_deliverable_id"] = document_emis
    # LE FILIGRANE ENREGISTRE DIT DEJA SI DES PARAMETRES NON CONFIRMES ONT PU
    # SERVIR: il a ete calcule au moment ou les octets ont ete produits, et il
    # est fige avec eux. Le recalculer depuis l'etat d'aujourd'hui ferait dire
    # a un vieux document ce qui est vrai maintenant.
    charge["notice"] = MENTION_OBLIGATOIRE
    charge["mention"] = brut.get("watermark") or None
    return LivrableDetail(**charge)


#: LA MATRICE, TELLE QUE L'ECRAN ET LA ROUTE LA LISENT.
#:
#: ELLE NE PROTEGE RIEN, ET C'EST DELIBERE. La frontiere est dans
#: `project_exiger_capacite()` (0023), qui refuse quel que soit l'appelant. Ce
#: qui est ici sert a deux choses qu'un refus SQL ne peut pas rendre: NE PAS
#: ECRIRE DANS LE MAGASIN pour une demande qu'on sait refusee, et dire a
#: l'ecran quels boutons ont un sens.
REDACTEURS = frozenset({"owner", "admin", "engineer"})
VALIDATEURS = frozenset({"validating_engineer"})
#: TOUS LES ROLES DE PROJET. Regarder n'engage rien; ce qui protege la lecture,
#: c'est l'appartenance elle-meme — `_projet_de` ne rend un projet qu'a un
#: membre — et l'exigence qu'elle soit ACTIVE, controlee ci-dessous.
LECTEURS = REDACTEURS | VALIDATEURS

#: CAPACITE -> ROLES QUI LA PORTENT.
#:
#: UNE TABLE PLUTOT QU'UN TERNAIRE, ET C'EST UN CORRECTIF. La version
#: precedente lisait « REDACTEURS si capacite == "redaction", sinon
#: VALIDATEURS »: n'importe quel nom mal orthographie tombait donc
#: silencieusement du cote des validateurs. Un controle d'autorisation ne doit
#: pas avoir de branche « sinon » qui accorde quoi que ce soit.
_CAPACITES: dict[str, frozenset[str]] = {
    "redaction": REDACTEURS,
    "validation": VALIDATEURS,
    "lecture": LECTEURS,
}


def _exiger_capacite(projet: dict[str, Any], capacite: str) -> None:
    """Le precontrole d'autorisation, AVANT tout octet depose.

    POURQUOI IL EXISTE ALORS QUE POSTGRESQL REFUSE DEJA. La route composait le
    document, deposait ses octets, PUIS appelait la primitive — qui refusait.
    Le magasin gardait un objet que plus aucune ligne ne referencait, et
    qu'aucune reconciliation ne saurait rattacher a quoi que ce soit.

    IL NE REMPLACE PAS LE CONTROLE FINAL. La primitive le rejoue apres le
    depot, et c'est elle la frontiere: entre ce precontrole et l'ecriture, une
    adhesion peut etre revoquee. Deux controles, et le dernier decide.

    LE ROLE VIENT DU SERVEUR. `project_workspace_list()` le derive de
    `organization_members` sous l'identite du jeton (0021, resserre par 0023);
    il ne traverse jamais depuis le navigateur.
    """
    if not projet.get("member_active", True):
        raise ConfirmationDomainError(
            "votre acces a cette organisation a ete revoque: il n'ouvre plus "
            "aucun geste, pas meme la lecture."
        )
    # UNE CAPACITE INCONNUE REFUSE. Elle ne peut venir que d'une faute de
    # frappe dans le code de la route: mieux vaut un 422 immediat qu'un
    # controle qui porte sur autre chose que ce que son appelant croit.
    permis = _CAPACITES.get(capacite)
    if permis is None:
        raise ConfirmationDomainError(
            f"capacite inconnue: « {capacite} ». Aucun geste n'est ouvert."
        )
    role = str(projet.get("member_role") or "")
    if role not in permis:
        raise ConfirmationDomainError(
            f"le role « {role} » ne porte pas cette action. "
            + ("La creation d'un brouillon, sa revision et sa soumission a la "
               "relecture reviennent aux roles owner, admin et engineer."
               if capacite == "redaction" else
               "Le retour motive au brouillon, l'attestation et l'emission "
               "reviennent a l'ingenieur qui repond de l'etude, porteur du "
               "role validating_engineer.")
        )


def _octets_du_document(ouvert: Any, jeton: str, projet: dict[str, Any],
                        calculation_id: str, forme: str = "html",
                        ferraillage: Any = None,
                        lecture: Any = None) -> tuple[bytes, str | None]:
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

    if forme == "dxf":
        return _octets_du_dessin(calcul, ferraillage, mention, lecture), mention

    # LES DEUX FORMES DISENT LA MEME CHOSE, ET C'EST LA REGLE. Meme calcul
    # relu, meme notice, meme mention: seule la forme du fichier change. Un
    # PDF qui affirmerait autre chose que le HTML du meme calcul serait un
    # second document, pas un second format.
    if forme == "pdf":
        return rendre_note_pdf(projet, calcul, notice=notice,
                               mention=mention), mention
    document = rendre_note(projet, calcul, notice=notice, mention=mention)
    return document.encode("utf-8"), mention


def _modele_du_dessin(calcul: dict[str, Any], ferraillage: Any,
                      mention: str | None, lecture: Any = None) -> Any:
    """Le modele geometrique, **verifie avant d'exister**, depuis la requete
    GELEE du calcul.

    C'EST LE POINT OU LE DXF ET L'APERCU SE REJOIGNENT. Les deux appellent
    cette fonction, recoivent le meme objet gele, et ne recalculent rien. Un
    apercu qui montrerait autre chose que le fichier telecharge serait un
    defaut grave — l'ingenieur valide ce qu'il voit — et cette structure le
    rend impossible plutot que de le surveiller.

    CE QUE LE NAVIGATEUR ENVOIE, ET CE QU'IL N'ENVOIE PAS
    ------------------------------------------------------
    Il envoie le CHOIX DES BARRES — nombre, diametre, enrobage, cadres. C'est
    une decision d'ingenieur, pas une valeur derivable: `As_required` dit
    combien d'acier il faut, jamais comment le disposer.

    Il n'envoie ni la section, ni les materiaux, ni l'effort, ni le
    referentiel: les quatre sont relus dans `calcul["request"]`, c'est-a-dire
    la requete exacte que le moteur a recue et que la base a gelee. Un appelant
    ne peut donc pas faire dessiner une poutre qui n'a pas ete verifiee.

    C'EST LE DEFAUT DU 30/08, ET IL NE DOIT PAS REPARAITRE PAR UNE AUTRE PORTE.
    L'ecran envoyait alors une section codee en dur a l'endpoint de dessin, qui
    la dessinait correctement: l'ingenieur recevait le plan d'une poutre jamais
    verifiee, portant la mention obligatoire et son propre repere.

    RIEN N'EST PRODUIT SI LE FERRAILLAGE NE VERIFIE PAS. `verify_and_render_
    beam_section` leve avant de dessiner, et cette fonction est appelee AVANT
    tout depot: ni ligne, ni octet.

    AUCUNE DATE N'ENTRE DANS LE FICHIER. `date` reste vide — le cartouche
    imprime alors un tiret — parce que la cle du livrable derive de son
    contenu: un horodatage ferait deux objets pour un seul et meme dessin.
    """
    if ferraillage is None:
        raise ConfirmationDomainError(
            "aucun ferraillage n'a ete fourni: un plan de ferraillage sans "
            "barres ne represente rien. Le nombre et le diametre des barres "
            "sont une decision d'ingenieur, et le produit ne la prend pas a "
            "sa place."
        )

    gelee = calcul.get("request") or {}
    try:
        requete = Ec2BeamFlexureRequest(**gelee)
    except Exception as cause:
        raise ConfirmationDomainError(
            "la requete gelee de ce calcul n'est pas relisible: aucun dessin "
            "ne peut en etre tire sans risquer de representer autre chose."
        ) from cause

    try:
        modele, _tableau, _reponse = verify_and_model_beam_section(
            Ec2BeamSectionRequest(
                calculation=requete,
                reinforcement=ferraillage,
                mention=mention or "",
            ),
            provider=lecture.provider if lecture else None,
        )
    except ReinforcementNotVerified as cause:
        raise ConfirmationDomainError(str(cause)) from cause
    return modele


def _octets_du_dessin(calcul: dict[str, Any], ferraillage: Any,
                      mention: str | None, lecture: Any = None) -> bytes:
    """Les octets du DXF, transcrits depuis le modele gele."""
    modele = _modele_du_dessin(calcul, ferraillage, mention, lecture)
    tampon = io.StringIO()
    rendre_dxf(modele).write(tampon)
    return tampon.getvalue().encode("utf-8")


def _nom_du_document_emis(projet: dict[str, Any],
                          source: dict[str, Any]) -> str:
    """Le nom du document émis, dérivé de celui qu'il atteste.

    IL DIT CE QU'IL EST DÈS LE NOM DE FICHIER. Rangés côte à côte dans un
    dossier, l'original et le document émis ne doivent pas se ressembler : le
    second porte l'attestation, le premier non, et c'est le second qu'on
    transmet.
    """
    reference = "".join(
        c for c in str(projet.get("reference") or projet.get("name") or "")
        if c.isalnum() or c in "-_")[:40]
    court = "".join(c for c in str(source.get("deliverable_id") or "")
                    if c.isalnum() or c == "-")[:36]
    return f"attestation-{reference or 'projet'}-{court or 'livrable'}.pdf"


def _nom_sur(nom: str) -> str:
    """Ne garde d'un nom enregistre que des caracteres surs.

    IL VIENT DE LA BASE, PAS D'UN CORPS DE REQUETE — `_nom_de_fichier` l'y a
    ecrit, et il est deja filtre. Le refiltrer ici coute une passe et supprime
    une hypothese: le jour ou un autre chemin ecrira cette colonne, l'en-tete
    ne portera toujours rien d'autre que ce qu'on accepte.
    """
    propre = "".join(c for c in nom if c.isalnum() or c in "-_.")[:120]
    return propre or "document"


def _nom_de_fichier(projet: dict[str, Any], calcul_id: str,
                    forme: str = "html") -> str:
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
    # L'EXTENSION SUIT LA FORME REELLEMENT PRODUITE. Un `.html` servi avec
    # `application/pdf` ferait enregistrer au navigateur un fichier que son
    # systeme ouvrirait avec le mauvais programme.
    #
    # ELLE EST LUE DANS `_FORMES`, ET N'EST PAS REECRITE ICI. La version
    # precedente enumerait `pdf` puis retombait sur `html` : ajouter le DXF a
    # `_FORMES` suffisait alors a faire servir un dessin nomme `.html`.
    suffixe = _FORMES.get(forme, _FORMES["html"])[2]
    return f"note-{reference or 'projet'}-{court or 'calcul'}.{suffixe}"


def _creer(ouvert: Any, corps: LivrableCreation, project_id: str,
           supersedes_id: str | None, lecture: Any = None) -> LivrableDetail:
    """Le geste complet : produire, déposer, relire, vérifier, enregistrer.

    LA RELECTURE AVANT ENREGISTREMENT EST LE CŒUR DE CETTE FONCTION. Elle
    transforme « on a demandé au magasin d'écrire » en « les octets sont là,
    et ce sont les bons ». Sans elle, un magasin qui accepte silencieusement
    et perd le contenu — disque plein, quota, montage en lecture seule mal
    diagnostiqué — laisserait une ligne parfaitement formée devant un
    document introuvable.
    """
    jeton = _jeton_de(ouvert)

    # L'AUTORISATION AVANT LE MAGASIN, ET AVANT MEME DE COMPOSER. Un refus
    # prononce apres le depot laisse un objet orphelin; un refus prononce
    # apres la composition ne laisse rien mais fait travailler le moteur de
    # rendu pour personne. L'ordre le moins couteux est aussi le plus sur.
    try:
        projet = _projet_de(ouvert, jeton, project_id)
        _exiger_capacite(projet, "redaction")
        # LE LIVRABLE REMPLACE SE VERIFIE ICI, ET C'EST UN CORRECTIF.
        #
        # `creer_livrable` controle deja que `supersedes_id` appartient au
        # projet — mais elle le fait a la toute fin, APRES que cette fonction a
        # depose les octets. Mesure du jour: une revision visant un
        # identifiant qui n'est pas un livrable de ce projet rendait 422,
        # n'ecrivait aucune ligne, et laissait un objet dans le magasin que
        # plus rien ne referencait. Voir
        # `test_une_revision_refusee_ne_laisse_pas_d_objet_que_rien_ne_reference`.
        #
        # CE N'EST PAS UN DETAIL DE PROPRETE. La politique du magasin
        # (`docs/STOCKAGE.md` §5) interdit toute suppression par le produit:
        # l'objet abandonne est DEFINITIF. Se tromper d'identifiant de
        # livrable — une page rouverte, une URL recopiee — est l'erreur la
        # plus banale qui soit, et elle ne doit pas couter une fuite.
        #
        # ON RELIT PLUTOT QUE D'AJOUTER UNE PRIMITIVE. `project_deliverable_read`
        # figure deja parmi les fonctions declarees au backend, porte la meme
        # borne de projet et la meme exigence de capacite. Ajouter une fonction
        # d'existence elargirait la surface SQL du backend pour un controle que
        # celle-ci fait deja.
        if supersedes_id is not None:
            ouvert.atelier.relire_livrable(
                jeton, project_id=project_id, deliverable_id=supersedes_id)
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        ouvert.fermer()
        raise _refus(cause) from cause

    try:
        magasin = stockage_configure()
    except StockageIndisponible as cause:
        ouvert.fermer()
        raise _indisponible(cause) from cause

    # LA FORME EST LE SEUL CHOIX DU CLIENT, ET TOUT LE RESTE EN DECOULE:
    # genre enregistre, type de media, extension du chemin, extension du nom
    # de fichier. Les laisser diverger donnerait une ligne qui annonce un PDF
    # devant un objet HTML — et le telechargement servirait l'un en promettant
    # l'autre.
    forme = corps.format
    genre, media, extension = _FORMES[forme]

    try:
        octets, filigrane = _octets_du_document(
            ouvert, jeton, projet, corps.calculation_id, forme,
            corps.reinforcement, lecture)
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        ouvert.fermer()
        raise _refus(cause) from cause
    except CaractereNonRepresentable as cause:
        # LE DOCUMENT AURAIT PERDU UN SYMBOLE. On refuse plutot que de servir
        # une note ou `eps_s` serait devenu autre chose.
        ouvert.fermer()
        raise _indisponible(cause) from cause

    sha = empreinte(octets)
    try:
        chemin = chemin_de_livrable(
            org_id=projet["organization_id"], project_id=project_id,
            sha256=sha, extension=extension)
        magasin.deposer(chemin, octets, media)
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
            kind=genre,
            filename=_nom_de_fichier(projet, corps.calculation_id, forme),
            media_type=media, storage_backend=magasin.nom,
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
          ouvert: Any = Depends(ouvrir_atelier),
          lecture: Any = Depends(provider_de_lecture)) -> LivrableDetail:
    """Crée un brouillon depuis un calcul enregistré.

    LE DOCUMENT EST COMPOSÉ ICI, PAS DANS LE NAVIGATEUR. Le client n'envoie
    qu'un identifiant de calcul ; tout le reste — contenu, nom, empreinte,
    taille, contexte normatif, version du moteur, build, identité d'exécution
    — est produit ou dérivé côté serveur.
    """
    return _creer(ouvert, corps, project_id, supersedes_id=None,
                  lecture=lecture)


@routeur.post("/{project_id}/deliverables/preview")
def previsualiser(project_id: str, corps: LivrableCreation,
                  ouvert: Any = Depends(ouvrir_atelier),
                  lecture: Any = Depends(provider_de_lecture)) -> Response:
    """L'aperçu SVG du dessin, **sans rien déposer ni enregistrer**.

    POURQUOI UN APERÇU, ET POURQUOI CELUI-CI
    ------------------------------------------
    Choisir un ferraillage sans le voir revient à télécharger, ouvrir un
    logiciel de CAO, regarder, revenir, corriger. L'aperçu supprime ce
    va-et-vient — à une condition : qu'il montre **exactement** ce que le
    fichier contiendra.

    C'est pourquoi il ne dessine rien lui-même. Il appelle le même
    `_modele_du_dessin` que la création du livrable, reçoit le même objet gelé,
    et le transcrit. Deux implémentations indépendantes de la géométrie
    concorderaient le jour où on les écrit et divergeraient à la première
    correction de l'une des deux, sans que rien ne le signale.

    CE N'EST PAS UN LIVRABLE, ET LE PRODUIT NE FAIT PAS SEMBLANT
    -------------------------------------------------------------
    Aucun octet n'est déposé, aucune ligne n'est écrite, aucune empreinte n'est
    conservée : il n'y a rien à retrouver dix ans plus tard, et c'est voulu.
    L'image porte « APERCU NON CONTRACTUEL » **dans le dessin**, parce qu'une
    image se copie et se transmet sans le bouton qui l'a produite.

    LA CAPACITÉ EXIGÉE EST `lecture`, PAS `redaction`. Regarder n'engage rien.
    Le ferraillage envoyé ne devient une décision qu'au moment où il produit un
    livrable, et ce moment-là exige d'écrire.

    UN FERRAILLAGE QUI NE VÉRIFIE PAS N'A PAS D'APERÇU. Le même refus que pour
    le fichier : un dessin qui échoue à sa propre vérification ressemble trait
    pour trait à un dessin valide, à l'écran comme sur le papier.
    """
    jeton = _jeton_de(ouvert)
    try:
        projet = _projet_de(ouvert, jeton, project_id)
        _exiger_capacite(projet, "lecture")
        calcul = ouvert.atelier.rouvrir_calcul(
            jeton, project_id=project_id, calculation_id=corps.calculation_id)
        if not (calcul.get("result") or {}).get("result"):
            raise ConfirmationDomainError(
                "ce calcul n'a produit aucun resultat: il a ete refuse par le "
                "moteur. Il n'y a rien a dessiner, meme en apercu."
            )
        _notice, mention = _mentions(bool(calcul.get("strict_ndp")))
        modele = _modele_du_dessin(calcul, corps.reinforcement, mention, lecture)
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        raise _refus(cause) from cause
    finally:
        ouvert.fermer()

    return Response(content=rendre_svg(modele).encode("utf-8"),
                    media_type=MEDIA_TYPE_SVG, headers=_EN_TETES_DOCUMENT)


@routeur.post("/{project_id}/deliverables/{deliverable_id}/revision",
              response_model=LivrableDetail, status_code=201)
def reviser(project_id: str, deliverable_id: str, corps: LivrableCreation,
            ouvert: Any = Depends(ouvrir_atelier),
            lecture: Any = Depends(provider_de_lecture)) -> LivrableDetail:
    """Émet l'indice suivant, qui remplace celui-ci.

    C'EST LE SEUL MOYEN DE CORRIGER APRÈS ATTESTATION. Un livrable validé ou
    émis ne se modifie plus : la base le refuse, et c'est la seule façon
    qu'une attestation garde un sens. Corriger, c'est publier l'indice
    suivant, qui référence celui qu'il remplace.
    """
    return _creer(ouvert, corps, project_id, supersedes_id=deliverable_id,
                  lecture=lecture)


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
        magasin = _magasin_du_livrable(localisation)
        # LE PREMIER BLOC EST LU ICI, HORS DU GENERATEUR, et c'est
        # necessaire: un objet absent ou un magasin injoignable doit devenir un
        # 503 AVANT que le moindre en-tete ne parte. Une fois la reponse
        # commencee, il n'y a plus de code de statut a corriger.
        flux = magasin.lire_en_flux(localisation["storage_path"])
        premier = next(flux, b"")
    except (StockageIndisponible, ObjetIntrouvable, OctetsAlteres) as cause:
        raise _indisponible(cause) from cause

    return StreamingResponse(
        _servir_en_verifiant(premier, flux, localisation["sha256"]),
        media_type=localisation["media_type"],
        headers={
            "Content-Disposition": disposition_de_fichier(
                localisation["filename"]),
            **_EN_TETES_DOCUMENT,
        },
    )


#: LE MOMENT GRAVE DANS CHAQUE ENTREE D'ARCHIVE.
#:
#: ZIP N'A PAS DE CHAMP « SANS DATE ». Prendre l'heure courante rendrait deux
#: archives du MEME dossier different d'un octet, donc d'empreinte — et un
#: dossier de revue dont l'empreinte change a chaque telechargement ne peut
#: rien attester. 1980-01-01 est le plus ancien moment que le format sache
#: representer: c'est la valeur qui dit « pas de date » sans en inventer une.
_EPOQUE_ZIP = (1980, 1, 1, 0, 0, 0)

#: TOUS LES GENRES QUE `deliverable_kind` ENUMERE, dans l'ordre des migrations
#: (0001, puis `calculation_note_html` ajoute par 0020).
_GENRES_CONNUS: tuple[str, ...] = (
    "calculation_note_html", "calculation_note_pdf", "rebar_drawing_dxf",
    "rebar_drawing_pdf", "connection_drawing_dxf", "schedule_xlsx",
    "quantities_xlsx", "ifc_export", "model_json",
)


def _genres_absents() -> tuple[str, ...]:
    """Ce que le produit ne sait PAS encore produire — **derive, jamais ecrit**.

    LE MANIFESTE NOMME LES DEUX: un dossier qui listerait seulement ce qu'il
    contient laisserait croire que le reste n'existe pas parce qu'il n'a pas
    ete demande, alors qu'il n'existe pas du tout.

    CETTE LISTE ETAIT ECRITE EN DUR, ET ELLE A CESSE D'ETRE VRAIE SANS QUE
    RIEN NE BOUGE. Le jour ou la note PDF est apparue, chaque dossier de revue
    s'est mis a declarer `calculation_note_pdf` non produit — y compris le
    dossier D'UNE NOTE PDF. Le relecteur y lisait que le document qu'il tenait
    entre les mains ne devrait pas exister.

    Elle se derive donc de `_FORMES`, c'est-a-dire de ce que la route sait
    reellement composer. Ajouter une forme la retire de cette liste sans que
    personne ait a y penser — et c'est exactement la propriete qui manquait.
    """
    produits = {genre for genre, _media, _ext in _FORMES.values()}
    return tuple(g for g in _GENRES_CONNUS if g not in produits)


def _instantane_de_revue(detail: dict[str, Any],
                         fratrie: list[dict[str, Any]]) -> dict[str, Any]:
    """CE QUI EXISTAIT POUR CE CALCUL AU MOMENT OU LE DOSSIER A ETE PRIS.

    LE SILENCE SUR UN ARTEFACT SE LIT COMME SON APPROBATION, et c'est le
    defaut que cette section ferme. Un meme calcul porte desormais plusieurs
    documents — note HTML, note PDF, plan DXF. Le dossier de revue n'en
    nommait qu'un: celui qu'on relisait. Qui recevait ce dossier pouvait en
    conclure que l'etude entiere avait ete relue, alors que l'attestation ne
    couvre qu'une piece.

    IL SE DATE PAR SES PROPRES ARTEFACTS, ET C'EST UN CORRECTIF.
    ------------------------------------------------------------
    La premiere version portait l'heure de l'horloge, `now()`. Elle rendait le
    dossier NON DETERMINISTE: deux telechargements separes par une seconde
    donnaient des octets differents, et
    `test_deux_telechargements_du_dossier_rendent_les_memes_octets` est tombe
    des que la seconde a change. Un dossier dont l'empreinte bouge ne peut
    rien attester — on ne peut plus dire « voici le dossier que j'ai relu ».

    `artifacts_as_of` est donc la date du PLUS RECENT artefact enumere. Elle
    dit ce qu'une horloge disait — jusqu'ou l'inventaire porte — mais elle le
    dit avec une valeur qui vient des donnees, donc stable. Un plan produit
    apres coup fait avancer cette date; l'ancien dossier garde la sienne.

    IL NE RATISSE PAS PLUS LARGE QUE LE CALCUL. Melanger les livrables des
    autres calculs du projet ferait dire au dossier que l'attestation laisse
    de cote des documents qui ne la concernent pas — aussi faux qu'un oubli.
    """
    dates = [str(a["generated_at"]) for a in fratrie if a.get("generated_at")]
    return {
        "calculation_id": detail["calculation_id"],
        "artifacts_as_of": max(dates) if dates else None,
        # ORDRE FIXE, PAR EMPREINTE. L'ordre de la primitive suit la date de
        # creation; deux artefacts crees dans la meme seconde pourraient en
        # sortir dans un ordre variable, et l'archive cesserait d'etre
        # deterministe.
        "artifacts": sorted(
            ({
                "deliverable_id": a["deliverable_id"],
                "calculation_id": a["calculation_id"],
                "kind": a["kind"],
                "derived_from_id": a.get("derived_from_id"),
                "filename": a["filename"],
                "media_type": a["media_type"],
                "sha256": a["sha256"],
                "size_bytes": a["size_bytes"],
                "state": a["state"],
                "revision": a["revision"],
                "is_the_reviewed_one": (
                    a["deliverable_id"] == detail["deliverable_id"]),
            } for a in fratrie),
            key=lambda a: (a["sha256"], a["deliverable_id"]),
        ),
    }


def _portee_de_l_attestation(
        detail: dict[str, Any],
        instantane: dict[str, Any]) -> tuple[dict[str, Any] | None,
                                             list[dict[str, Any]]]:
    """Ce que l'attestation couvre, et ce qu'elle NE couvre PAS.

    VALIDER LE PDF NE VALIDE PAS LE DXF. Un ingenieur atteste des octets
    precis, identifies par leur empreinte; tout le reste lui reste etranger,
    et le dossier doit l'ecrire plutot que de le laisser supposer.

    Sans attestation, `couvre` vaut `null` et la liste est vide: des champs
    absents se liraient moins clairement que des champs vides — le lecteur ne
    saurait pas si la question a seulement ete posee.
    """
    if not detail.get("validation_id"):
        return None, []
    couvre = {
        "deliverable_id": detail["deliverable_id"],
        "kind": detail["kind"],
        "filename": detail["filename"],
        "sha256": detail["sha256"],
    }
    autres = [
        {"deliverable_id": a["deliverable_id"], "kind": a["kind"],
         "filename": a["filename"], "sha256": a["sha256"],
         "state": a["state"]}
        for a in instantane["artifacts"]
        if a["deliverable_id"] != detail["deliverable_id"]
    ]
    return couvre, autres


def _manifeste(projet: dict[str, Any], detail: dict[str, Any],
               octets: bytes, fratrie: list[dict[str, Any]]) -> dict[str, Any]:
    """Ce que le dossier contient, et a quoi cela se rattache.

    TOUT VIENT DES DONNEES GELEES. Pas un champ n'est recalcule : le contexte
    normatif, la version du moteur, le build, l'identite d'execution et
    l'empreinte des entrees sont les colonnes que la primitive a rendues, et
    l'empreinte du document est celle des octets **relus dans le magasin**.

    LES DEUX EMPREINTES SONT ECRITES SEPAREMENT, et c'est le point : celle que
    la base a enregistree, et celle des octets qui partent dans l'archive. Un
    manifeste qui n'en porterait qu'une ne permettrait pas de constater
    qu'elles s'accordent — il l'affirmerait.
    """
    instantane = _instantane_de_revue(detail, fratrie)
    couvre, non_couverts = _portee_de_l_attestation(detail, instantane)
    return {
        "kind": "eurostruct/review-bundle",
        # VERSION 2: le manifeste porte desormais l'instantane du dossier et la
        # portee exacte de l'attestation. Un lecteur qui saurait lire la
        # version 1 ne trouverait pas ces sections; il doit pouvoir s'en
        # apercevoir plutot que de conclure qu'il n'y a rien d'autre.
        "version": 2,
        "organization": {
            "id": projet["organization_id"],
            "name": projet["organization_name"],
        },
        "project": {
            "id": projet["project_id"],
            "name": projet["name"],
            "reference": projet.get("reference"),
            "country": projet["country"],
            "region": projet.get("region"),
            "ndp_as_of": projet["ndp_as_of"],
        },
        "calculation": {
            "id": detail["calculation_id"],
            "inputs_hash": detail.get("inputs_hash"),
            "ndp_as_of": detail.get("ndp_as_of"),
            "engine_version": detail["engine_version"],
            "engine_build_sha": detail.get("engine_build_sha"),
            "execution_identity": detail.get("execution_identity"),
        },
        "deliverable": {
            "id": detail["deliverable_id"],
            "kind": detail["kind"],
            "filename": detail["filename"],
            "state": detail["state"],
            "revision": detail["revision"],
            "supersedes_id": detail.get("supersedes_id"),
            "watermark": detail.get("watermark"),
            "generated_at": detail["generated_at"],
        },
        "files": [{
            "path": f"documents/{detail['filename']}",
            "media_type": detail["media_type"],
            "sha256_recorded": detail["sha256"],
            "sha256_served": empreinte(octets),
            "size_bytes": len(octets),
        }],
        # LES ARTEFACTS QUI N'EXISTENT PAS ENCORE SONT NOMMES.
        "artifacts_not_produced": list(_genres_absents()),
        # CE QUI EXISTAIT POUR CE CALCUL, AU MOMENT OU LE DOSSIER A ETE PRIS.
        "review_snapshot": instantane,
        # L'ATTESTATION, SI ELLE EXISTE. `null` partout ailleurs: un dossier de
        # revue d'un brouillon ne doit pas ressembler a celui d'une piece
        # attestee, et l'absence de champs le dirait moins clairement que des
        # champs a `null`.
        "attestation": {
            "kind": "attestation_metier_authentifiee",
            "is_qualified_electronic_signature": False,
            "validation_id": detail.get("validation_id"),
            "validator_name": detail.get("validator_name"),
            "validator_role": detail.get("validator_role"),
            "professional_id": detail.get("professional_id"),
            "statement": detail.get("statement"),
            "reservations": detail.get("reservations"),
            "signed_at": detail.get("validated_at"),
            # LA PORTEE, DES DEUX COTES. `covers` nomme les octets attestes
            # par leur empreinte; `does_not_cover` nomme tous les autres
            # artefacts du meme calcul. Ne pas les nommer reviendrait a
            # laisser supposer qu'ils le sont.
            "covers": couvre,
            "does_not_cover": non_couverts,
        },
        "transitions": detail.get("transitions") or [],
        "notice": MENTION_OBLIGATOIRE,
        "mention": detail.get("watermark") or None,
    }


@routeur.get("/{project_id}/deliverables/{deliverable_id}/review-bundle")
def dossier_de_revue(project_id: str, deliverable_id: str,
                     ouvert: Any = Depends(ouvrir_atelier)) -> Response:
    """Le dossier de revue : le document, et le manifeste qui le rattache.

    CE QU'IL CONTIENT
    ------------------
    ``documents/<nom>`` — les octets **exacts** du livrable, lus dans le
    magasin, jamais recomposés. ``manifeste.json`` — l'organisation, le projet,
    le contexte normatif, la version et le SHA du moteur, l'identité
    d'exécution, l'empreinte des entrées, l'empreinte du document telle
    qu'enregistrée **et** telle que servie, l'attestation si elle existe, et
    l'historique des transitions.

    IL EST DÉTERMINISTE, ET C'EST NÉCESSAIRE. Deux téléchargements du même
    dossier rendent les **mêmes octets** : dates d'archive figées, entrées dans
    un ordre fixe, JSON aux clés triées. Un dossier dont l'empreinte change à
    chaque appel ne peut rien attester — on ne pourrait pas dire « voici le
    dossier que j'ai relu ».

    IL NE PRODUIT NI N'ENREGISTRE RIEN. C'est une lecture : aucun livrable
    n'est créé, aucun octet n'est déposé, et le moteur n'est pas relancé.
    """
    jeton = _jeton_de(ouvert)
    try:
        projet = _projet_de(ouvert, jeton, project_id)
        detail = ouvert.atelier.relire_livrable(
            jeton, project_id=project_id, deliverable_id=deliverable_id)
        # LA FRATRIE VIENT DE LA MEME SESSION QUE LA RELECTURE. Deux appels
        # separes pourraient tomber de part et d'autre d'une creation, et
        # l'instantane dirait alors qu'il n'existe rien d'autre alors qu'un
        # plan vient d'etre produit.
        fratrie = [
            a for a in ouvert.atelier.livrables(jeton, project_id=project_id)
            if a["calculation_id"] == detail["calculation_id"]
        ]
        localisation = ouvert.atelier.octets_du_livrable(
            jeton, project_id=project_id, deliverable_id=deliverable_id)
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        raise _refus(cause) from cause
    finally:
        ouvert.fermer()

    try:
        magasin = _magasin_du_livrable(localisation)
        # LE DOSSIER EST UNE ARCHIVE: il faut les octets ENTIERS pour les
        # comprimer, et les verifier avant de les y mettre. Le flux n'a donc
        # pas d'objet ici — ce que la borne de taille du magasin encadre deja.
        octets = magasin.lire(localisation["storage_path"])
        if empreinte(octets) != localisation["sha256"]:
            raise OctetsAlteres(
                "les octets stockes ne portent plus l'empreinte enregistree: "
                "on refuse de les mettre dans un dossier de revue."
            )
    except (StockageIndisponible, ObjetIntrouvable, OctetsAlteres) as cause:
        raise _indisponible(cause) from cause

    # AUCUNE HORLOGE N'ENTRE DANS LE DOSSIER, et c'est ce qui le rend
    # attestable: deux telechargements rendent exactement les memes octets.
    manifeste = json.dumps(_manifeste(projet, detail, octets, fratrie),
                           ensure_ascii=False, indent=2, sort_keys=True)

    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_DEFLATED) as archive:
        for chemin, contenu in (
            (f"documents/{detail['filename']}", octets),
            ("manifeste.json", manifeste.encode("utf-8")),
        ):
            entree = zipfile.ZipInfo(chemin, date_time=_EPOQUE_ZIP)
            entree.external_attr = 0o644 << 16
            archive.writestr(entree, contenu)

    # LE NOM DE L'ARCHIVE SUIT LE DOCUMENT, IL NE LE RECALCULE PAS.
    #
    # Il etait reconstruit ici par `_nom_de_fichier(projet, calcul)`, puis son
    # `.html` retire. Deux consequences, l'une mesuree, l'autre latente:
    #
    #   * MESUREE — les dossiers de la note HTML et de la note PDF du meme
    #     calcul se telechargeaient sous LE MEME NOM. Le navigateur du
    #     relecteur les range en « (1) », et plus rien ne dit laquelle
    #     contient quoi.
    #   * LATENTE — un nom recalcule reflete le projet d'AUJOURD'HUI, tandis
    #     que le document dans l'archive porte celui du jour de sa creation.
    #     Renommer un projet suffisait a les faire diverger.
    #
    # `detail['filename']` est le nom ENREGISTRE avec les octets. Son extension
    # distingue les formes, et il ne bouge plus.
    nom = f"dossier-revue-{_nom_sur(detail['filename'])}.zip"
    return Response(
        content=tampon.getvalue(), media_type="application/zip",
        headers={
            "Content-Disposition": disposition_de_fichier(nom),
            **_EN_TETES_DOCUMENT,
        },
    )


def _magasin_du_livrable(localisation: dict[str, Any]):
    """Le magasin configure, s'il est bien CELUI qui detient ces octets.

    UN LIVRABLE DEPOSE SUR S3 NE SE LIT PAS SUR LE DISQUE LOCAL. Servir « ce
    qu'on trouve la ou on regarde aujourd'hui » rendrait un document d'un
    autre deploiement, ou rien du tout, sans que la difference se voie.
    """
    magasin = stockage_configure()
    if magasin.nom != localisation["storage_backend"]:
        raise StockageIndisponible(
            f"le livrable a ete depose dans le magasin "
            f"« {localisation['storage_backend']} » et le service est "
            f"configure avec « {magasin.nom} ». On refuse plutot que de "
            "servir des octets venus d'ailleurs."
        )
    return magasin


def _servir_en_verifiant(premier: bytes, reste, attendue: str):
    """Sert les octets par blocs, en verifiant l'empreinte AU FIL DE L'EAU.

    POURQUOI PAS UNE LECTURE COMPLETE PUIS UNE VERIFICATION. Elle tiendrait
    l'objet entier en memoire — jusqu'a la borne de 32 Mio — pour chaque
    telechargement concurrent. Une note pese quelques dizaines de kilo-octets;
    un dossier de pieces jointes ne fera pas cette promesse.

    CE QUE LE FLUX NE PEUT PAS FAIRE, ET QUI EST DIT ICI. L'empreinte n'est
    connue qu'a la fin: les premiers blocs sont deja partis quand une
    alteration se revele. Le generateur LEVE alors plutot que de conclure, et
    le client recoit une reponse INTERROMPUE — un corps tronque, detectable,
    au lieu d'un document complet et faux. L'empreinte attendue reste par
    ailleurs lisible sur la fiche du livrable et dans le manifeste du dossier
    de revue: un destinataire peut la verifier lui-meme.
    """
    calcul = hashlib.sha256()
    if premier:
        calcul.update(premier)
        yield premier
    for bloc in reste:
        calcul.update(bloc)
        yield bloc
    if calcul.hexdigest() != attendue:
        raise OctetsAlteres(
            "les octets stockes ne portent plus l'empreinte enregistree. Le "
            "document a ete altere depuis son depot: la reponse est "
            "interrompue plutot que servie entiere."
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
            corps: EmissionDemande | None = None,
            ouvert: Any = Depends(ouvrir_atelier)) -> LivrableDetail:
    """Émet le livrable, **et produit le document attesté**.

    SÉPARÉE DE L'ATTESTATION, ET DÉLIBÉRÉMENT. Valider, c'est répondre du
    calcul ; émettre, c'est mettre le document en circulation. Les fondre
    ferait de toute relecture une publication.

    CE QUE L'ÉMISSION AJOUTE, ET POURQUOI
    ---------------------------------------
    Le nom du validateur, son rôle, son inscription, sa déclaration, ses
    réserves et la date vivaient dans la base — c'est-à-dire là où le
    destinataire du document ne les voit pas. Le PDF qu'on lui transmettait ne
    portait rien de tout cela.

    Le retoucher pour y ajouter l'attestation était exclu : **son empreinte
    est ce sur quoi l'attestation porte**. Émettre produit donc un SECOND PDF,
    immuable, qui référence l'original par son SHA-256 sans le modifier d'un
    bit.

    L'ORDRE EST LE SEUL QUI NE MENTE PAS : composer, déposer, **relire**,
    vérifier l'empreinte, puis appeler la primitive qui bascule l'original et
    enregistre le document émis **dans une seule transaction**. Si cette
    transaction échoue après le dépôt, l'objet devient un orphelin que le
    scanner détecte — coût accepté. L'inverse ne l'est pas : la base ne doit
    jamais référencer des octets qu'on n'a pas su relire.

    UNE SECONDE TENTATIVE NE COÛTE PAS UN SECOND DOCUMENT. Le PDF émis est
    composé depuis des données gelées : il retombe sur les mêmes octets, donc
    sur le même chemin, et la primitive rend le document déjà émis.
    """
    jeton = _jeton_de(ouvert)
    try:
        projet = _projet_de(ouvert, jeton, project_id)
        # LA CAPACITE AVANT LE MAGASIN. Un refus prononcé après le dépôt
        # laisserait un objet que plus rien ne référencerait, et la politique
        # du magasin interdit au produit de le supprimer.
        _exiger_capacite(projet, "validation")
        source = ouvert.atelier.relire_livrable(
            jeton, project_id=project_id, deliverable_id=deliverable_id)
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        ouvert.fermer()
        raise _refus(cause) from cause

    # SEULE UNE NOTE EN PDF DONNE LIEU A UN DOCUMENT ATTESTE. Les autres
    # s'emettent comme avant, et il ne faut PAS le leur retirer.
    #
    # Un plan de ferraillage se transmet tel quel: il ne porte pas
    # d'attestation nominative de calcul, et lui en fabriquer une laisserait
    # croire qu'un ingenieur repond du dessin comme il repond des nombres. La
    # note HTML, elle, est un format de lecture. Refuser de les emettre aurait
    # ete une REGRESSION que la suite existante a mesuree: ils s'emettaient
    # avant ce lot, et rien ne justifie de le leur enlever.
    if source.get("kind") != "calculation_note_pdf":
        try:
            ouvert.atelier.emettre_livrable(
                jeton, project_id=project_id, deliverable_id=deliverable_id)
            return _detail(ouvert.atelier.relire_livrable(
                jeton, project_id=project_id, deliverable_id=deliverable_id))
        except (AuthentificationRequise, ConfirmationDomainError) as cause:
            raise _refus(cause) from cause
        finally:
            ouvert.fermer()

    try:
        magasin = stockage_configure()
    except StockageIndisponible as cause:
        ouvert.fermer()
        raise _indisponible(cause) from cause

    try:
        octets = rendre_attestation_pdf(projet, source)
    except CaractereNonRepresentable as cause:
        ouvert.fermer()
        raise _indisponible(cause) from cause

    sha = empreinte(octets)
    try:
        chemin = chemin_de_livrable(
            org_id=projet["organization_id"], project_id=project_id,
            sha256=sha, extension="pdf")
        magasin.deposer(chemin, octets, MEDIA_TYPE_PDF)
        relus = magasin.lire(chemin)
        if empreinte(relus) != sha or len(relus) != len(octets):
            raise OctetsAlteres(
                f"les octets relus depuis « {chemin} » ne portent pas "
                "l'empreinte deposee. Le livrable n'est PAS emis: une "
                "attestation qu'on ne sait pas relire n'atteste rien."
            )
    except (StockageIndisponible, ObjetIntrouvable, OctetsAlteres) as cause:
        ouvert.fermer()
        raise _indisponible(cause) from cause

    try:
        emis = ouvert.atelier.emettre_avec_attestation(
            jeton, project_id=project_id, source_id=deliverable_id,
            filename=_nom_du_document_emis(projet, source),
            media_type=MEDIA_TYPE_PDF, storage_backend=magasin.nom,
            storage_path=chemin, sha256=sha, size_bytes=len(octets))
        return _detail(
            ouvert.atelier.relire_livrable(
                jeton, project_id=project_id, deliverable_id=deliverable_id),
            document_emis=emis)
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        raise _refus(cause) from cause
    finally:
        ouvert.fermer()
