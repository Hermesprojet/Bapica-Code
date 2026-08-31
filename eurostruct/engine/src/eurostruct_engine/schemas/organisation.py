"""Les formes de fil de l'entrée : fonder, inviter, administrer.

CE QU'AUCUN DE CES CORPS NE PORTE
----------------------------------
**L'identité de celui qui agit.** Elle vient du jeton, dérivée par
``project_backend_actor()`` dans PostgreSQL, et pas une seule de ces formes
n'a de champ pour elle. Deux formes portent l'identité de celui qui *subit* —
modifier l'adhésion d'un collègue — et la primitive refuse que ce soit
l'appelant.

CE QUE ``InvitationEmise`` PORTE UNE SEULE FOIS
------------------------------------------------
Le secret du lien. Il est tiré par l'API, la base n'en connaît que
l'empreinte, et cette réponse est le **seul** endroit où il apparaîtra jamais.
Ni la liste des invitations, ni les journaux, ni un rechargement de l'écran ne
le montreront de nouveau : il n'existe plus nulle part.

CE QU'AUCUNE DE CES RÉPONSES NE DIT
------------------------------------
« Habilité ». Un ``validating_engineer`` créé ici porte un rôle
d'**organisation** : il décide qui, dans ce bureau, atteste un livrable. Il ne
porte aucune habilitation **normative** — celle-là se prend par le quatre-yeux,
et le registre national reste à 0/29.
"""

from __future__ import annotations

from pydantic import Field

from .common import CountryCode, Strict

__all__ = [
    "AdhesionModifiee",
    "Invitation",
    "InvitationAcceptee",
    "InvitationCreation",
    "InvitationEmise",
    "JetonInvitation",
    "ListeInvitations",
    "ListeMembres",
    "Membre",
    "MembreModification",
    "Organisation",
    "OrganisationCreation",
]

#: LES CINQ RÔLES D'ORGANISATION, tels que l'énumération PostgreSQL les nomme.
#: Le contrat les répète pour que l'interface les propose sans les deviner ;
#: la frontière, elle, reste dans la base — un rôle inconnu y est refusé par
#: le type, avant toute politique.
ROLES = ("owner", "admin", "engineer", "validating_engineer", "viewer")


class OrganisationCreation(Strict):
    """Ce qu'une personne saisit pour fonder son bureau.

    AUCUN CHAMP NE DÉSIGNE LE FONDATEUR. C'est l'appelant, dérivé du jeton :
    fonder au nom de quelqu'un d'autre n'a pas de sens, et l'accepter dans le
    corps ferait de l'appartenance une simple affirmation.
    """

    name: str = Field(min_length=1, max_length=200)
    country: CountryCode
    display_name: str | None = Field(
        default=None, max_length=200,
        description="Le nom professionnel du fondateur dans ce bureau. Il "
                    "figurera sur les attestations qu'il signera ; sans lui, "
                    "la primitive d'attestation refuse.")
    professional_id: str | None = Field(
        default=None, max_length=100,
        description="Numéro d'inscription à l'ordre ou à la chambre "
                    "professionnelle. Il n'est vérifié par personne ici, et "
                    "aucune valeur n'est inventée : il est reproduit tel quel.")


class Organisation(Strict):
    """Un bureau, tel que l'écran d'entrée le montre."""

    organization_id: str
    name: str
    country: CountryCode
    member_role: str = Field(
        description="Le rôle de l'appelant DANS ce bureau. Dérivé de "
                    "l'adhésion, jamais déclaré.")


class InvitationCreation(Strict):
    """Ce qu'un owner ou un admin saisit pour accueillir quelqu'un.

    AUCUNE ADRESSE ÉLECTRONIQUE. Une invitation liée à une adresse ouvre
    l'énumération des comptes : « invitez untel@exemple.fr » répondrait
    différemment selon que le compte existe ou non, et l'on apprendrait qui
    travaille où. ``label`` est un aide-mémoire libre pour l'émetteur ; il
    n'entre dans aucune décision.
    """

    role: str = Field(
        description="Le rôle que l'invité aura. Un « admin » ne peut pas "
                    "inviter un « owner » : il donnerait plus que son propre "
                    "pouvoir.")
    label: str | None = Field(
        default=None, max_length=200,
        description="Aide-mémoire libre, pour que l'émetteur s'y retrouve. "
                    "N'entre dans aucune décision.")
    display_name: str | None = Field(
        default=None, max_length=200,
        description="Le nom professionnel sous lequel l'invité signera. POSÉ "
                    "PAR L'ORGANISATION, jamais par l'invité : quelqu'un qui "
                    "choisirait lui-même ce nom pourrait attester sous celui "
                    "d'un autre.")
    professional_id: str | None = Field(default=None, max_length=100)
    validity_days: int = Field(
        default=14, ge=1, le=90,
        description="Durée de validité du lien. Un lien qui n'expire jamais "
                    "est un mot de passe permanent.")


