/**
 * La session Supabase, côté navigateur.
 *
 * CE QUE CE MODULE EST, ET CE QU'IL N'EST PAS
 * --------------------------------------------
 * Il obtient un jeton, le renouvelle, et sait dire s'il est encore utilisable.
 * Il ne le **vérifie** pas : la vérification est côté API, dans
 * `AuthentificateurSupabase`, parce qu'une vérification faite dans le
 * navigateur ne prouve rien — le navigateur est l'endroit que l'attaquant
 * contrôle.
 *
 * Ce que le jeton porte n'est donc jamais lu ici pour décider quoi que ce
 * soit. On l'envoie, et c'est l'API qui dit oui ou non. La seule chose qu'on
 * lise est `expires_in`, rendu par l'émetteur **à côté** du jeton — et
 * uniquement pour savoir quand cesser de s'en servir.
 *
 * PAS DE SDK, ET C'EST DELIBERE
 * ------------------------------
 * `@supabase/supabase-js` apporte un client complet — base, stockage, temps
 * réel — dont cette tranche n'utilise rien, et qui **persiste la session dans
 * `localStorage` par défaut**. On appelle donc directement le point d'entrée
 * `token` de GoTrue, qui est une API HTTP stable et publique. Moins de
 * surface, rien à tenir à jour, et aucune persistance à désactiver.
 *
 * RIEN NE SORT DE LA MEMOIRE DE L'ONGLET
 * ---------------------------------------
 * Ni `localStorage`, ni `sessionStorage`, ni cookie, ni fragment d'URL. Un
 * jeton dans `localStorage` survit à la fermeture, se lit depuis n'importe
 * quel script de la page, et se retrouve dans les copies d'écran de débogage.
 * Le jeton de renouvellement est logé à la même enseigne : il vaut le jeton
 * d'accès, en plus durable.
 *
 * La contrepartie — se reconnecter en rouvrant l'onglet — est assumée.
 *
 * AUCUNE JOURNALISATION
 * ----------------------
 * Aucune fonction de ce module n'écrit un jeton, ni un fragment de jeton, dans
 * la console. Un `console.log` de débogage laissé là est une fuite dans chaque
 * navigateur qui ouvre l'application.
 */

import { configuration } from "@/lib/configuration";

//: L'ADRESSE DE L'EMETTEUR ET SA CLE ANONYME SONT LUES AU MOMENT DE L'APPEL.
//:
//: C'etaient deux constantes de module alimentees par `NEXT_PUBLIC_*`, donc
//: inlinees dans le bundle au build: la cle anonyme d'un projet Supabase
//: restait imprimee dans l'image. Voir `lib/configuration.ts`.

/**
 * Marge avant expiration. On cesse de se servir d'un jeton AVANT sa mort.
 *
 * Le trajet réseau, la vérification côté API et la tolérance d'horloge tiennent
 * là-dedans. Sans marge, un jeton parfaitement valide au moment du clic arrive
 * périmé, et l'utilisateur reçoit un 401 qu'il ne peut pas comprendre.
 */
export const MARGE_EXPIRATION_MS = 15_000;

/** La configuration est-elle présente ? Sinon l'écran n'affiche pas la connexion. */
export function authDisponible(): boolean {
  const { supabaseUrl, supabaseAnonKey } = configuration();
  return Boolean(supabaseUrl && supabaseAnonKey);
}

/**
 * Une session vivante. **Immuable** : on la remplace, on ne la modifie pas.
 *
 * `rafraichissement` peut manquer — un émetteur n'est pas tenu d'en délivrer.
 * Dans ce cas l'expiration ferme la session au lieu de la renouveler, et
 * l'écran demande une reconnexion propre. C'est un chemin normal, pas un cas
 * dégradé à rattraper.
 */
export type Session = {
  readonly jeton: string;
  /** Horodatage local (ms) au-delà duquel le jeton n'est plus utilisable. */
  readonly expire_a: number;
  readonly rafraichissement: string | null;
};

export type IssueConnexion =
  | { type: "session"; valeur: Session }
  | { type: "refus"; message: string };

/**
 * Le jeton est-il encore utilisable ? Marge comprise.
 *
 * REND UN BOOLEEN, PAS UN PREDICAT DE TYPE. Une rédaction antérieure
 * déclarait `s is Session` : TypeScript en déduisait qu'un résultat faux
 * exclut le type `Session`, et une session **expirée** — qui est bel et bien
 * une `Session` — devenait `never` dans la branche négative. Le compilateur
 * refusait alors de lire son jeton de renouvellement, c'est-à-dire exactement
 * le champ dont on a besoin pour la sauver.
 *
 * La validité est un fait sur l'horloge, pas sur la forme de l'objet. Le
 * système de types n'a rien à en dire.
 */
