/**
 * L'entrée dans l'application, vue du navigateur.
 *
 * CE QUE CET ÉCRAN REMPLACE
 * --------------------------
 * Rien. Il n'y avait rien. Un compte tout neuf, parfaitement authentifié,
 * arrivait devant une liste de projets vide — pas une erreur, pas une
 * explication, un écran nu — et aucun bouton ne permettait d'en sortir. La
 * seule façon d'exister dans l'application était un `insert` fait à la main
 * par le propriétaire de la base.
 *
 * AUCUNE FORME N'EST REDÉFINIE ICI
 * ---------------------------------
 * `Organisation`, `InvitationEmise`, `Membre` et les autres viennent du
 * contrat **généré** depuis les modèles Pydantic. L'une d'elles porte, une
 * seule fois, le secret d'une invitation : la recopier à la main quelque part
 * serait exactement la façon de le faire fuir dans un champ qu'on croyait
 * anodin.
 *
 * LE SECRET N'EST NI STOCKÉ NI RÉAFFICHABLE
 * -------------------------------------------
 * Il arrive dans la réponse de `emettreInvitation`, et nulle part ailleurs. Le
 * navigateur ne l'écrit pas en `localStorage` : un secret rangé dans le
 * navigateur d'une personne survivrait à sa session, et c'est exactement ce
 * qu'un lien à usage unique ne doit pas faire.
 *
 * AUCUN RÔLE N'EST JUGÉ ICI
 * --------------------------
 * « Un admin ne peut pas inviter un owner », « on ne modifie pas sa propre
 * adhésion », « le dernier propriétaire actif ne disparaît pas » : les trois
 * règles sont dans PostgreSQL. L'écran s'en sert pour **montrer ou
 * expliquer** ; la frontière n'est pas ici.
 */
import type {
  AdhesionModifiee,
  Invitation,
  InvitationAcceptee,
  InvitationCreation,
  InvitationEmise,
  ListeInvitations,
  ListeMembres,
  Membre,
  MembreModification,
  Organisation,
  OrganisationCreation,
} from "@contracts/generated/engine";
import { appelProtege, type PorteurDeJeton } from "@/lib/transport";

export type {
  AdhesionModifiee,
  Invitation,
  InvitationAcceptee,
  InvitationCreation,
  InvitationEmise,
  ListeInvitations,
  ListeMembres,
  Membre,
  MembreModification,
  Organisation,
  OrganisationCreation,
};

/** Les cinq rôles d'organisation, dans l'ordre décroissant de pouvoir. */
export const ROLES = [
  "owner",
  "admin",
  "engineer",
  "validating_engineer",
  "viewer",
] as const;

/** Ce que chaque rôle fait, en une phrase, pour l'écran d'invitation. */
export const ROLE_EXPLIQUE: Record<string, string> = {
  owner: "administre le bureau, et ne peut pas disparaître s'il est le dernier",
  admin: "administre les membres, sans pouvoir créer de propriétaire",
  engineer: "calcule et rédige les livrables",
  validating_engineer: "atteste et émet ; il ne rédige pas ce qu'il atteste",
  viewer: "lit, et rien d'autre",
};

/** Les deux rôles qui administrent. L'écran s'en sert pour MONTRER. */
export function peutAdministrer(organisation: Organisation | null): boolean {
  return organisation?.member_role === "owner"
    || organisation?.member_role === "admin";
}

/**
 * Les bureaux de l'appelant, et son rôle dans chacun.
 *
 * IDEMPOTENT: c'est une lecture. Elle peut être rejouée après un 401 sans rien
 * créer.
 *
 * SÉPARÉE DE `listerProjets` DÉLIBÉRÉMENT. « Zéro projet et zéro bureau » et
 * « zéro projet et un bureau » sont deux écrans différents — « créez votre
 * bureau » d'un côté, « créez votre premier projet » de l'autre — et une seule
 * liste vide ne permet pas de les distinguer.
 */
export async function listerOrganisations(
  porteur: PorteurDeJeton,
): Promise<Organisation[]> {
  const liste = await appelProtege<Organisation[]>(
    "/v1/organizations", porteur, { methode: "GET", idempotent: true },
  );
  return liste ?? [];
}

/**
 * Fonde un bureau et rend **le bureau**, pas son identifiant.
 *
 * PAS IDEMPOTENT AU SENS DU TRANSPORT — c'est une création — mais la primitive
 * l'est: un second appel avec le même nom rend le bureau déjà créé. Un
 * double-clic ne fonde donc pas deux bureaux, et l'écran n'a pas à s'en
 * préoccuper.
 */
