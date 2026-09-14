"""Entrer dans l'application : fonder son bureau, inviter, administrer.

LE CUL-DE-SAC QUE CES ROUTES FERMENT
--------------------------------------
Tout le produit suppose une ligne dans ``organization_members``. Sans elle,
``GET /v1/projects`` rendait une liste **vide** — pas une erreur, pas une
explication, un écran nu — et la création d'un projet refusait par « aucune
organisation ». Ce refus est juste. Ce qui manquait, c'est la suite : **aucune
route ne permettait d'en sortir.** La seule façon d'exister dans l'application
était un ``insert`` fait à la main par le propriétaire de la base.

OÙ VIT LE SECRET D'UNE INVITATION
-----------------------------------
Il est tiré **ici**, par ``secrets.token_urlsafe``, et la base n'en reçoit que
le sha256. Il apparaît dans **une** réponse HTTP et nulle part ailleurs : ni
en base, ni dans les journaux, ni dans un rechargement de l'écran. C'est le
prix de la propriété qui compte — une fuite de sauvegarde ne rend aucun lien
utilisable — et il est explicitement dit à l'appelant.

CE QUE CES ROUTES NE DÉCIDENT PAS
-----------------------------------
Aucune ne juge un rôle. « Un admin ne peut pas inviter un owner », « on ne
modifie pas sa propre adhésion », « le dernier propriétaire actif ne disparaît
pas » : les trois règles sont dans PostgreSQL, dans
``0024_entree_application.sql``, et les routes se contentent d'en traduire les
refus. Une vérification applicative de plus donnerait deux frontières, dont la
plus faible finirait par décider.
"""
from __future__ import annotations

import hashlib
import secrets
from typing import Any

from eurostruct_engine.ndp.confirmation import ConfirmationDomainError
from eurostruct_engine.ndp.postgres_provider import AuthentificationRequise
from eurostruct_engine.schemas.organisation import (
    ROLES,
    AdhesionModifiee,
    Invitation,
    InvitationAcceptee,
    InvitationCreation,
    InvitationEmise,
    JetonInvitation,
    ListeInvitations,
    ListeMembres,
    Membre,
    MembreModification,
    Organisation,
    OrganisationCreation,
)
from fastapi import APIRouter, Depends, HTTPException

from ..dependances import ouvrir_atelier

routeur = APIRouter(prefix="/v1/organizations", tags=["entree"])

#: LE SECRET D'UNE INVITATION. 32 octets d'aléa cryptographique — environ 256
#: bits — rendus en base64url. Deviner un lien à ce prix n'est pas une menace
#: qu'on borne par la limitation de débit : c'est une menace qui n'existe pas.
OCTETS_DU_SECRET = 32


