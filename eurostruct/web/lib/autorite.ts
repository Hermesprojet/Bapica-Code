/**
 * Les trois primitives du quatre-yeux, vues du navigateur.
 *
 * AUCUNE FORME N'EST REDÉFINIE ICI
 * ---------------------------------
 * `AuthorityDecisionRequest`, `AuthorityDecisionCreated` et
 * `AuthorityDecisionConsumed` viennent du contrat **généré** depuis les
 * modèles Pydantic. Les recopier créerait une seconde définition, qui
 * dériverait au premier champ renommé — et ici le champ en question décide qui
 * peut confirmer une valeur nationale.
 *
 * AUCUN CORPS NE NOMME UN ACTEUR
 * -------------------------------
 * Ni `actor_id`, ni proposant, ni approbateur : l'identité sort du jeton
 * porteur, et de lui seul. Ce n'est pas une convention de politesse — le
 * contrat côté serveur est `extra="forbid"`, si bien qu'un champ ajouté ici
 * ferait un 422 plutôt qu'une usurpation. La propriété tient donc même si
 * quelqu'un essaie.
 *
 * `approuver` ET `consommer` NE PRENNENT QU'UN IDENTIFIANT. Qui approuve est
 * la question du jeton ; PostgreSQL refuse ensuite que ce soit le proposant,
 * par contrainte de table et non par vérification applicative.
 */
import type {
  AuthorityDecisionConsumed,
  AuthorityDecisionCreated,
  AuthorityDecisionRequest,
} from "@contracts/generated/engine";
import { appelProtege, type PorteurDeJeton } from "@/lib/transport";

export type {
  AuthorityDecisionConsumed,
  AuthorityDecisionCreated,
  AuthorityDecisionRequest,
};

/** Propose une décision. Le proposant est le porteur du jeton. */
export async function proposerDecision(
  porteur: PorteurDeJeton,
  corps: AuthorityDecisionRequest,
): Promise<AuthorityDecisionCreated> {
  const cree = await appelProtege<AuthorityDecisionCreated>(
    "/v1/authority/decisions", porteur, { methode: "POST", corps },
  );
  if (!cree?.decision_id) {
    // 201 SANS IDENTIFIANT N'EST PAS UNE CREATION. On refuse plutôt que
    // d'afficher un dossier vide dont personne ne pourra rien faire.
    throw new Error("la proposition n'a rendu aucun identifiant de decision.");
  }
  return cree;
}

/** Approuve. L'approbateur est le porteur du jeton, et lui seul. */
export async function approuverDecision(
  porteur: PorteurDeJeton,
  decisionId: string,
): Promise<void> {
  await appelProtege<null>(
    `/v1/authority/decisions/${encodeURIComponent(decisionId)}/approval`,
    porteur, { methode: "POST" },
  );
}

/** Consomme une décision approuvée. Une seule fois : le rejeu est refusé. */
export async function consommerDecision(
  porteur: PorteurDeJeton,
  decisionId: string,
): Promise<AuthorityDecisionConsumed> {
  const consommee = await appelProtege<AuthorityDecisionConsumed>(
    `/v1/authority/decisions/${encodeURIComponent(decisionId)}/consumption`,
    porteur, { methode: "POST" },
  );
  if (!consommee) {
    throw new Error("la consommation n'a rendu aucun corps.");
  }
  return consommee;
}