export function sessionValide(s: Session | null): boolean {
  return Boolean(s && s.expire_a - MARGE_EXPIRATION_MS > Date.now());
}

/** Combien de temps reste-t-il, marge comprise ? Négatif si c'est fini. */
export function resteMs(s: Session | null): number {
  return s ? s.expire_a - MARGE_EXPIRATION_MS - Date.now() : -1;
}

type ReponseJeton = {
  access_token?: unknown;
  refresh_token?: unknown;
  expires_in?: unknown;
};

/** Traduit la réponse de l'émetteur en session, ou refuse. */
function _session(corps: unknown): IssueConnexion {
  if (!corps || typeof corps !== "object") {
    return { type: "refus", message: "reponse illisible de l'emetteur." };
  }
  const c = corps as ReponseJeton;
  if (typeof c.access_token !== "string" || !c.access_token) {
    return { type: "refus", message: "reponse sans jeton d'acces." };
  }
  // UNE DUREE ABSENTE N'EST PAS UNE DUREE INFINIE. Faute de mieux on prend une
  // heure — la valeur par defaut de GoTrue — et la marge fera le reste.
  const duree = typeof c.expires_in === "number" && c.expires_in > 0
    ? c.expires_in
    : 3600;
  return {
    type: "session",
    valeur: {
      jeton: c.access_token,
      expire_a: Date.now() + duree * 1000,
      rafraichissement:
        typeof c.refresh_token === "string" && c.refresh_token
          ? c.refresh_token
          : null,
    },
  };
}

async function _demander(
  grant: string,
  charge: Record<string, string>,
): Promise<IssueConnexion> {
  if (!authDisponible()) {
    return {
      type: "refus",
      message:
        "authentification non configuree: l'adresse de l'emetteur et sa cle " +
        "anonyme ne sont pas servies avec la page. En conteneur, poser " +
        "EUROSTRUCT_SUPABASE_URL et EUROSTRUCT_SUPABASE_ANON_KEY sur le " +
        "processus web; en local, les variantes NEXT_PUBLIC_*. Voir " +
        "eurostruct/api/.env.example.",
    };
  }
  const { supabaseUrl, supabaseAnonKey } = configuration();
  let reponse: Response;
  try {
    reponse = await fetch(
      `${supabaseUrl}/auth/v1/token?grant_type=${encodeURIComponent(grant)}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json", apikey: supabaseAnonKey },
        body: JSON.stringify(charge),
      },
    );
  } catch {
    // NI LE LIBELLE DU NAVIGATEUR, NI L'URL DE L'EMETTEUR. Le premier
    // (« TypeError: Failed to fetch ») n'apprend rien; la seconde est une
    // adresse de projet Supabase, et l'ecran de connexion n'a pas a l'afficher
    // a quelqu'un qui n'est pas encore authentifie.
    return {
      type: "refus",
      message: "Le service d'authentification n'a pas repondu. Verifiez votre "
        + "connexion reseau, puis reessayez.",
    };
  }

  const corps: unknown = await reponse.json().catch(() => null);
  if (!reponse.ok) {
    // ON NE RECOPIE PAS LE MESSAGE DE SUPABASE TEL QUEL. Il distingue parfois
    // « utilisateur inconnu » de « mot de passe faux », ce qui donne un
    // oracle d'enumeration de comptes.
    return { type: "refus", message: "identifiants refuses." };
  }
  return _session(corps);
}

/**
 * Échange un couple courriel / mot de passe contre une session.
 *
 * Rend un refus explicite plutôt que de lever : un identifiant refusé n'est
 * pas une exception, c'est une réponse que l'utilisateur doit lire.
 */
export function ouvrirSession(
  courriel: string,
  motDePasse: string,
): Promise<IssueConnexion> {
  return _demander("password", { email: courriel, password: motDePasse });
}

/**
 * Renouvelle une session à partir de son jeton de renouvellement.
 *
 * REND UNE SESSION NEUVE, NE MODIFIE PAS L'ANCIENNE. GoTrue fait tourner le
 * jeton de renouvellement à chaque usage : conserver l'ancien à côté du
 * nouveau ferait échouer le renouvellement suivant.
 *
 * Un refus ici n'est pas rattrapable côté client. Le jeton de renouvellement
 * a été révoqué, ou il a déjà servi : la seule suite correcte est de fermer la
 * session et de demander une reconnexion.
 */
export function renouvelerSession(s: Session): Promise<IssueConnexion> {
  if (!s.rafraichissement) {
    return Promise.resolve({
      type: "refus",
      message: "aucun jeton de renouvellement: la session doit etre rouverte.",
    });
  }
  return _demander("refresh_token", { refresh_token: s.rafraichissement });
}
