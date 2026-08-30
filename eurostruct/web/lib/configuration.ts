/**
 * D'OÙ L'INTERFACE APPREND SON ADRESSE D'API ET SON ÉMETTEUR.
 *
 * LE PROBLÈME, ET IL EST PROPRE À NEXT
 * -------------------------------------
 * Une variable `NEXT_PUBLIC_*` est **inlinée dans le bundle au moment du
 * build**. Une image construite avec `NEXT_PUBLIC_EUROSTRUCT_API_URL=
 * http://127.0.0.1:8000` porte donc `http://127.0.0.1:8000` **en dur** dans
 * son JavaScript, pour toujours. La même image ne peut pas servir deux
 * environnements, et une clé anonyme Supabase de développement y reste
 * imprimée jusqu'à ce que quelqu'un s'en aperçoive.
 *
 * C'est exactement ce que l'exigence « aucune URL localhost ou clé Supabase
 * figée dans l'image » interdit.
 *
 * CE QU'ON FAIT À LA PLACE
 * -------------------------
 * Le layout — un composant **serveur** — lit `process.env` à chaque requête et
 * dépose les valeurs dans `window.__EUROSTRUCT__`. Le client les lit ici. La
 * configuration voyage donc avec la page, pas avec le bundle : la même image
 * sert le développement, la recette et la production, et un changement
 * d'adresse est un redémarrage, pas une reconstruction.
 *
 * CE QUI PASSE PAR LÀ, ET CE QUI N'Y PASSERA JAMAIS
 * --------------------------------------------------
 * Uniquement ce qui est **public par nature** : l'adresse de l'API et celle de
 * l'émetteur, plus la clé anonyme de GoTrue — qui désigne un projet et
 * n'autorise rien par elle-même. Aucun secret d'API, aucune DSN, aucune clé de
 * service : ce qui atterrit dans `window` est lisible par quiconque ouvre la
 * page, et cette phrase est le critère.
 *
 * LE REPLI SUR `process.env` RESTE, POUR `npm run dev`
 * ----------------------------------------------------
 * En développement local sans conteneur, les `NEXT_PUBLIC_*` continuent de
 * fonctionner. Elles ne sont plus le chemin de production, elles en sont la
 * commodité.
 *
 * IL N'Y A PLUS DE REPLI SUR `http://127.0.0.1:8000`
 * ---------------------------------------------------
 * Ce littéral était le dernier chemin par lequel une adresse pouvait entrer
 * sans que personne l'ait déclarée. Une image déployée sans
 * `EUROSTRUCT_API_URL` ne rendait pas d'erreur : elle appelait le port 8000 du
 * poste de **l'utilisateur**, ce qui échoue en silence chez lui, réussit chez
 * un développeur qui a une API locale, et ne se voit dans aucun journal
 * serveur. Un défaut de configuration doit se voir tout de suite.
 *
 * `configuration()` rend donc une chaîne vide, et `base()` REFUSE en la
 * nommant. `apiUrlConfiguree()` permet à l'écran d'afficher le diagnostic
 * plutôt que de laisser chaque appel lever.
 */

/** Ce que le serveur dépose dans la page. Rien d'autre n'y a sa place. */
export type ConfigurationPublique = {
  apiUrl: string;
  supabaseUrl: string;
  supabaseAnonKey: string;
};

declare global {
  interface Window {
    __EUROSTRUCT__?: Partial<ConfigurationPublique>;
  }
}

/** Le nom de la clé globale, partagé avec le layout qui l'écrit. */
export const CLE_GLOBALE = "__EUROSTRUCT__";

/**
 * Lit la configuration servie avec la page, sinon celle du build.
 *
 * Appelée à chaque usage plutôt que mémorisée dans une constante de module :
 * une constante serait évaluée à l'import, c'est-à-dire avant que le script
 * du layout ait posé la globale sur certaines trajectoires de rendu.
 */
export function configuration(): ConfigurationPublique {
  const servie = typeof window !== "undefined" ? window.__EUROSTRUCT__ : undefined;
  return {
    apiUrl:
      servie?.apiUrl ||
      process.env.NEXT_PUBLIC_EUROSTRUCT_API_URL ||
      "",
    supabaseUrl: servie?.supabaseUrl || process.env.NEXT_PUBLIC_SUPABASE_URL || "",
    supabaseAnonKey:
      servie?.supabaseAnonKey || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "",
  };
}

/** Le diagnostic exact quand l'adresse de l'API n'a pas été déclarée. */
export const DIAGNOSTIC_API_ABSENTE =
  "l'adresse de l'API n'est pas configuree. Le serveur qui sert cette page " +
  "doit porter EUROSTRUCT_API_URL dans son environnement (elle est lue a " +
  "chaque requete et deposee dans la page). En developpement local, " +
  "NEXT_PUBLIC_EUROSTRUCT_API_URL fait aussi l'affaire.";

/** Une configuration absente. Nommée, pour ne pas se confondre avec un réseau. */
export class ConfigurationAbsente extends Error {
  constructor(message: string = DIAGNOSTIC_API_ABSENTE) {
    super(message);
    this.name = "ConfigurationAbsente";
  }
}

/** `true` si l'adresse de l'API a été déclarée. Pour l'AFFICHER, pas pour lever. */
export function apiUrlConfiguree(): boolean {
  return configuration().apiUrl.trim().length > 0;
}
