/**
 * Playwright et Chromium sont-ils la ?
 *
 * Le harnais pose une base, applique quatorze migrations, demarre trois
 * processus et construit l'interface. Decouvrir ensuite qu'aucun navigateur
 * n'est installe coute plusieurs minutes et rend le diagnostic illisible.
 * Cette sonde repond en quelques millisecondes, avant tout decor.
 */
import { chargerChromium, cheminChromium } from "./playwright.mjs";

const chromium = await chargerChromium();
const chrome = cheminChromium();
if (!chromium || !chrome) {
  console.error(
    `absent: ${!chromium ? "Playwright" : "un binaire Chromium"}.`,
  );
  process.exit(1);
}
console.log("ok");
