/**
 * LE PARCOURS DE DEMONSTRATION, TEL QU'UNE PERSONNE LE FERAIT AU CLAVIER.
 *
 *   node web/e2e/parcours_demo.mjs creer       # cree une etude, PDF, DXF
 *   node web/e2e/parcours_demo.mjs retrouver   # apres redemarrage: la retrouve
 *   node web/e2e/parcours_demo.mjs variante    # en cree une variante, puis
 *                                              # change de projet et se deconnecte
 *
 * CE QUE CE FICHIER PROUVE, ET CE QU'IL NE PROUVE PAS
 * -----------------------------------------------------
 * Il pilote l'environnement monte par `deploy/demo.sh up` — pas un decor
 * dresse pour l'occasion — et fait exactement ce que decrit `docs/ESSAYER.md`:
 * se connecter, choisir le projet belge, remplir les sept etapes, lancer en
 * exploratoire assume, telecharger la note PDF et le plan DXF. Puis, apres
 * `demo.sh down` et `demo.sh up`, se reconnecter, cliquer « Rouvrir » dans
 * l'historique, et retrouver l'etude A L'ECRAN — ses cinq chapitres, leurs
 * etats et leurs taux tels qu'ils ont ete enregistres, ses entrees, sans
 * qu'aucun calcul soit relance — puis RETELECHARGER la note et le plan
 * depuis la liste des livrables, et comparer leurs octets aux empreintes du
 * premier jour. Une capture de l'etude rouverte est ecrite.
 *
 * Le mode « variante » rouvre l'etude, clique « Creer une variante », verifie
 * que les sept etapes sont PREREMPLIES avec les entrees gelees de l'etude,
 * passe de 4 a 5 barres, lance: le nouveau calcul recoit son propre
 * identifiant, nomme son origine, et l'etude d'origine se rouvre encore avec
 * ses cinq verdicts du premier jour. Puis il change de projet et se
 * deconnecte, et verifie que l'ecran n'affiche plus rien du contexte
 * precedent. Une capture de la variante est ecrite.
 *
 * Il ne prouve rien sur la validite normative de l'etude: elle est
 * EXPLORATOIRE, elle porte « PROJET — NON SIGNABLE », et c'est verifie ici.
 *
 * LES OCTETS TELECHARGES SONT COMPARES A L'EMPREINTE ENREGISTREE. Un fichier
 * qui arrive dans le navigateur sans porter l'empreinte que la base a inscrite
 * n'est pas le livrable: c'est autre chose qui porte son nom. Apres le
 * redemarrage, ce sont les MEMES octets qui doivent revenir, pas un document
 * recompose qui leur ressemblerait.
 *
 * AUCUN SECRET N'EST ECRIT. Le mot de passe du compte d'essai est lu dans
 * `deploy/demo.env` et ne sort ni sur la console, ni dans `etat.json`.
 */
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chargerChromium, cheminChromium } from "./playwright.mjs";

const ICI = dirname(fileURLToPath(import.meta.url));
const RACINE = resolve(ICI, "..", "..");
const MODE = process.argv[2] || "";
const SORTIE = resolve(process.env.EUROSTRUCT_DEMO_SORTIE
                       || join(RACINE, "deploy", "demo"));
const NOM_PROJET = "Démonstration — poutre belge";

if (!["creer", "retrouver", "variante"].includes(MODE)) {
  console.error("usage: parcours_demo.mjs creer | retrouver | variante");
  process.exit(2);
}

// ---------------------------------------------------------------------------
// L'ENVIRONNEMENT DE DEMONSTRATION, LU LA OU demo.sh L'A ECRIT
// ---------------------------------------------------------------------------
function lireEnv(chemin) {
  const env = {};
  for (const ligne of readFileSync(chemin, "utf8").split("\n")) {
    const m = ligne.match(/^([A-Z0-9_]+)=(.*)$/);
    if (!m) continue;
    env[m[1]] = m[2].replace(/^"(.*)"$/, "$1");
  }
  return env;
}
const ENVF = process.env.EUROSTRUCT_DEMO_ENV || join(RACINE, "deploy", "demo.env");
if (!existsSync(ENVF)) {
  console.error(`deploy/demo.env absent (${ENVF}): lancez « deploy/demo.sh up ».`);
  process.exit(2);
}
const ENV = lireEnv(ENVF);
const WEB = `http://127.0.0.1:${ENV.WEB_PORT || 3000}`;
const API = ENV.EUROSTRUCT_PUBLIC_API_URL || `http://127.0.0.1:${ENV.API_PORT || 8000}`;
const COMPTE = { courriel: ENV.EUROSTRUCT_DEMO_COMPTE_A, mdp: ENV.EUROSTRUCT_DEMO_MDP_A };
if (!COMPTE.courriel || !COMPTE.mdp) {
  console.error("le compte d'essai A n'est pas dans deploy/demo.env.");
  process.exit(2);
}