def _refus(cause: AuthentificationRequise | ConfirmationDomainError) -> HTTPException:
    """Traduit un refus CONNU. Une exception inattendue ne passe pas par ici.

    Même règle que sur les autres chemins : ``psycopg2.OperationalError`` porte
    la chaîne de connexion, mot de passe compris. Attraper ``Exception`` pour
    en faire un 422 avec ``str(cause)`` ferait sortir cela au client, sous un
    code qui se lit « votre demande est refusée » — donc sans alerte.
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
        detail={"error": "entree_refusee", "what": type(cause).__name__,
                "detail": str(cause)},
    )


def _jeton_de(ouvert: Any) -> str:
    return ouvert.jeton


def _role_connu(role: str) -> str:
    """Refuse un rôle inconnu **avant** de l'envoyer à PostgreSQL.

    Ce n'est pas la frontière — le type ``org_role`` refuserait de toute façon
    — mais un cast raté rend un message de pilote au lieu d'une phrase. Le
    contrôle existe pour la lisibilité du refus, jamais pour la sécurité.
    """
    if role not in ROLES:
        raise HTTPException(
            status_code=422,
            detail={"error": "entree_refusee", "what": "role",
                    "detail": (f"« {role} » n'est pas un role connu. Les cinq "
                               f"roles sont: {', '.join(ROLES)}.")},
        )
    return role


@routeur.get("", response_model=list[Organisation])
def lister(ouvert: Any = Depends(ouvrir_atelier)) -> list[Organisation]:
    """Les bureaux de l'appelant, et son rôle dans chacun.

    SÉPARÉE DE ``GET /v1/projects`` DÉLIBÉRÉMENT. Un compte tout neuf a zéro
    projet **et** zéro organisation ; un compte qui vient de fonder son bureau
    a zéro projet et **une** organisation. Les deux écrans à montrer ne sont
    pas les mêmes — « créez votre bureau » d'un côté, « créez votre premier
    projet » de l'autre — et une seule liste vide ne permet pas de les
    distinguer.
    """
    try:
        organisations = ouvert.atelier.organisations(_jeton_de(ouvert))
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        raise _refus(cause) from cause
    finally:
        ouvert.fermer()
    return [Organisation(**o) for o in organisations]


@routeur.post("", response_model=Organisation, status_code=201)
def fonder(corps: OrganisationCreation,
           ouvert: Any = Depends(ouvrir_atelier)) -> Organisation:
    """Fonde un bureau, et son propriétaire avec lui.

    ATOMIQUE, ET LA PRIMITIVE LE GARANTIT. L'organisation et l'adhésion
    ``owner`` naissent ensemble ou pas du tout : une organisation sans
    propriétaire serait un bureau que personne ne peut administrer, et il
    faudrait un ``insert`` à la main pour l'en sortir — le cul-de-sac de
    départ, un cran plus loin.

    UN DOUBLE-CLIC NE FONDE PAS DEUX BUREAUX. Un second appel avec le même nom
    rend le même bureau : c'est ce que l'utilisateur voulait, une fois.

    LE FONDATEUR VIENT DU JETON. Le corps n'a aucun champ pour le désigner, et
    c'est ce qui rend l'appartenance autre chose qu'une affirmation.
    """
    jeton = _jeton_de(ouvert)
    try:
        identifiant = ouvert.atelier.fonder_organisation(
            jeton, name=corps.name, country=corps.country,
            display_name=corps.display_name,
            professional_id=corps.professional_id)
        # LA RELECTURE SUIT LA FONDATION, dans la même requête. Rendre
        # l'identifiant seul obligerait l'écran à construire le bureau de son
        # côté en attendant, donc à afficher des champs que la base n'a pas
        # confirmés.
        for organisation in ouvert.atelier.organisations(jeton):
            if organisation["organization_id"] == identifiant:
                return Organisation(**organisation)
        raise ConfirmationDomainError(
            "le bureau vient d'etre fonde et reste invisible: on refuse "
            "d'annoncer une entree qu'on ne peut pas relire."
        )
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        raise _refus(cause) from cause
    finally:
        ouvert.fermer()


@routeur.post("/{org_id}/invitations", response_model=InvitationEmise,
              status_code=201)
def inviter(org_id: str, corps: InvitationCreation,
            ouvert: Any = Depends(ouvrir_atelier)) -> InvitationEmise:
    """Émet un lien d'invitation. **Le secret n'apparaît qu'ici.**

    IL EST TIRÉ PAR L'API, ET LA BASE N'EN VOIT QUE L'EMPREINTE. Une fuite de
    sauvegarde, un journal trop bavard ou une lecture accidentelle ne rendent
    aucun lien utilisable. En contrepartie, ce secret ne peut pas être
    réaffiché : il faut le copier maintenant, ou révoquer et réémettre.

    AUCUNE ADRESSE N'EST DEMANDÉE, ET C'EST UNE DÉCISION. Une invitation liée
    à une adresse ouvre l'énumération des comptes : « invitez
    untel@exemple.fr » répondrait différemment selon que le compte existe ou
    non, et l'on apprendrait qui travaille où. Le lien se transmet par le
    canal que l'émetteur choisit.
    """
    role = _role_connu(corps.role)
    # LE SECRET NE TRAVERSE NI LE SQL NI LES JOURNAUX. Seule son empreinte
    # descend; lui remonte, une fois, dans le corps de cette réponse.
    secret = secrets.token_urlsafe(OCTETS_DU_SECRET)
    empreinte = hashlib.sha256(secret.encode("utf-8")).hexdigest()
    try:
        emise = ouvert.atelier.emettre_invitation(
            _jeton_de(ouvert), org_id=org_id, role=role,
            token_sha256=empreinte, label=corps.label,
            display_name=corps.display_name,
            professional_id=corps.professional_id,
            validity_days=corps.validity_days)
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        raise _refus(cause) from cause
    finally:
        ouvert.fermer()
    return InvitationEmise(
        invitation_id=emise["invitation_id"], organization_id=org_id,
        role=role, expires_at=emise["expires_at"] or "", token=secret)


@routeur.get("/{org_id}/invitations", response_model=ListeInvitations)
def lister_invitations(org_id: str,
                       ouvert: Any = Depends(ouvrir_atelier)) -> ListeInvitations:
    """Les invitations de ce bureau — **sans le secret ni son empreinte**.

    Le premier n'existe plus ; la seconde suffirait à reconnaître un lien
    intercepté ailleurs, et n'aide en rien l'écran.
    """
    try:
        invitations = ouvert.atelier.invitations(_jeton_de(ouvert),
                                                 org_id=org_id)
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        raise _refus(cause) from cause
    finally:
        ouvert.fermer()
    return ListeInvitations(
        invitations=[Invitation(**i) for i in invitations])


@routeur.delete("/{org_id}/invitations/{invitation_id}", status_code=204)
def revoquer(org_id: str, invitation_id: str,
             ouvert: Any = Depends(ouvrir_atelier)) -> None:
    """Révoque un lien encore en attente.

    UNE INVITATION DÉJÀ CONSOMMÉE NE SE RÉVOQUE PAS. Révoquer un lien qui a
    servi ne retirerait personne du bureau — l'adhésion existe — et laisserait
    croire le contraire. Pour retirer quelqu'un : désactiver son adhésion.
    """
    try:
        ouvert.atelier.revoquer_invitation(
            _jeton_de(ouvert), org_id=org_id, invitation_id=invitation_id)
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        raise _refus(cause) from cause
    finally:
        ouvert.fermer()


@routeur.get("/{org_id}/members", response_model=ListeMembres)
def lister_membres(org_id: str,
                   ouvert: Any = Depends(ouvrir_atelier)) -> ListeMembres:
    """L'équipe du bureau, telle que la base la porte.

    LES ADHÉSIONS DÉSACTIVÉES Y FIGURENT, et c'est voulu depuis 0009 : une
    note de dix ans doit rester lisible et nommer son signataire. Ce qui
    disparaît en désactivant, c'est l'accès, pas la trace.
    """
    try:
        membres = ouvert.atelier.membres(_jeton_de(ouvert), org_id=org_id)
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        raise _refus(cause) from cause
    finally:
        ouvert.fermer()
    return ListeMembres(members=[Membre(**m) for m in membres])


@routeur.patch("/{org_id}/members/{user_id}", response_model=AdhesionModifiee)
def modifier_membre(org_id: str, user_id: str, corps: MembreModification,
                    ouvert: Any = Depends(ouvrir_atelier)) -> AdhesionModifiee:
    """Change le rôle, l'état ou le nom professionnel d'un **collègue**.

    LES QUATRE REFUS VIENNENT DE POSTGRESQL, et aucun n'est rejoué ici :

    * on ne modifie pas sa propre adhésion — se promouvoir ``owner``, ou se
      donner ``validating_engineer`` pour attester son propre travail, sont le
      même geste vu de deux côtés ;
    * un ``admin`` ne crée ni ne modifie un ``owner`` ;
    * le dernier propriétaire actif ne disparaît pas, ni par changement de
      rôle ni par désactivation ;
    * un rôle inconnu est refusé par le type.

    ``update_names`` DOIT ÊTRE DEMANDÉ. Sans lui, ``display_name`` et
    ``professional_id`` sont ignorés : un formulaire partiel effacerait le nom
    sous lequel quelqu'un a signé.
    """
    role = _role_connu(corps.role) if corps.role is not None else None
    try:
        modifiee = ouvert.atelier.modifier_membre(
            _jeton_de(ouvert), org_id=org_id, user_id=user_id, role=role,
            is_active=corps.is_active, display_name=corps.display_name,
            professional_id=corps.professional_id,
            toucher_noms=corps.update_names)
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        raise _refus(cause) from cause
    finally:
        ouvert.fermer()
    return AdhesionModifiee(**modifiee)


# LE ROUTEUR DE L'ACCEPTATION EST SÉPARÉ, ET SON CHEMIN AUSSI.
#
# Un invité ne connaît PAS l'organisation qui l'invite : c'est le secret qui
# la lui apprend. Une route sous ``/v1/organizations/{org_id}/…`` l'obligerait
# à nommer un identifiant qu'il n'a pas — et si le lien le portait, il
# suffirait d'en changer pour sonder l'existence d'autres bureaux.
routeur_invitations = APIRouter(prefix="/v1/invitations", tags=["entree"])


@routeur_invitations.post("/accept", response_model=InvitationAcceptee)
def accepter(corps: JetonInvitation,
             ouvert: Any = Depends(ouvrir_atelier)) -> InvitationAcceptee:
    """Rejoint un bureau avec un lien, sous identité authentifiée.

    LE LIEN SEUL NE SUFFIT PAS. Il faut aussi un jeton valide : une adhésion
    créée sans identité ne désignerait personne, et le premier passant
    entrerait dans le bureau.

    LE REFUS EST LE MÊME dans les quatre cas — inconnue, expirée, révoquée,
    déjà consommée. Distinguer « ce lien n'existe pas » de « ce lien a
    expiré » apprendrait à qui essaie des liens au hasard quand il a visé
    juste.

    LE NOM PROFESSIONNEL VIENT DE L'INVITATION, PAS DE L'INVITÉ. Quelqu'un qui
    choisirait lui-même le nom sous lequel il atteste pourrait signer sous
    celui d'un autre : c'est exactement ce que 0009 et 0020 ferment en
    dérivant ces valeurs de l'adhésion.
    """
    empreinte = hashlib.sha256(corps.token.encode("utf-8")).hexdigest()
    try:
        acceptee = ouvert.atelier.accepter_invitation(
            _jeton_de(ouvert), token_sha256=empreinte)
    except (AuthentificationRequise, ConfirmationDomainError) as cause:
        raise _refus(cause) from cause
    finally:
        ouvert.fermer()
    return InvitationAcceptee(**acceptee)
