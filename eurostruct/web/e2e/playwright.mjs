/**
 * Où trouver Playwright, sans l'imposer comme dépendance du paquet.
 *
 * L'interface n'a besoin de rien pour tourner: `next`, `react`, `react-dom`.
 * Ajouter Playwright aux dépendances de production ferait porter au produit
 * l'outillage de ses tests. On le CHERCHE donc, et on rend un refus lisible
 * quand il manque, plutôt qu'une trace d'import.
 */
const PISTES = [
  "playwright",
  "/opt/node22/lib/node_modules/playwright/index.mjs",
  "/usr/lib/node_modules/playwright/index.mjs",
];

export async function chargerChromium() {
  for (const piste of PISTES) {
    try {
      const mod = await import(piste);
      if (mod?.chromium) return mod.chromium;
    } catch {
      /* piste suivante */
    }
  }
  return null;
}

/**
 * Le binaire Chromium, CHOISI PARCE QU'IL EXISTE.
 *
 * Une première rédaction prenait un indice fixe dans la liste. Le filtre qui
 * retire la variable d'environnement vide décale les indices: sans
 * `EUROSTRUCT_CHROME`, l'indice visé désignait un chemin absent, et Playwright
 * échouait sur « executable doesn't exist » — une panne d'outillage qui se lit
 * comme un échec du produit.
 */
import { existsSync } from "node:fs";

export function cheminChromium() {
  const pistes = [
    process.env.EUROSTRUCT_CHROME || "",
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
    "/opt/pw-browsers/chromium/chrome-linux/chrome",
  ].filter(Boolean);
  return pistes.find((p) => existsSync(p)) || null;
}
