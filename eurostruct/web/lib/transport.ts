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
import { ConfigurationAbsente, configuration } from "@/lib/configuration";

/**
 * L'adresse de l'API, lue **au moment de l'appel**.
 *
 * C'ETAIT UNE CONSTANTE DE MODULE ALIMENTEE PAR `NEXT_PUBLIC_*`, donc inlinee
 * dans le bundle au build: l'image portait `http://127.0.0.1:8000` en dur et
 * ne pouvait servir qu'un seul environnement. Voir `lib/configuration.ts`.
 *
 * ELLE REFUSE PLUTOT QUE DE REPLIER SUR `http://127.0.0.1:8000`. Ce repli
 * faisait appeler le port 8000 du poste de l'UTILISATEUR: cela echoue chez
 * lui, reussit chez un developpeur qui a une API locale, et n'apparait dans
 * aucun journal serveur. Une configuration absente doit se voir tout de suite,
 * et se nommer.
 */
export function base(): string {
  const adresse = configuration().apiUrl.trim();
  if (!adresse) throw new ConfigurationAbsente();
  return adresse;
}

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
  /**
   * Force un renouvellement APRES un 401, même si le jeton local semblait bon.
   *
   * C'est le cas que `jetonUtilisable()` ne peut pas voir: l'horloge locale
   * dit « encore valide », et le serveur dit non. Seul le serveur a raison —
   * il connaît les révocations, et notre horloge peut dériver.
   */
  renouvellementForce(): Promise<string | null>;
  /**
   * Ferme la session: le serveur a refusé un jeton que nous croyions bon, et
   * le renouvellement n'a rien donné. Garder une session dont chaque appel
   * fait 401 n'est pas une session, c'est un écran qui ment.
   */
  abandonner(): void;
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
      if (Array.isArray(d)) {
        // UN 422 DE VALIDATION FastAPI: `detail` est une LISTE d'objets
        // `{loc, msg, type}`. `JSON.stringify` en faisait un pave de JSON a
        // l'ecran — le champ fautif y etait, noye. On nomme le champ et on
        // reprend le message du serveur, sans en composer un autre.
        const lignes = d.map((x) => {
          const o = (x ?? {}) as { loc?: unknown; msg?: unknown };
          const ou = Array.isArray(o.loc)
            ? o.loc.filter((p) => p !== "body").join(".") : "";
          const quoi = typeof o.msg === "string" ? o.msg : "";
          return ou && quoi ? `${ou} : ${quoi}` : (quoi || ou);
        }).filter((s) => s.length > 0);
        if (lignes.length) return lignes.join(" ; ");
      }
      if (d && typeof d === "object" && "detail" in d) {
        return String((d as { detail: unknown }).detail);
      }
      // LE MOTIF DU SERVEUR SOUS UNE FORME QU'ON N'ATTENDAIT PAS. On le rend
      // quand meme: le remplacer par « sans motif lisible » effacerait la
      // seule chose que le serveur ait dite.
      return JSON.stringify(d);
    }
    return `reponse ${this.statut}`;
  }
}

/** L'API n'a pas répondu. Ce n'est pas un refus: c'est une absence. */
export class ApiInjoignable extends Error {
  constructor(cause: unknown) {
    // `base()` PEUT LEVER, et un constructeur d'erreur qui lève remplace le
    // diagnostic par une seconde panne — celle-là sans message utile. On lit
    // donc l'adresse sans passer par la garde, et on dit « non configuree »
    // quand il n'y en a pas.
    const adresse = configuration().apiUrl.trim() || "(adresse non configuree)";
    // LE LIBELLE DU NAVIGATEUR NE VA PAS A L'ECRAN. `String(cause)` donnait
    // « TypeError: Failed to fetch » — exact, et inutilisable par un ingenieur
    // en bureau d'etudes. La cause reste attachee a l'erreur (`{ cause }`),
    // donc lisible dans la console par qui debogue, sans etre affichee.
    super(`Le serveur EUROSTRUCT n'a pas repondu a l'adresse ${adresse}. `
          + "Verifiez qu'il est demarre et joignable depuis ce poste, puis "
          + "reessayez.",
          { cause });
    this.name = "ApiInjoignable";
  }
}

