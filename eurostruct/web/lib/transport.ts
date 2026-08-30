/**
 * LE SEUL ENDROIT QUI JOINT UN `Authorization`.
 *
 * POURQUOI CENTRALISER
 * ---------------------
 * Un `fetch` par appelant, c'est une décision par appelant : joindre le jeton
 * ou non, le rafraîchir ou non, traiter le 401 ou non. La question se repose à
 * chaque nouvel écran, et il suffit d'une réponse distraite pour qu'un jeton
 * parte vers une route qui ne l'exige pas — ou qu'un 401 soit affiché comme
 * une panne du serveur.
 *
 * Ici la règle est écrite une fois :
 *
 *   * `appelPublic`  — n'attache JAMAIS de jeton. Le référentiel national est
 *     le même pour tout le monde ; le calcul EC2 est déterministe et ne
 *     consulte aucune donnée de locataire. Leur envoyer une identité serait
 *     répandre le jeton sans raison ;
 *   * `appelProtege` — attache le jeton, et **refuse de partir sans**. Une
 *     requête d'autorité sans identité n'est pas une requête à tenter : c'est
 *     un 401 qu'on peut éviter, et surtout la preuve que l'écran ne sait pas
 *     ce qu'il détient.
 *
 * LE JETON N'EST JAMAIS JOURNALISÉ
 * ---------------------------------
 * Ni en clair, ni tronqué, ni dans un message d'erreur. `SessionExpiree` et
 * `AppelRefuse` portent un motif lisible et rien d'autre. Un `console.log` de
 * débogage sur ce chemin serait une fuite dans chaque navigateur.
 *
 * LE JETON N'EST NI STOCKÉ NI CONSERVÉ ICI
 * -----------------------------------------
 * Ce module ne détient rien. Il le **demande** au porteur au moment de partir,
 * et l'oublie aussitôt : c'est ce qui rend impossible qu'une session fermée
 * laisse un jeton utilisable derrière elle dans un module transverse.
 */

export const BASE =
  process.env.NEXT_PUBLIC_EUROSTRUCT_API_URL ?? "http://127.0.0.1:8000";

/**
 * Ce que le transport exige d'une session pour partir.
 *
 * Une interface plutôt que le type `Session`: le transport n'a pas à savoir
 * ce qu'est une session, ni comment elle se renouvelle. Il demande un jeton
 * utilisable **maintenant** et reçoit `null` s'il n'y en a pas.
 */
export type PorteurDeJeton = {
  /**
   * Le jeton à joindre, renouvelé si nécessaire, ou `null`.
   *
   * `null` veut dire « pas de session utilisable » — jamais « envoie quand
   * même ». Le porteur a déjà fermé la session dans ce cas.
   */
  jetonUtilisable(): Promise<string | null>;
};

/** Aucune session utilisable: la requête n'est pas partie. */
export class SessionExpiree extends Error {
  constructor() {
    super("session expiree ou absente: reconnectez-vous.");
    this.name = "SessionExpiree";
  }
}

/** Le serveur a refusé. Le corps est celui qu'il a rendu, jamais inventé. */
export class AppelRefuse extends Error {
  readonly statut: number;
  readonly corps: unknown;

  constructor(statut: number, corps: unknown) {
    super(`l'API a refuse (${statut}).`);
    this.name = "AppelRefuse";
    this.statut = statut;
    this.corps = corps;
  }

  /** Le détail lisible du refus, tel que l'API l'a rendu. */
  get detail(): string {
    const c = this.corps;
    if (c && typeof c === "object" && "detail" in c) {
      const d = (c as { detail: unknown }).detail;
      if (typeof d === "string") return d;
      if (d && typeof d === "object" && "detail" in d) {
        return String((d as { detail: unknown }).detail);
      }
      return JSON.stringify(d);
    }
    return `reponse ${this.statut}`;
  }
}

/** L'API n'a pas répondu. Ce n'est pas un refus: c'est une absence. */
export class ApiInjoignable extends Error {
  constructor(cause: unknown) {
    super(`l'API n'a pas repondu (${String(cause)}). Voir ${BASE}.`);
    this.name = "ApiInjoignable";
  }
}

type Options = {
  methode?: "GET" | "POST";
  corps?: unknown;
};

async function _lire(reponse: Response): Promise<unknown> {
  return reponse.json().catch(() => null);
}

function _entetes(corps: unknown): Record<string, string> {
  const e: Record<string, string> = { Accept: "application/json" };
  if (corps !== undefined) e["Content-Type"] = "application/json";
  return e;
}

/**
 * Un appel qui ne porte AUCUNE identité, et qui n'en portera jamais.
 *
 * Rend `null` sur panne réseau plutôt que de lever : les écrans qui s'en
 * servent (bandeau du référentiel, plan de charge) doivent rester utilisables
 * sans lui. Un bandeau absent apprend moins qu'une page blanche, mais il
 * n'empêche pas de travailler.
 */
export async function appelPublic<T>(
  chemin: string,
  options: Options = {},
): Promise<T | null> {
  const { methode = "GET", corps } = options;
  try {
    const reponse = await fetch(`${BASE}${chemin}`, {
      method: methode,
      headers: _entetes(corps),
      body: corps === undefined ? undefined : JSON.stringify(corps),
    });
    if (!reponse.ok) return null;
    return (await _lire(reponse)) as T;
  } catch {
    return null;
  }
}

/**
 * Un appel d'autorité. Il ne part qu'avec une identité utilisable.
 *
 * @throws {SessionExpiree} aucun jeton utilisable — RIEN N'EST PARTI. C'est la
 *   propriété qui compte : un jeton périmé envoyé quand même est un 401 de
 *   plus dans les journaux, et surtout la preuve que l'écran ne sait pas ce
 *   qu'il détient.
 * @throws {AppelRefuse} le serveur a répondu autre chose qu'un succès. Un 401
 *   est traité comme les autres refus **du point de vue du transport** : c'est
 *   à l'appelant de fermer la session, parce que lui seul la détient.
 * @throws {ApiInjoignable} le réseau a échoué.
 */
export async function appelProtege<T>(
  chemin: string,
  porteur: PorteurDeJeton,
  options: Options = {},
): Promise<T | null> {
  const { methode = "POST", corps } = options;
  const jeton = await porteur.jetonUtilisable();
  if (!jeton) throw new SessionExpiree();

  let reponse: Response;
  try {
    reponse = await fetch(`${BASE}${chemin}`, {
      method: methode,
      headers: { ..._entetes(corps), Authorization: `Bearer ${jeton}` },
      body: corps === undefined ? undefined : JSON.stringify(corps),
    });
  } catch (cause) {
    throw new ApiInjoignable(cause);
  }

  if (!reponse.ok) throw new AppelRefuse(reponse.status, await _lire(reponse));
  // 204: un succès sans corps. `json()` léverait sur zéro octet.
  if (reponse.status === 204) return null;
  return (await _lire(reponse)) as T;
}