// ---------------------------------------------------------------------------
// LE NAVIGATEUR
// ---------------------------------------------------------------------------
const chromium = await chargerChromium();
const chrome = cheminChromium();
if (!chromium || !chrome) {
  console.error("NON EXECUTE: Playwright ou Chromium absent.");
  process.exit(4);
}
mkdirSync(SORTIE, { recursive: true });
const nav = await chromium.launch({ executablePath: chrome, args: ["--no-sandbox"] });
const ctx = await nav.newContext({ acceptDownloads: true });
const page = await ctx.newPage();

const criees = [];
page.on("pageerror", (e) => criees.push(`erreur de page: ${e.message}`));
page.on("console", (m) => {
  if (m.type() === "error") criees.push(`console: ${m.text()}`);
});
//: LE JETON DE LA SESSION, CAPTURE AU PASSAGE. Il ne sert qu'a relire l'etude
//: par l'API sous la meme identite que l'ecran, et n'est jamais ecrit.
let autorisation = "";
//: CE QUE LA PAGE ECRIT. Rouvrir une etude ne doit lancer AUCUN calcul: on
//: compte les POST vers les routes de calcul pour le prouver, pas le deviner.
let calculsLances = 0;
page.on("request", (r) => {
  const a = r.headers().authorization;
  if (a && r.url().startsWith(API)) autorisation = a;
  if (r.method() === "POST" && /\/(beam-verifications|calculations\/ec2)/.test(r.url())) {
    calculsLances += 1;
  }
});

function exige(cond, message) {
  if (!cond) throw new Error(message);
}
function etape(nom) { console.log(`  · ${nom}`); }

async function corpsDe(motif, methode, action) {
  const attente = page.waitForResponse(
    (r) => r.url().includes(motif) && r.request().method() === methode,
    { timeout: 90000 });
  await action();
  const reponse = await attente;
  return { statut: reponse.status(), corps: await reponse.json().catch(() => null) };
}