export async function fonderOrganisation(
  porteur: PorteurDeJeton,
  brouillon: OrganisationCreation,
): Promise<Organisation> {
  const cree = await appelProtege<Organisation>(
    "/v1/organizations", porteur, { methode: "POST", corps: brouillon },
  );
  if (!cree?.organization_id) {
    // 201 SANS IDENTIFIANT N'EST PAS UNE FONDATION. On refuse plutôt que
    // d'afficher un bureau vide dont personne ne pourra rien faire.
    throw new Error("la fondation n'a rendu aucun bureau.");
  }
  return cree;
}

/**
 * Émet un lien d'invitation. **La réponse porte le secret, une seule fois.**
 *
 * Il n'existe nulle part ailleurs — ni en base, ni dans les journaux, ni dans
 * un rechargement de l'écran. L'appelant doit le montrer maintenant.
 */
export async function emettreInvitation(
  porteur: PorteurDeJeton,
  organizationId: string,
  brouillon: InvitationCreation,
): Promise<InvitationEmise> {
  const emise = await appelProtege<InvitationEmise>(
    `/v1/organizations/${encodeURIComponent(organizationId)}/invitations`,
    porteur, { methode: "POST", corps: brouillon },
  );
  if (!emise?.token) {
    throw new Error("l'emission n'a rendu aucun lien.");
  }
  return emise;
}

/** Les invitations du bureau — sans le secret ni son empreinte. */
export async function listerInvitations(
  porteur: PorteurDeJeton,
  organizationId: string,
): Promise<Invitation[]> {
  const liste = await appelProtege<ListeInvitations>(
    `/v1/organizations/${encodeURIComponent(organizationId)}/invitations`,
    porteur, { methode: "GET", idempotent: true },
  );
  return liste?.invitations ?? [];
}

/** Révoque un lien encore en attente. Un lien déjà consommé ne se révoque pas. */
export async function revoquerInvitation(
  porteur: PorteurDeJeton,
  organizationId: string,
  invitationId: string,
): Promise<void> {
  await appelProtege<null>(
    `/v1/organizations/${encodeURIComponent(organizationId)}`
    + `/invitations/${encodeURIComponent(invitationId)}`,
    porteur, { methode: "DELETE" },
  );
}

/**
 * Rejoint un bureau avec un lien.
 *
 * LE SECRET NE PASSE PAS PAR L'URL. Une adresse voyage dans l'historique du
 * navigateur, dans les journaux d'un proxy et dans l'en-tête `Referer` de la
 * page suivante ; le corps d'un POST, non.
 */
export async function accepterInvitation(
  porteur: PorteurDeJeton,
  token: string,
): Promise<InvitationAcceptee> {
  const acceptee = await appelProtege<InvitationAcceptee>(
    "/v1/invitations/accept", porteur, { methode: "POST", corps: { token } },
  );
  if (!acceptee?.organization_id) {
    throw new Error("l'acceptation n'a rendu aucun bureau.");
  }
  return acceptee;
}

/** L'équipe du bureau, adhésions désactivées comprises. */
export async function listerMembres(
  porteur: PorteurDeJeton,
  organizationId: string,
): Promise<Membre[]> {
  const liste = await appelProtege<ListeMembres>(
    `/v1/organizations/${encodeURIComponent(organizationId)}/members`,
    porteur, { methode: "GET", idempotent: true },
  );
  return liste?.members ?? [];
}

/**
 * Change le rôle, l'état ou le nom professionnel d'un collègue.
 *
 * `update_names` DOIT ÊTRE DEMANDÉ. Sans lui, `display_name` et
 * `professional_id` sont ignorés côté serveur : un formulaire partiel
 * n'efface pas le nom sous lequel quelqu'un a signé.
 */
export async function modifierMembre(
  porteur: PorteurDeJeton,
  organizationId: string,
  userId: string,
  modification: MembreModification,
): Promise<AdhesionModifiee> {
  const modifiee = await appelProtege<AdhesionModifiee>(
    `/v1/organizations/${encodeURIComponent(organizationId)}`
    + `/members/${encodeURIComponent(userId)}`,
    porteur, { methode: "PATCH", corps: modification },
  );
  if (!modifiee?.user_id) {
    throw new Error("la modification n'a rendu aucune adhesion.");
  }
  return modifiee;
}
