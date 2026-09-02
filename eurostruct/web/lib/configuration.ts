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
 * passe les valeurs en **props React** à `FournisseurConfiguration`. La
 * configuration voyage donc avec la page, pas avec le bundle : la même image
 * sert le développement, la recette et la production, et un changement
 * d'adresse est un redémarrage, pas une reconstruction.
 *
 * CE QUI A CHANGÉ LE 02/09, ET POURQUOI
 * --------------------------------------
 * Ces valeurs étaient déposées dans `window.__EUROSTRUCT__` par un
 * `<script dangerouslySetInnerHTML>` placé dans `<head>`. React 19 **hisse**
 * les balises `<script>` hors de l'endroit où on les écrit : le HTML rendu par
 * le serveur et l'arbre reconstruit par le client ne correspondaient plus, et
 * chaque chargement de page levait l'erreur React #418 — « hydration failed…
 * this tree will be regenerated on the client ». Mesuré sur une construction
 * de production réelle (`next build` puis `next start`), et confirmé par
 * neutralisation : le `<head>` retiré, l'erreur disparaît.
 *
 * Ce n'était pas qu'un avertissement. Une hydratation qui échoue fait jeter
 * l'arbre rendu par le serveur et le reconstruire entièrement côté client : le
 * premier rendu utile arrive plus tard, et l'écran clignote sur les machines
 * lentes.
 *
 * LA TRANSMISSION EST DÉSORMAIS CELLE DE REACT
 * ----------------------------------------------
 * Des props sérialisées par React vers un composant client. Trois conséquences
 * qui sont exactement ce qu'on cherchait :
 *
 *   * **plus aucune balise à hisser**, donc plus de divergence d'hydratation ;
 *   * **l'échappement est celui de React**, qui sérialise ses props ; il n'y a
 *     plus de JavaScript composé à la main dans lequel un `</script>` pourrait
 *     terminer la balise. La garde manuelle disparaît avec le risque qu'elle
 *     couvrait, pas avant lui ;
 *   * **plus de dépendance temporelle**. `window.__EUROSTRUCT__` n'existait
 *     qu'après l'exécution du script du `<head>` : tout module qui lisait la
 *     configuration à l'import voyait une globale absente. La valeur est
 *     maintenant posée pendant le rendu du fournisseur, avant tout enfant.
 *
 * CE QUI PASSE PAR LÀ, ET CE QUI N'Y PASSERA JAMAIS
 * --------------------------------------------------
 * Uniquement ce qui est **public par nature** : l'adresse de l'API et celle de
 * l'émetteur, plus la clé anonyme de GoTrue — qui désigne un projet et
 * n'autorise rien par elle-même. Aucun secret d'API, aucune DSN, aucune clé de
 * service : ce qui atterrit dans la page est lisible par quiconque l'ouvre, et
 * cette phrase est le critère.
 *
 * LE REPLI SUR `NEXT_PUBLIC_*` RESTE, POUR `npm run dev`
 * -------------------------------------------------------
 * Il ne sert que lorsqu'aucun fournisseur n'a posé de valeur — c'est-à-dire
 * hors de l'application. Il n'est plus le chemin de production, il en est la
 * commodité, et `e2e/image_sans_configuration.mjs` vérifie qu'il ne fuit rien.
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

/** Ce que le serveur passe à la page. Rien d'autre n'y a sa place. */
export type ConfigurationPublique = {
  apiUrl: string;
  supabaseUrl: string;
  supabaseAnonKey: string;
};

/**
 * La configuration telle que le SERVEUR la lit, à chaque requête.
 *
 * ELLE N'EST APPELÉE QUE CÔTÉ SERVEUR — par le layout, et par
 * `configuration()` pendant le rendu serveur d'un composant client. Les deux
 * chemins passent donc par la MÊME fonction : le serveur et le premier rendu
 * client ne peuvent pas diverger, puisqu'il n'y a qu'une source.
 *
 * Les variables sans préfixe d'abord — ce sont celles du runtime, les seules
 * qu'une image puisse recevoir après sa construction.
 */
export function configurationDuServeur(): ConfigurationPublique {
  return {
    apiUrl:
      process.env.EUROSTRUCT_API_URL
      || process.env.NEXT_PUBLIC_EUROSTRUCT_API_URL
      || "",
    supabaseUrl:
      process.env.EUROSTRUCT_SUPABASE_URL
      || process.env.NEXT_PUBLIC_SUPABASE_URL
      || "",
    supabaseAnonKey:
      process.env.EUROSTRUCT_SUPABASE_ANON_KEY
      || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
      || "",
  };
}

/**
 * La valeur posée par le fournisseur, CÔTÉ NAVIGATEUR UNIQUEMENT.
 *
 * ELLE N'EST JAMAIS ÉCRITE SUR LE SERVEUR, et c'est délibéré : un module est
 * partagé par toutes les requêtes d'un même processus, si bien qu'y écrire
 * pendant un rendu ferait dépendre une réponse de celle d'à côté. Sur le
 * serveur, `configuration()` relit donc `process.env` — la même source que
 * celle du layout, donc la même valeur.
 */
let _posee: ConfigurationPublique | null = null;

/**
 * Le fournisseur dépose ici ce que le serveur lui a passé.
 *
 * IDEMPOTENTE PAR NATURE : le fournisseur repose la même valeur à chaque
 * rendu. Elle est appelée PENDANT le rendu, pas dans un effet — un effet
 * s'exécute après les enfants, et un enfant qui appellerait `base()` au
 * montage lirait alors une configuration absente.
 */
export function poserConfiguration(valeur: ConfigurationPublique): void {
  if (typeof window === "undefined") return;
  _posee = valeur;
}

/**
 * Lit la configuration en vigueur.
 *
 * Appelée à chaque usage plutôt que mémorisée dans une constante de module :
 * une constante serait évaluée à l'import, avant que le fournisseur ait rendu.
 */
export function configuration(): ConfigurationPublique {
  if (typeof window === "undefined") return configurationDuServeur();
  if (_posee) return _posee;
  //: HORS DE L'APPLICATION — un test unitaire, un composant monté seul. Le
  //: repli `NEXT_PUBLIC_*` est inliné au build: il ne sert pas la production.
  return {
    apiUrl: process.env.NEXT_PUBLIC_EUROSTRUCT_API_URL || "",
    supabaseUrl: process.env.NEXT_PUBLIC_SUPABASE_URL || "",
    supabaseAnonKey: process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "",
  };
}

/** Le diagnostic exact quand l'adresse de l'API n'a pas été déclarée. */
export const DIAGNOSTIC_API_ABSENTE =
  "l'adresse de l'API n'est pas configuree. Le serveur qui sert cette page " +
  "doit porter EUROSTRUCT_API_URL dans son environnement (elle est lue a " +
  "chaque requete et passee a la page). En developpement local, " +
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