async function connecter() {
  await page.goto(WEB, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#connecter", { timeout: 30000 });
  exige(await page.locator("#environnement-demonstration").count() === 1,
        "le bandeau « environnement de démonstration » n'est pas affiché");
  await page.fill("#courriel", COMPTE.courriel);
  await page.fill("#mdp", COMPTE.mdp);
  await page.click("#connecter");
  await page.waitForSelector("#deconnecter", { timeout: 30000 });
  await page.waitForSelector("#projet", { timeout: 30000 });
  await page.waitForFunction(
    (nom) => [...document.querySelectorAll("#projet option")]
      .some((o) => o.textContent.includes(nom)),
    NOM_PROJET, { timeout: 30000 });
  await page.selectOption("#projet", { label: await page.evaluate(
    (nom) => [...document.querySelectorAll("#projet option")]
      .find((o) => o.textContent.includes(nom)).textContent, NOM_PROJET) });
  await page.waitForSelector("#etape-section", { timeout: 30000 });
}

/** Les sept etapes, par les onglets, comme un ingenieur. */
async function remplirLesEtapes() {
  await page.click("#etape-section");
  for (const [sel, v] of [["#vc-b", "300"], ["#vc-h", "600"], ["#vc-d", "550"],
                          ["#vc-leff", "6000"]]) await page.fill(sel, v);
  await page.click("#etape-materiaux");
  await page.fill("#vc-beton", "C30/37");
  await page.fill("#vc-acier", "B500B");
  await page.selectOption("#vc-expo", "XC3");
  await page.click("#etape-sollicitations");
  for (const [sel, v] of [["#vc-med", "250"], ["#vc-ved", "300"],
                          ["#vc-mchar", "180"], ["#vc-mqp", "120"]]) await page.fill(sel, v);
  await page.click("#etape-ferraillage");
  for (const [sel, v] of [["#vc-nb", "4"], ["#vc-phi", "20"], ["#vc-branches", "2"],
                          ["#vc-phiw", "10"], ["#vc-s", "150"], ["#vc-enrobage", "40"],
                          ["#vc-cot", "1.5"], ["#vc-ancrage", "800"]]) await page.fill(sel, v);
  await page.click("#etape-service");
  await page.fill("#vc-phicreep", "2.0");
  await page.selectOption("#vc-systeme", "simply_supported");
}

async function telecharger(selecteur, fichier) {
  const attente = page.waitForEvent("download", { timeout: 90000 });
  const cree = await corpsDe("/deliverables", "POST", () => page.click(selecteur));
  const dl = await attente;
  const chemin = join(SORTIE, fichier);
  await dl.saveAs(chemin);
  const octets = readFileSync(chemin);
  const sha256 = createHash("sha256").update(octets).digest("hex");
  exige(cree.statut === 201, `${fichier}: la creation a rendu ${cree.statut}`);
  exige(cree.corps?.sha256 === sha256,
        `${fichier}: les octets recus (${sha256.slice(0, 12)}) ne portent pas `
        + `l'empreinte enregistree (${String(cree.corps?.sha256).slice(0, 12)})`);
  return { fichier: chemin, taille: octets.length, sha256, kind: cree.corps?.kind,
           deliverable_id: cree.corps?.deliverable_id ?? null, octets };
}

/**
 * Rouvre l'etude enregistree depuis l'historique et attend sa synthese relue.
 * Rend le corps que la route de relecture a rendu.
 */
async function rouvrirDepuisHistorique(calculationId) {
  const ligne = `tr[data-calcul="${calculationId}"]`;
  await page.waitForSelector(ligne, { timeout: 30000 });
  const relecture = page.waitForResponse(
    (r) => r.url().includes(`/beam-verifications/${calculationId}`)
           && r.request().method() === "GET", { timeout: 60000 });
  await page.click(`${ligne} button:has-text("Rouvrir")`);
  const reponse = await relecture;
  exige(reponse.status() === 200, `la relecture a rendu ${reponse.status()}`);
  await page.waitForSelector(
    `#synthese-etude[data-calcul="${calculationId}"][data-relue="oui"]`,
    { timeout: 30000 });
  return reponse.json();
}

/** Les cinq chapitres affiches, compares a ceux enregistres. */
async function exigerChapitres(attendus) {
  for (const attendu of attendus) {
    const rangee = page.locator(`#chapitre-${attendu.key}`);
    exige(await rangee.count() === 1, `le chapitre « ${attendu.key} » n'est pas affiche`);
    const etatAffiche = await rangee.getAttribute("data-etat");
    exige(etatAffiche === attendu.status,
          `chapitre « ${attendu.key} »: etat affiche « ${etatAffiche} », `
          + `enregistre « ${attendu.status} »`);
    const taux = (await rangee.locator("td.nombre").innerText()).trim();
    const tauxAttendu = typeof attendu.utilisation === "number"
      ? `${(attendu.utilisation * 100).toFixed(1)} %` : "—";
    exige(taux === tauxAttendu,
          `chapitre « ${attendu.key} »: taux affiche « ${taux} », attendu « ${tauxAttendu} »`);
  }
}

const ETAT = join(SORTIE, "etat.json");
let code = 0;
try {
  if (MODE === "creer") {
    etape("connexion du compte d'essai A, choix du projet belge");
    await connecter();
    const projetId = await page.$eval("#projet", (s) => s.value);

    etape("les sept etapes, puis le mode exploratoire assume");
    await remplirLesEtapes();
    await page.click("#etape-mode");
    await page.uncheck("#vc-strict");
    await page.check("#vc-assume");

    etape("lancement de l'etude");
    const etude = await corpsDe("/beam-verifications", "POST",
                                () => page.click("#lancer-verification"));
    exige(etude.statut === 201, `l'etude a rendu ${etude.statut}`);
    exige(etude.corps?.status === "passed", `l'etude n'a pas abouti: ${etude.corps?.status}`);
    exige(etude.corps?.is_exploratory === true, "l'etude n'est pas marquee exploratoire");
    exige((etude.corps?.sections ?? []).length === 5,
          `${(etude.corps?.sections ?? []).length} chapitre(s) au lieu de 5`);
    const calculId = etude.corps.calculation_id;
    await page.waitForSelector("#synthese-etude", { timeout: 30000 });
    const synthese = await page.locator("#synthese-etude").innerText();
    exige(synthese.includes("NON SIGNABLE"),
          "la mention « PROJET — NON SIGNABLE » n'est pas affichee");

    etape("note de calcul PDF");
    const pdf = await telecharger("#etude-note-pdf", "note-de-calcul.pdf");
    exige(pdf.octets.subarray(0, 5).toString() === "%PDF-", "le fichier n'est pas un PDF");
    exige(pdf.kind === "calculation_note_pdf", `nature inattendue: ${pdf.kind}`);

    etape("plan de ferraillage DXF");
    const dxf = await telecharger("#etude-plan-dxf", "plan-de-ferraillage.dxf");
    const texte = dxf.octets.toString("utf8");
    exige(texte.includes("AC1032") && texte.includes("ENTITIES") && texte.trimEnd().endsWith("EOF"),
          "le fichier n'a pas la structure d'un DXF R2018");
    exige(dxf.kind === "rebar_drawing_dxf", `nature inattendue: ${dxf.kind}`);

    exige(criees.length === 0, `la page a crie: ${criees.slice(0, 3).join(" | ")}`);
    //: LES CINQ VERDICTS DU PREMIER JOUR SONT GARDES, tels que le serveur les
    //: a rendus: apres le redemarrage, l'ecran devra montrer EXACTEMENT ceux-la.
    writeFileSync(ETAT, JSON.stringify({
      cree_le: new Date().toISOString(),
      project_id: projetId,
      calculation_id: calculId,
      is_exploratory: true,
      calculation_fingerprint: etude.corps.calculation_fingerprint,
      sections: etude.corps.sections.map((s) => ({
        key: s.key, status: s.status, utilisation: s.utilisation ?? null,
      })),
      inputs: etude.corps.inputs ?? {},
      pdf: { fichier: pdf.fichier, taille: pdf.taille, sha256: pdf.sha256,
             deliverable_id: pdf.deliverable_id },
      dxf: { fichier: dxf.fichier, taille: dxf.taille, sha256: dxf.sha256,
             deliverable_id: dxf.deliverable_id },
    }, null, 2) + "\n");
    console.log("");
    console.log(`etude exploratoire ${calculId} creee sur le projet ${projetId}`);
    console.log(`  PDF ${pdf.taille} o  sha256 ${pdf.sha256}`);
    console.log(`  DXF ${dxf.taille} o  sha256 ${dxf.sha256}`);
    console.log(`  etat: ${ETAT}`);
  } else {
    exige(existsSync(ETAT), `${ETAT} absent: lancez d'abord « creer ».`);
    const etat = JSON.parse(readFileSync(ETAT, "utf8"));

    etape("reconnexion apres redemarrage, choix du projet belge");
    await connecter();
    const projetId = await page.$eval("#projet", (s) => s.value);
    exige(projetId === etat.project_id,
          `le projet retrouve (${projetId}) n'est pas celui de l'etude (${etat.project_id})`);

    etape("l'etude est dans l'historique a l'ecran");
    const ligne = `tr[data-calcul="${etat.calculation_id}"]`;
    await page.waitForSelector(ligne, { timeout: 30000 });
    const lignesAvant = await page.locator("tr[data-calcul]").count();

    etape("« Rouvrir »: les cinq chapitres, tels qu'enregistres, sans recalcul");
    const relecture = page.waitForResponse(
      (r) => r.url().includes(`/beam-verifications/${etat.calculation_id}`)
             && r.request().method() === "GET", { timeout: 60000 });
    await page.click(`${ligne} button:has-text("Rouvrir")`);
    const reponseRelue = await relecture;
    exige(reponseRelue.status() === 200, `la relecture a rendu ${reponseRelue.status()}`);
    const corps = await reponseRelue.json();
    exige(corps.calculation_id === etat.calculation_id, "l'identifiant relu differe");
    exige((corps.sections ?? []).length === 5, "l'etude relue n'a pas ses cinq chapitres");
    exige(corps.is_exploratory === true, "l'etude relue n'est plus exploratoire");
    exige(corps.calculation_fingerprint === etat.calculation_fingerprint,
          "l'empreinte de calcul relue n'est pas celle du premier jour");
    await page.waitForSelector(
      `#synthese-etude[data-calcul="${etat.calculation_id}"][data-relue="oui"]`,
      { timeout: 30000 });
    exige(await page.locator("#etude-relue").count() === 1,
          "la synthese ne dit pas que l'etude est rouverte sans recalcul");
    for (const attendu of etat.sections) {
      const rangee = page.locator(`#chapitre-${attendu.key}`);
      exige(await rangee.count() === 1, `le chapitre « ${attendu.key} » n'est pas affiche`);
      const etatAffiche = await rangee.getAttribute("data-etat");
      exige(etatAffiche === attendu.status,
            `chapitre « ${attendu.key} »: etat affiche « ${etatAffiche} », `
            + `enregistre « ${attendu.status} »`);
      const taux = (await rangee.locator("td.nombre").innerText()).trim();
      const tauxAttendu = typeof attendu.utilisation === "number"
        ? `${(attendu.utilisation * 100).toFixed(1)} %` : "—";
      exige(taux === tauxAttendu,
            `chapitre « ${attendu.key} »: taux affiche « ${taux} », attendu « ${tauxAttendu} »`);
    }
    const synthese = await page.locator("#synthese-etude").innerText();
    exige(synthese.includes("NON SIGNABLE"),
          "l'etude rouverte ne porte plus « PROJET — NON SIGNABLE »");
    //: LES ENTREES VIENNENT DU CALCUL ENREGISTRE, et on le verifie sur la
    //: geometrie: ce que le serveur a gele le premier jour est ce que l'ecran
    //: montre aujourd'hui, valeur et unite.
    await page.evaluate(() => document.querySelectorAll("#synthese-etude details")
      .forEach((d) => { d.open = true; }));
    for (const cle of ["geometry.b", "geometry.h", "M_Ed", "V_Ed"]) {
      const affichee = (await page.locator(`tr[data-entree="${cle}"] td`).innerText()).trim();
      const enregistree = cle.split(".").reduce((o, k) => o?.[k], etat.inputs);
      exige(String(enregistree) === affichee,
            `entree « ${cle} »: affichee « ${affichee} », enregistree « ${enregistree} »`);
    }
    exige(calculsLances === 0, `${calculsLances} calcul(s) lance(s) par la reouverture`);
    exige(await page.locator("tr[data-calcul]").count() === lignesAvant,
          "l'historique a gagne une ligne: quelque chose a ete recalcule");

    etape("capture de l'etude rouverte");
    const capture = join(SORTIE, "etude-rouverte.png");
    await page.locator("#synthese-etude").screenshot({ path: capture });

    etape("les deux livrables, retelecharges depuis l'interface: memes octets");
    await page.waitForSelector("#table-livrables", { timeout: 30000 });
    const retrouves = {};
    for (const [nom, attendu, fichier] of [
      ["PDF", etat.pdf, "note-de-calcul.retrouvee.pdf"],
      ["DXF", etat.dxf, "plan-de-ferraillage.retrouve.dxf"],
    ]) {
      const bouton = page.locator(
        `tr[data-livrable="${attendu.deliverable_id}"] button:text-is("Télécharger")`);
      exige(await bouton.count() === 1,
            `le ${nom} (${attendu.deliverable_id}) n'a pas de bouton de telechargement`);
      const attente = page.waitForEvent("download", { timeout: 90000 });
      await bouton.click();
      const dl = await attente;
      const chemin = join(SORTIE, fichier);
      await dl.saveAs(chemin);
      const octets = readFileSync(chemin);
      const sha256 = createHash("sha256").update(octets).digest("hex");
      exige(sha256 === attendu.sha256,
            `le ${nom} retelecharge (${sha256.slice(0, 12)}) n'a pas les octets `
            + `du premier jour (${attendu.sha256.slice(0, 12)})`);
      exige(octets.length === attendu.taille,
            `le ${nom} retelecharge fait ${octets.length} o au lieu de ${attendu.taille}`);
      retrouves[nom] = { fichier: chemin, sha256 };
    }
    exige(criees.length === 0, `la page a crie: ${criees.slice(0, 3).join(" | ")}`);
    writeFileSync(ETAT, JSON.stringify({
      ...etat,
      retrouvee_le: new Date().toISOString(),
      capture,
      retelecharges: retrouves,
    }, null, 2) + "\n");
    console.log("");
    console.log(`etude ${etat.calculation_id} rouverte apres redemarrage: cinq chapitres `
                + "et entrees tels qu'enregistres, aucun calcul relance; PDF et DXF "
                + "retelecharges depuis l'interface, octets identiques au premier jour.");
    console.log(`  capture: ${capture}`);
  }

  if (MODE === "variante") {
    exige(existsSync(ETAT), `${ETAT} absent: lancez d'abord « creer ».`);
    const etat = JSON.parse(readFileSync(ETAT, "utf8"));
    const origineId = etat.calculation_id;

    etape("connexion, projet belge, « Rouvrir » l'etude enregistree");
    await connecter();
    const projetId = await page.$eval("#projet", (s) => s.value);
    exige(projetId === etat.project_id, "le projet retrouve n'est pas celui de l'etude");
    await rouvrirDepuisHistorique(origineId);
    const lignesAvant = await page.locator("tr[data-calcul]").count();
    exige(await page.locator("#etude-derivee").count() === 0,
          "l'etude initiale se presente comme une variante");

    etape("« Creer une variante »: les sept etapes preremplies depuis les entrees gelees");
    await page.click("#etude-variante");
    await page.waitForSelector(`#variante-origine[data-origine="${origineId}"]`,
                               { timeout: 15000 });
    exige(await page.locator("#variante-non-repris").count() === 0,
          `le formulaire n'a pas repris: ${
            await page.locator("#variante-non-repris").innerText().catch(() => "?")}`);
    //: CHAQUE CHAMP PORTE LA VALEUR GELEE DE L'ETUDE — nombre sans unite, tel
    //: que le champ le demande — et pas le defaut de l'ecran. Le mode strict
    //: est celui de l'etude (exploratoire), l'assumer reste un geste.
    const nombreDe = (texte) => String(texte).trim().split(/\s+/)[0];
    const attendus = [
      ["#etape-section", [["#vc-b", nombreDe(etat.inputs.geometry.b)],
                          ["#vc-h", nombreDe(etat.inputs.geometry.h)],
                          ["#vc-d", nombreDe(etat.inputs.geometry.d)],
                          ["#vc-leff", nombreDe(etat.inputs.geometry.l_eff)]]],
      ["#etape-materiaux", [["#vc-beton", etat.inputs.concrete_grade],
                            ["#vc-acier", etat.inputs.steel_grade],
                            ["#vc-expo", etat.inputs.exposure_class]]],
      ["#etape-sollicitations", [["#vc-med", nombreDe(etat.inputs.M_Ed)],
                                 ["#vc-ved", nombreDe(etat.inputs.V_Ed)],
                                 ["#vc-mchar", nombreDe(etat.inputs.M_char)],
                                 ["#vc-mqp", nombreDe(etat.inputs.M_qp)]]],
      ["#etape-ferraillage", [["#vc-nb", String(etat.inputs.bars.count)],
                              ["#vc-phi", nombreDe(etat.inputs.bars.diameter)],
                              ["#vc-branches", String(etat.inputs.links.legs)],
                              ["#vc-phiw", nombreDe(etat.inputs.links.diameter)],
                              ["#vc-s", nombreDe(etat.inputs.links.spacing)],
                              ["#vc-enrobage", nombreDe(etat.inputs.cover)],
                              ["#vc-cot", String(etat.inputs.cot_theta)],
                              ["#vc-ancrage", nombreDe(etat.inputs.anchorage_available)],
                              ["#vc-adherence", etat.inputs.bond_condition]]],
      ["#etape-service", [["#vc-phicreep", String(etat.inputs.phi_creep)],
                          ["#vc-systeme", etat.inputs.system]]],
    ];
    for (const [onglet, champs] of attendus) {
      await page.click(onglet);
      for (const [sel, attendu] of champs) {
        const lu = await page.$eval(sel, (e) => e.value);
        exige(lu === attendu, `${sel}: prerempli « ${lu} », attendu « ${attendu} »`);
      }
    }
    await page.click("#etape-mode");
    exige(!(await page.isChecked("#vc-strict")),
          "la variante d'une etude exploratoire devrait partir en mode exploratoire");
    exige(!(await page.isChecked("#vc-assume")),
          "l'exploratoire a ete assume tacitement: c'est un geste a refaire");

    etape("modification du ferraillage: 4 -> 5 barres, puis lancement");
    await page.click("#etape-ferraillage");
    await page.fill("#vc-nb", "5");
    await page.click("#etape-mode");
    await page.check("#vc-assume");
    const lances = calculsLances;
    const reponse = await corpsDe("/beam-verifications", "POST",
                                  () => page.click("#lancer-verification"));
    exige(reponse.statut === 201, `la variante a rendu ${reponse.statut}`);
    const variante = reponse.corps;
    exige(calculsLances === lances + 1, "un seul calcul devait partir");
    exige(variante.calculation_id && variante.calculation_id !== origineId,
          "la variante n'a pas recu son propre identifiant");
    exige(variante.derived_from_calculation_id === origineId,
          `la variante nomme « ${variante.derived_from_calculation_id} » `
          + `au lieu de son origine ${origineId}`);
    exige(variante.status === "passed", `la variante n'a pas abouti: ${variante.status}`);
    exige(variante.inputs?.bars?.count === 5, "la variante n'a pas 5 barres");
    exige(variante.is_exploratory === true, "la variante n'est pas exploratoire");
    await page.waitForSelector(
      `#synthese-etude[data-calcul="${variante.calculation_id}"][data-relue="non"]`,
      { timeout: 30000 });
    await page.waitForSelector(`#etude-derivee[data-origine="${origineId}"]`,
                               { timeout: 15000 });
    exige((await page.locator("#synthese-etude").innerText()).includes("NON SIGNABLE"),
          "la variante ne porte pas « PROJET — NON SIGNABLE »");
    //: LA FLEXION A CHANGE AVEC LES BARRES: le taux affiche est celui de la
    //: variante, pas celui de l'origine copie.
    const flexionOrigine = etat.sections.find((s) => s.key === "flexure");
    const flexionVariante = variante.sections.find((s) => s.key === "flexure");
    exige(typeof flexionVariante?.utilisation === "number"
          && flexionVariante.utilisation < flexionOrigine.utilisation,
          "cinq barres au lieu de quatre devraient abaisser le taux de flexion");
    await exigerChapitres(variante.sections.map((s) => ({
      key: s.key, status: s.status, utilisation: s.utilisation ?? null })));
    await page.waitForFunction(
      (n) => document.querySelectorAll("tr[data-calcul]").length === n,
      lignesAvant + 1, { timeout: 30000 });

    etape("capture de la variante, puis sa note PDF");
    const captureVariante = join(SORTIE, "etude-variante.png");
    await page.locator("#synthese-etude").screenshot({ path: captureVariante });
    const pdfVariante = await telecharger("#etude-note-pdf", "note-de-calcul.variante.pdf");
    exige(pdfVariante.octets.subarray(0, 5).toString() === "%PDF-", "pas un PDF");

    etape("« Rouvrir l'etude d'origine »: ses cinq verdicts du premier jour, intacts");
    const relectureOrigine = page.waitForResponse(
      (r) => r.url().includes(`/beam-verifications/${origineId}`)
             && r.request().method() === "GET", { timeout: 60000 });
    await page.click("#rouvrir-origine");
    const origineRelue = await (await relectureOrigine).json();
    exige(origineRelue.calculation_fingerprint === etat.calculation_fingerprint,
          "l'origine relue n'a plus l'empreinte du premier jour");
    exige(!origineRelue.derived_from_calculation_id,
          "l'origine se presente maintenant comme une variante");
    await page.waitForSelector(
      `#synthese-etude[data-calcul="${origineId}"][data-relue="oui"]`, { timeout: 30000 });
    await exigerChapitres(etat.sections);
    exige(await page.locator("#etude-derivee").count() === 0,
          "l'etude d'origine affiche un bandeau de variante");
    //: LE LIVRABLE DE L'ORIGINE EST TOUJOURS LA, avec son empreinte.
    exige(await page.locator(
      `tr[data-livrable="${etat.pdf.deliverable_id}"] button:text-is("Télécharger")`)
      .count() === 1, "la note PDF de l'etude d'origine n'est plus dans les livrables");
    exige(calculsLances === lances + 1, "rouvrir l'origine a lance un calcul");

    etape("changement de projet: l'ecran ne montre plus rien du dossier precedent");
    await page.selectOption("#projet", "");
    await page.waitForFunction(() => !document.querySelector("#synthese-etude"),
                               null, { timeout: 15000 });
    exige(await page.locator("tr[data-calcul]").count() === 0,
          "l'historique du projet precedent est encore affiche");
    exige(await page.locator("#table-livrables").count() === 0,
          "les livrables du projet precedent sont encore affiches");
    exige(await page.locator("#variante-origine").count() === 0,
          "la saisie porte encore l'origine du projet precedent");
    //: REVENIR SUR LE PROJET NE RESSUSCITE PAS L'ETUDE AFFICHEE: l'historique
    //: revient, la synthese non — il faut la rouvrir.
    await page.selectOption("#projet", projetId);
    await page.waitForSelector(`tr[data-calcul="${variante.calculation_id}"]`,
                               { timeout: 30000 });
    exige(await page.locator("#synthese-etude").count() === 0,
          "une synthese est reapparue sans qu'on l'ait rouverte");
    await rouvrirDepuisHistorique(variante.calculation_id);
    await page.waitForSelector(`#etude-derivee[data-origine="${origineId}"]`,
                               { timeout: 15000 });

    etape("deconnexion: plus de synthese, plus d'historique, plus de projet");
    await page.click("#deconnecter");
    await page.waitForSelector("#connecter", { timeout: 15000 });
    await page.waitForFunction(() => !document.querySelector("#synthese-etude"),
                               null, { timeout: 15000 });
    exige(await page.locator("tr[data-calcul]").count() === 0,
          "l'historique survit a la deconnexion");
    exige(await page.locator("#projet").count() === 0,
          "le selecteur de projet survit a la deconnexion");
    exige(await page.locator("#etude-derivee, #variante-origine").count() === 0,
          "un lien de variante survit a la deconnexion");

    exige(criees.length === 0, `la page a crie: ${criees.slice(0, 3).join(" | ")}`);
    writeFileSync(ETAT, JSON.stringify({
      ...etat,
      variante: {
        creee_le: new Date().toISOString(),
        calculation_id: variante.calculation_id,
        derived_from_calculation_id: variante.derived_from_calculation_id,
        modification: "bars.count 4 -> 5",
        calculation_fingerprint: variante.calculation_fingerprint,
        sections: variante.sections.map((s) => ({
          key: s.key, status: s.status, utilisation: s.utilisation ?? null,
        })),
        capture: captureVariante,
        pdf: { fichier: pdfVariante.fichier, taille: pdfVariante.taille,
               sha256: pdfVariante.sha256, deliverable_id: pdfVariante.deliverable_id },
      },
    }, null, 2) + "\n");
    console.log("");
    console.log(`variante ${variante.calculation_id} creee depuis ${origineId} `
                + "(5 barres au lieu de 4): identifiant propre, origine nommee, etude "
                + "d'origine rouverte intacte; changement de projet et deconnexion "
                + "effacent l'ecran.");
    console.log(`  capture: ${captureVariante}`);
    console.log(`  PDF ${pdfVariante.taille} o  sha256 ${pdfVariante.sha256}`);
  }
} catch (cause) {
  console.error(`ECHEC: ${cause.message}`);
  code = 1;
} finally {
  await nav.close();
}
process.exit(code);