type Options = {
  /**
   * `PATCH` ET `DELETE` SONT ARRIVÉS AVEC L'ADMINISTRATION DES MEMBRES.
   *
   * Modifier une adhésion n'est pas la remplacer — un `PUT` obligerait
   * l'écran à renvoyer les champs qu'il ne touche pas, c'est-à-dire à
   * réaffirmer le nom sous lequel quelqu'un a signé à chaque changement de
   * rôle. Révoquer une invitation n'est pas non plus une création.
   *
   * AUCUN DES DEUX N'EST IDEMPOTENT AU SENS DE CE TRANSPORT: rejouer une
   * révocation après un 401 la refuserait une seconde fois, et rejouer un
   * changement de rôle appliquerait deux fois une décision prise une.
   */
  methode?: "GET" | "POST" | "PATCH" | "DELETE";
  corps?: unknown;
  /**
   * L'appel peut-il être REPETE sans effet supplémentaire ?
   *
   * FAUX PAR DEFAUT, ET CE DEFAUT EST LE POINT. Proposer, approuver et
   * consommer sont des actes: les rejouer après un 401 créerait une seconde
   * décision, ou consommerait deux fois. Un 401 sur un acte ferme donc la
   * session et remonte le refus — c'est à la personne de recommencer, en
   * sachant ce qu'elle refait.
   *
   * Seules les lectures le portent.
   */
  idempotent?: boolean;
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
    const reponse = await fetch(`${base()}${chemin}`, {
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
  const { methode = "POST", corps, idempotent = false } = options;
  const jeton = await porteur.jetonUtilisable();
  if (!jeton) throw new SessionExpiree();

  // HORS DU `try`, ET C'EST LE POINT: une `ConfigurationAbsente` prise ici
  // ressortirait en `ApiInjoignable`, c'est-a-dire « le reseau a echoue »
  // pour un serveur qui n'a jamais ete appele.
  const adresse = base();

  const envoyer = async (avec: string): Promise<Response> => {
    try {
      return await fetch(`${adresse}${chemin}`, {
        method: methode,
        headers: { ..._entetes(corps), Authorization: `Bearer ${avec}` },
        body: corps === undefined ? undefined : JSON.stringify(corps),
      });
    } catch (cause) {
      throw new ApiInjoignable(cause);
    }
  };

  let reponse = await envoyer(jeton);

  // UN 401 SUR UNE SESSION QUE NOUS CROYIONS BONNE.
  //
  // Notre horloge disait « encore valide »; le serveur dit non, et c'est lui
  // qui a raison — il connaît les révocations, notre horloge peut dériver.
  //
  // AU PLUS UN RENOUVELLEMENT FORCE, ET AU PLUS UNE REPETITION. Sans borne,
  // un serveur qui refuse toujours produit une boucle de renouvellements: on
  // martèle l'émetteur, la personne voit un écran figé, et rien dans les
  // journaux ne dit pourquoi. Si le second appel est encore 401, la session
  // est FERMEE: elle ne sert plus à rien, et la garder ouverte ferait croire
  // le contraire.
  //
  // SEULEMENT POUR UN APPEL IDEMPOTENT. Rejouer une proposition créerait une
  // seconde décision; rejouer une consommation la consommerait deux fois.
  if (reponse.status === 401) {
    if (!idempotent) {
      porteur.abandonner();
      throw new AppelRefuse(401, await _lire(reponse));
    }
    const neuf = await porteur.renouvellementForce();
    if (!neuf) throw new AppelRefuse(401, await _lire(reponse));
    reponse = await envoyer(neuf);
    if (reponse.status === 401) {
      porteur.abandonner();
      throw new AppelRefuse(401, await _lire(reponse));
    }
  }

  if (!reponse.ok) throw new AppelRefuse(reponse.status, await _lire(reponse));
  // 204: un succès sans corps. `json()` léverait sur zéro octet.
  if (reponse.status === 204) return null;
  return (await _lire(reponse)) as T;
}
