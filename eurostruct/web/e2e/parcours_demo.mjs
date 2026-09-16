/**
 * LE PARCOURS DE DEMONSTRATION, TEL QU'UNE PERSONNE LE FERAIT AU CLAVIER.
 *
 *   node web/e2e/parcours_demo.mjs creer       # cree une etude, PDF, DXF
 *   node web/e2e/parcours_demo.mjs retrouver   # apres redemarrage: la retrouve
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

if (!["creer", "retrouver"].includes(MODE)) {
  console.error("usage: parcours_demo.mjs creer | retrouver");
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
} catch (cause) {
  console.error(`ECHEC: ${cause.message}`);
  code = 1;
} finally {
  await nav.close();
}
process.exit(code);
