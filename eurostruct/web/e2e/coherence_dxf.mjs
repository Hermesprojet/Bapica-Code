/**
 * LE DESSIN DOIT ÊTRE CELUI DU CALCUL QUI L'A PRÉCÉDÉ.
 *
 * CE QUE CE PARCOURS A TROUVÉ, MESURÉ LE 30/08
 * ---------------------------------------------
 * `Ferraillage` envoyait `b: 300, h: 500` **en dur** à l'endpoint DXF, quelle
 * que soit la section saisie. Un ingénieur qui calculait une poutre 250 × 600
 * téléchargeait un plan coté 300 × 500 — sans aucun message, avec la mention
 * légale dessus, et sous le nom `P1.dxf` quel que soit le repère saisi.
 *
 * Rien dans la suite ne pouvait le voir : les cas de l'API vérifient que
 * l'endpoint rend un fichier conforme à la requête qu'on lui donne, et ils ont
 * raison. Le défaut était dans ce que l'interface **envoie**, pas dans ce que
 * l'API **rend**. Seul un parcours navigateur traverse les deux.
 *
 * ON LIT LE FICHIER TÉLÉCHARGÉ, PAS LA RÉPONSE HTTP
 * --------------------------------------------------
 * La page consomme la réponse en `blob()` pour déclencher l'enregistrement ;
 * `response.text()` rend alors **zéro octet**. Une rédaction antérieure lisait
 * ce corps vide, le comparait à `null` — et `"" !== null` est vrai — puis
 * concluait au vert avec le défaut sous les yeux. On passe donc par
 * l'événement `download` et on lit le fichier sur le disque : c'est celui que
 * le dessinateur ouvrira.
 */
import { readFileSync } from "node:fs";
import { chargerChromium, cheminChromium } from "./playwright.mjs";

const WEB = process.env.EUROSTRUCT_WEB || "http://localhost:3000";

const B = "250";
const H = "600";
const D = "550";
const REPERE = "P7";

/** Les cotes annotées dans le DXF, telles qu'ezdxf les écrit (MTEXT). */
function cotesDu(dxf) {
  const cotes = new Set();
  for (const m of dxf.matchAll(/AcDbMText\n(?:.*\n)*? {2}1\n(.*)/g)) {
    const v = m[1].trim();
    if (/^\d+([.,]\d+)?$/.test(v)) cotes.add(v);
  }
  return cotes;
}

const echecs = [];
const exige = (ok, message) => {
  if (!ok) echecs.push(message);
};

const chromium = await chargerChromium();
const chrome = cheminChromium();
if (!chromium || !chrome) {
  console.log(
    `NON EXECUTE: ${!chromium ? "Playwright introuvable" : "aucun binaire Chromium"}.`,
  );
  process.exit(4);
}

const nav = await chromium.launch({ executablePath: chrome, args: ["--no-sandbox"] });
const ctx = await nav.newContext({ acceptDownloads: true });
const page = await ctx.newPage();

let envoye = null;
page.on("request", (r) => {
  if (r.url().includes("beam-section.dxf")) envoye = r.postData();
});

try {
  await page.goto(WEB, { waitUntil: "networkidle" });

  // --- une section qui n'est PAS celle des valeurs de démonstration --------
  await page.fill("#b", B);
  await page.fill("#h", H);
  await page.fill("#d", D);
  await page.fill("#element", REPERE);
  await page.uncheck("#strict"); // sinon le calcul refuse: aucun NDP confirmé
  await page.click("button[type=submit]");
  await page.waitForSelector("#nb", { timeout: 20000 });

  // Le vocabulaire de l'ecran: « NON SIGNABLE », jamais « signable ».
  const nonSignable = await page.locator(".mention-non-signable").count();
  exige(nonSignable > 0, "le calcul exploratoire ne porte pas la mention");

  // --- D'ABORD: un ferraillage INSUFFISANT ne doit rien produire ----------
  //
  // Trois HA16 (603 mm²) ne verifient pas cette section. Le moteur le dit, et
  // AUCUN fichier ne part: un plan qui echoue a sa propre verification a l'air
  // d'un plan valide entre les mains de celui qui l'ouvre.
  await page.fill("#nb", "3");
  await page.fill("#diam", "16");
  let telecharge = false;
  const espion = page.waitForEvent("download", { timeout: 6000 })
    .then(() => { telecharge = true; })
    .catch(() => {});
  await page.click("button:has-text('DXF')");
  await espion;
  exige(!telecharge, "un ferraillage insuffisant a quand meme produit un DXF");
  const refus = await page
    .locator("text=/ne verifie pas la section/")
    .count()
    .catch(() => 0);
  exige(refus > 0, "le refus de ferraillage n'est pas affiche a l'ecran");

  // --- ENSUITE: un ferraillage suffisant, et le plan qui va avec ----------
  await page.fill("#nb", "4");
  const attente = page.waitForEvent("download", { timeout: 20000 });
  await page.click("button:has-text('DXF')");
  const telechargement = await attente;
  const dxf = readFileSync(await telechargement.path(), "utf8");

  exige(
    telechargement.suggestedFilename() === `${REPERE}.dxf`,
    `le fichier s'appelle ${telechargement.suggestedFilename()}, ` +
      `attendu ${REPERE}.dxf`,
  );

  // La charge utile: la preuve directe de ce que l'écran a demandé.
  exige(envoye !== null, "aucune requête DXF observée");
  if (envoye) {
    // La requête porte le CALCUL, pas une géométrie libre: c'est la forme qui
    // rend l'écart inconstructible.
    const p = JSON.parse(envoye);
    const sec = p.calculation?.section ?? {};
    exige(
      sec.b?.value === Number(B),
      `la requête DXF porte b=${sec.b?.value}, saisi ${B}`,
    );
    exige(
      sec.h?.value === Number(H),
      `la requête DXF porte h=${sec.h?.value}, saisi ${H}`,
    );
    exige(
      p.calculation?.element === REPERE,
      `la requête DXF porte element=${p.calculation?.element}, saisi ${REPERE}`,
    );
    exige(
      p.reinforcement?.bottom?.[0]?.count === 4,
      "le ferraillage envoyé n'est pas celui qui vient d'être saisi",
    );
  }

  // Le fichier: la preuve de ce qui a été produit.
  exige(dxf.length > 1000, `fichier DXF vide ou tronque (${dxf.length} octets)`);
  const cotes = cotesDu(dxf);
  exige(
    cotes.has(B) && cotes.has(H),
    `le DXF cote « ${[...cotes].join(" × ") || "rien"} », attendu « ${B} × ${H} »`,
  );
} catch (cause) {
  echecs.push(`exception pendant le parcours: ${cause}`);
} finally {
  await nav.close();
}

if (echecs.length) {
  console.log("ROUGE — coherence calcul/DXF");
  echecs.forEach((e) => console.log("   - " + e));
  process.exit(1);
}
console.log(`ok: ${REPERE}.dxf cote ${B} x ${H} — la geometrie du calcul`);