class InvitationEmise(Strict):
    """La réponse à une émission — et le SEUL endroit où le secret apparaît.

    ``token`` N'EST PAS EN BASE. PostgreSQL n'en détient que le sha256 : une
    fuite de sauvegarde, un journal trop bavard ou une lecture accidentelle ne
    rendent aucun lien utilisable. En contrepartie, ce secret ne peut pas être
    réaffiché : il faut le copier maintenant, ou révoquer et réémettre.
    """

    invitation_id: str
    organization_id: str
    role: str
    expires_at: str
    token: str = Field(
        description="Le secret du lien, en clair, UNE SEULE FOIS. Il n'existe "
                    "nulle part ailleurs — ni en base, ni dans les journaux.")


class JetonInvitation(Strict):
    """Ce qu'un invité présente pour rejoindre un bureau.

    LE REFUS EST LE MÊME dans les quatre cas — inconnue, expirée, révoquée,
    déjà consommée. Distinguer « ce lien n'existe pas » de « ce lien a
    expiré » apprendrait à qui essaie des liens au hasard quand il a visé
    juste.
    """

    token: str = Field(min_length=1, max_length=512)


class InvitationAcceptee(Strict):
    """Ce que l'invité obtient : une organisation, et son rôle dedans."""

    organization_id: str
    organization_name: str
    member_role: str


class Invitation(Strict):
    """Une invitation, telle que le panneau d'administration la montre.

    NI LE SECRET NI SON EMPREINTE. Le premier n'existe plus ; la seconde
    suffirait à reconnaître un lien intercepté ailleurs, et n'aide en rien
    l'écran.
    """

    invitation_id: str
    role: str
    label: str | None
    display_name: str | None
    professional_id: str | None
    created_at: str
    expires_at: str
    accepted_at: str | None
    revoked_at: str | None
    state: str = Field(
        description="pending | accepted | revoked | expired. Calculé par la "
                    "base, pas par l'écran : deux horloges donneraient deux "
                    "réponses.")


class ListeInvitations(Strict):
    invitations: list[Invitation]


class Membre(Strict):
    """Une adhésion, telle que le panneau d'administration la montre.

    ``is_active = false`` NE FAIT PAS DISPARAÎTRE LA LIGNE, et c'est voulu
    depuis 0009 : une note de dix ans doit rester lisible et nommer son
    signataire. Ce qui disparaît, c'est l'accès.
    """

    user_id: str
    role: str
    display_name: str | None
    professional_id: str | None
    is_active: bool
    created_at: str
    deactivated_at: str | None
    is_me: bool = Field(
        description="Vrai pour la ligne de l'appelant. L'écran s'en sert pour "
                    "ne pas proposer des gestes que la base refuse de toute "
                    "façon : on ne modifie pas sa propre adhésion.")


class ListeMembres(Strict):
    members: list[Membre]


class MembreModification(Strict):
    """Ce qu'un owner ou un admin change sur l'adhésion d'un collègue.

    LES CHAMPS ABSENTS NE SONT PAS TOUCHÉS. Envoyer ``role`` seul ne remet pas
    les noms à zéro : ``update_names`` doit être demandé explicitement, faute
    de quoi un formulaire partiel effacerait le nom sous lequel quelqu'un a
    signé.
    """

    role: str | None = Field(default=None)
    is_active: bool | None = Field(default=None)
    display_name: str | None = Field(default=None, max_length=200)
    professional_id: str | None = Field(default=None, max_length=100)
    update_names: bool = Field(
        default=False,
        description="Sans lui, ``display_name`` et ``professional_id`` sont "
                    "ignorés. Un formulaire partiel n'efface pas le nom sous "
                    "lequel quelqu'un a signé.")


class AdhesionModifiee(Strict):
    """La confirmation d'une modification, relue depuis la base."""

    user_id: str
    role: str
    is_active: bool
