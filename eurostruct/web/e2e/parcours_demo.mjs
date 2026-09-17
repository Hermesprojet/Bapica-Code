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
 * Le mode « variante » rouvre l'etude et mesure quatre choses, dans l'ordre:
 *
 *   A. une variante SANS modification — chaque champ prerempli est compare a
 *      la REQUETE GELEE de l'origine (valeur et unite saisies), et le calcul
 *      lance rend la MEME empreinte d'entrees d'ingenierie et la MEME
 *      empreinte de calcul que l'origine, sous un identifiant different qui
 *      nomme l'origine;
 *   B. une variante MODIFIEE depuis l'origine — 5 barres au lieu de 4 — dont
 *      les entrees gelees ne different de l'origine QUE sur `bars.count`;
 *      capture et note PDF;
 *   C. une etude portant les PARAMETRES AVANCES (classe associee pour w_max,
 *      rapport b_eff/b_w, six coefficients d'ancrage), puis sa variante
 *      identique: les champs les reprennent, et les empreintes sont egales;
 *   D. le retour a l'origine — ses cinq verdicts du premier jour, intacts, sa
 *      note toujours dans les livrables — puis le changement de projet et la
 *      deconnexion, qui effacent tout ce qui etait affiche.
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

/**
 * Les chemins ou deux structures JSON different, feuille par feuille.
 *
 * C'EST LA COMPARAISON DES ENTREES METIER: « une variante sans modification
 * conserve les memes entrees » se mesure par une liste vide; « une
 * modification volontaire ne change que les donnees concernees » par une
 * liste qui ne contient QUE ces chemins-la.
 */
function ecarts(a, b, chemin = "") {
  const objet = (x) => x !== null && typeof x === "object" && !Array.isArray(x);
  if (objet(a) && objet(b)) {
    const cles = new Set([...Object.keys(a), ...Object.keys(b)]);
    return [...cles].sort()
      .flatMap((k) => ecarts(a[k], b[k], chemin ? `${chemin}.${k}` : k));
  }
  if (Array.isArray(a) && Array.isArray(b) && a.length === b.length) {
    return a.flatMap((x, i) => ecarts(x, b[i], `${chemin}[${i}]`));
  }
  return a === b ? [] : [chemin];
}
/** La requete gelee sans son lien d'origine: ce qui doit etre identique. */
function sansFiliation(requete) {
  const { derived_from_calculation_id: _origine, ...reste } = requete ?? {};
  return reste;
}
const ALPHAS = ["alpha_1", "alpha_2", "alpha_3", "alpha_4", "alpha_5", "alpha_6"];

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
  //: LE BOUTON DE LA LIGNE, PAS LE PREMIER « ROUVRIR » VENU: une ligne de
  //: variante porte aussi « Rouvrir l'origine », une origine liste ses
  //: variantes avec leur propre « Rouvrir ».
  await page.click(`${ligne} #rouvrir-${calculationId}`);
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
    exige(etude.corps?.request && typeof etude.corps.request === "object",
          "la reponse ne rend pas la requete gelee: aucune variante fidele n'en partira");
    await page.waitForSelector("#synthese-etude", { timeout: 30000 });
    const synthese = await page.locator("#synthese-etude").innerText();
    exige(synthese.includes("NON SIGNABLE"),
          "la mention « PROJET — NON SIGNABLE » n'est pas affichee");
    //: LA CAPTURE DE L'ETUDE QUI VIENT D'ETRE CREEE — la synthese telle que
    //: l'ingenieur la voit au premier jour, avant tout redemarrage.
    const captureCreee = join(SORTIE, "etude-creee.png");
    await page.locator("#synthese-etude").screenshot({ path: captureCreee });

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
      engineering_inputs_hash: etude.corps.engineering_inputs_hash,
      sections: etude.corps.sections.map((s) => ({
        key: s.key, status: s.status, utilisation: s.utilisation ?? null,
      })),
      inputs: etude.corps.inputs ?? {},
      //: LA REQUETE GELEE, telle que le serveur l'a rendue: c'est d'elle
      //: qu'une variante fidele repart, et le mode « variante » la compare.
      request: etude.corps.request,
      capture_creee: captureCreee,
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
  } else if (MODE === "retrouver") {
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
    await page.click(`${ligne} #rouvrir-${etat.calculation_id}`);
    const reponseRelue = await relecture;
    exige(reponseRelue.status() === 200, `la relecture a rendu ${reponseRelue.status()}`);
    const corps = await reponseRelue.json();
    exige(corps.calculation_id === etat.calculation_id, "l'identifiant relu differe");
    exige((corps.sections ?? []).length === 5, "l'etude relue n'a pas ses cinq chapitres");
    exige(corps.is_exploratory === true, "l'etude relue n'est plus exploratoire");
    exige(corps.calculation_fingerprint === etat.calculation_fingerprint,
          "l'empreinte de calcul relue n'est pas celle du premier jour");
    exige(corps.engineering_inputs_hash === etat.engineering_inputs_hash,
          "l'empreinte des entrees relue n'est pas celle du premier jour");
    //: LA REQUETE GELEE REVIENT A L'IDENTIQUE apres le redemarrage — valeurs
    //: et unites saisies — sinon aucune variante fidele n'en repartirait.
    const ecartsRequete = ecarts(etat.request, corps.request);
    exige(ecartsRequete.length === 0,
          `la requete gelee relue differe de celle du premier jour: ${ecartsRequete.join(", ")}`);
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
    exige(etat.request && typeof etat.request === "object",
          "etat.json ne porte pas la requete gelee: relancez « creer »");

    /**
     * Ce que chaque champ doit montrer pour une variante FIDELE a `requete`:
     * la valeur saisie, telle quelle — pas la grandeur formatee du moteur.
     * Les entrees avancees absentes de la requete laissent leur champ vide.
     */
    const champsAttendus = (requete) => {
      const q = (g) => String(g.value);
      const alphas = requete.anchorage_coefficients;
      return [
        ["#etape-dossier", [["#vc-element", requete.element]]],
        ["#etape-section", [["#vc-b", q(requete.geometry.b)],
                            ["#vc-h", q(requete.geometry.h)],
                            ["#vc-d", q(requete.geometry.d)],
                            ["#vc-leff", q(requete.geometry.l_eff)],
                            ["#vc-beff", requete.b_eff_over_b_w == null
                              ? "" : String(requete.b_eff_over_b_w)]]],
        ["#etape-materiaux", [["#vc-beton", requete.materials.concrete_grade],
                              ["#vc-acier", requete.materials.steel_grade],
                              ["#vc-expo", requete.exposure_class],
                              ["#vc-wmax", requete.w_max_associated_class ?? ""]]],
        ["#etape-sollicitations", [["#vc-med", q(requete.M_Ed)],
                                   ["#vc-ved", q(requete.V_Ed)],
                                   ["#vc-mchar", q(requete.M_char)],
                                   ["#vc-mqp", q(requete.M_qp)]]],
        ["#etape-ferraillage", [["#vc-nb", String(requete.bars.count)],
                                ["#vc-phi", q(requete.bars.diameter)],
                                ["#vc-branches", String(requete.links.legs)],
                                ["#vc-phiw", q(requete.links.diameter)],
                                ["#vc-s", q(requete.links.spacing)],
                                ["#vc-enrobage", q(requete.cover)],
                                ["#vc-cot", String(requete.cot_theta)],
                                ["#vc-ancrage", q(requete.anchorage_available)],
                                ["#vc-adherence", requete.bond_condition ?? "good"],
                                ...ALPHAS.map((a, i) => [
                                  `#vc-alpha${i + 1}`, alphas ? String(alphas[a]) : ""])]],
        ["#etape-service", [["#vc-phicreep", String(requete.phi_creep)],
                            ["#vc-systeme", requete.structural_system]]],
      ];
    };

    /** Clique « Creer une variante » sur l'etude affichee et verifie la reprise. */
    async function ouvrirVarianteDe(etudeId, requete) {
      await page.click("#etude-variante");
      await page.waitForSelector(`#variante-origine[data-origine="${etudeId}"]`,
                                 { timeout: 15000 });
      exige(await page.locator("#variante-non-repris").count() === 0,
            `le formulaire n'a pas tout repris: ${
              await page.locator("#variante-non-repris").innerText().catch(() => "?")}`);
      for (const [onglet, champs] of champsAttendus(requete)) {
        await page.click(onglet);
        for (const [sel, attendu] of champs) {
          const lu = await page.$eval(sel, (e) => e.value);
          exige(lu === attendu, `${sel}: prerempli « ${lu} », attendu « ${attendu} »`);
        }
      }
      await page.click("#etape-service");
      exige((await page.isChecked("#vc-cloisons")) === (requete.supports_brittle_partitions === true),
            "la case « cloisons fragiles » ne reprend pas l'etude d'origine");
      await page.click("#etape-mode");
      exige((await page.isChecked("#vc-strict")) === (requete.strict_ndp === true),
            "le mode strict de la variante n'est pas celui de l'etude d'origine");
      exige(!(await page.isChecked("#vc-assume")),
            "l'exploratoire a ete assume tacitement: c'est un geste a refaire");
      exige(await page.isDisabled("#lancer-verification"),
            "le lancement est ouvert avant que l'exploratoire soit assume");
    }

    /** Assume l'exploratoire s'il y a lieu et lance; rend le corps du 201. */
    async function lancerEtude() {
      await page.click("#etape-mode");
      if (!(await page.isChecked("#vc-strict")) && !(await page.isChecked("#vc-assume"))) {
        await page.check("#vc-assume");
      }
      const avant = calculsLances;
      const reponse = await corpsDe("/beam-verifications", "POST",
                                    () => page.click("#lancer-verification"));
      exige(reponse.statut === 201,
            `le lancement a rendu ${reponse.statut}: ${JSON.stringify(reponse.corps).slice(0, 300)}`);
      exige(calculsLances === avant + 1, "un seul calcul devait partir");
      const corps = reponse.corps;
      await page.waitForSelector(
        `#synthese-etude[data-calcul="${corps.calculation_id}"][data-relue="non"]`,
        { timeout: 30000 });
      return corps;
    }
    const attendreLignes = (n) => page.waitForFunction(
      (m) => document.querySelectorAll("tr[data-calcul]").length === m, n, { timeout: 30000 });

    etape("connexion, projet belge, « Rouvrir » l'etude enregistree");
    await connecter();
    const projetId = await page.$eval("#projet", (s) => s.value);
    exige(projetId === etat.project_id, "le projet retrouve n'est pas celui de l'etude");
    const origineRelue0 = await rouvrirDepuisHistorique(origineId);
    exige(ecarts(etat.request, origineRelue0.request).length === 0,
          "la requete gelee relue n'est pas celle du premier jour");
    const lignesAvant = await page.locator("tr[data-calcul]").count();
    exige(await page.locator("#etude-derivee").count() === 0,
          "l'etude initiale se presente comme une variante");

    // -- A. LA VARIANTE SANS MODIFICATION ------------------------------------
    etape("A. « Creer une variante »: chaque champ prerempli = la requete gelee de l'origine");
    await ouvrirVarianteDe(origineId, etat.request);

    etape("A. lancement sans rien modifier: memes entrees metier, memes empreintes");
    const identique = await lancerEtude();
    exige(identique.calculation_id !== origineId,
          "la variante identique n'a pas recu son propre identifiant");
    exige(identique.derived_from_calculation_id === origineId,
          `la variante identique nomme « ${identique.derived_from_calculation_id} » `
          + `au lieu de ${origineId}`);
    exige(identique.engineering_inputs_hash === etat.engineering_inputs_hash,
          "la variante sans modification n'a pas la meme empreinte d'entrees que "
          + `son origine (${String(identique.engineering_inputs_hash).slice(0, 12)} `
          + `≠ ${String(etat.engineering_inputs_hash).slice(0, 12)})`);
    exige(identique.calculation_fingerprint === etat.calculation_fingerprint,
          "la variante sans modification n'a pas la meme empreinte de calcul que son origine");
    const ecartsIdentique = ecarts(etat.inputs, identique.inputs);
    exige(ecartsIdentique.length === 0,
          `les entrees gelees de la variante identique different: ${ecartsIdentique.join(", ")}`);
    const ecartsRequeteIdentique = ecarts(sansFiliation(etat.request),
                                          sansFiliation(identique.request));
    exige(ecartsRequeteIdentique.length === 0,
          `la requete gelee de la variante identique differe: ${ecartsRequeteIdentique.join(", ")}`);
    exige(ecarts(etat.sections, identique.sections.map((s) => ({
      key: s.key, status: s.status, utilisation: s.utilisation ?? null }))).length === 0,
          "les cinq verdicts de la variante identique ne sont pas ceux de l'origine");
    await page.waitForSelector(`#etude-derivee[data-origine="${origineId}"]`,
                               { timeout: 15000 });
    await exigerChapitres(etat.sections);
    await attendreLignes(lignesAvant + 1);

    // -- B. LA VARIANTE MODIFIEE, DEPUIS L'ORIGINE ---------------------------
    etape("B. retour a l'origine, nouvelle variante: 4 -> 5 barres, puis lancement");
    const relectureB = page.waitForResponse(
      (r) => r.url().includes(`/beam-verifications/${origineId}`)
             && r.request().method() === "GET", { timeout: 60000 });
    await page.click("#rouvrir-origine");
    exige((await relectureB).status() === 200, "la relecture de l'origine a echoue");
    await page.waitForSelector(
      `#synthese-etude[data-calcul="${origineId}"][data-relue="oui"]`, { timeout: 30000 });
    await ouvrirVarianteDe(origineId, etat.request);
    await page.click("#etape-ferraillage");
    await page.fill("#vc-nb", "5");
    const variante = await lancerEtude();
    exige(variante.calculation_id !== origineId && variante.calculation_id !== identique.calculation_id,
          "la variante modifiee n'a pas recu son propre identifiant");
    exige(variante.derived_from_calculation_id === origineId,
          `la variante nomme « ${variante.derived_from_calculation_id} » `
          + `au lieu de son origine ${origineId}`);
    exige(variante.status === "passed", `la variante n'a pas abouti: ${variante.status}`);
    exige(variante.is_exploratory === true, "la variante n'est pas exploratoire");
    //: UNE MODIFICATION VOLONTAIRE NE CHANGE QUE LES DONNEES CONCERNEES: le
    //: nombre de barres, et rien d'autre, ni dans les entrees gelees ni dans
    //: la requete (hors le lien d'origine, qui differe par nature).
    const ecartsEntrees = ecarts(etat.inputs, variante.inputs);
    exige(ecartsEntrees.join(",") === "bars.count",
          `la variante modifiee differe de l'origine sur: ${ecartsEntrees.join(", ")} `
          + "(attendu: bars.count seulement)");
    const ecartsRequete = ecarts(etat.request, variante.request);
    exige(ecartsRequete.join(",") === "bars.count,derived_from_calculation_id",
          `la requete de la variante differe sur: ${ecartsRequete.join(", ")}`);
    exige(variante.inputs?.bars?.count === 5, "la variante n'a pas 5 barres");
    exige(variante.engineering_inputs_hash !== etat.engineering_inputs_hash,
          "cinq barres au lieu de quatre devraient changer l'empreinte des entrees");
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
    await attendreLignes(lignesAvant + 2);

    etape("B. capture de la variante, puis sa note PDF");
    const captureVariante = join(SORTIE, "etude-variante.png");
    await page.locator("#synthese-etude").screenshot({ path: captureVariante });
    const pdfVariante = await telecharger("#etude-note-pdf", "note-de-calcul.variante.pdf");
    exige(pdfVariante.octets.subarray(0, 5).toString() === "%PDF-", "pas un PDF");

    // -- C. LES PARAMETRES AVANCES, ET LEUR VARIANTE IDENTIQUE ----------------
    etape("C. une etude avec les parametres avances: XF1 + classe associee XC3, "
          + "b_eff/b_w = 1, coefficients d'ancrage, M_char = 150 kN·m");
    //: LA SAISIE SE DETACHE DE L'ORIGINE: les valeurs restent, le lien non.
    //: Ce qui part maintenant est une etude INITIALE.
    await page.click("#variante-detacher");
    await page.waitForFunction(() => !document.querySelector("#variante-origine"),
                               null, { timeout: 15000 });
    await page.click("#etape-section");
    await page.fill("#vc-beff", "1");
    await page.click("#etape-materiaux");
    await page.selectOption("#vc-expo", "XF1");
    await page.selectOption("#vc-wmax", "XC3");
    //: XF1 IMPOSE LA LIMITATION DE CONTRAINTE DU §7.2(2), que XC3 n'imposait
    //: pas: sous 180 kN·m caracteristiques, la section rougit a 110,7 % — et
    //: le moteur le dit, il ne rabote rien. Le cas d'essai porte 150 kN·m, un
    //: chargement different, pour que l'etude avancee et sa variante soient
    //: des etudes qui concluent.
    await page.click("#etape-sollicitations");
    await page.fill("#vc-mchar", "150");
    await page.click("#etape-ferraillage");
    await page.fill("#vc-nb", "4");
    if (!(await page.$eval("#ancrage-coefficients", (d) => d.open))) {
      await page.click("#ancrage-coefficients > summary");
    }
    const ALPHAS_ESSAI = ["1", "0.9", "1", "1", "1", "1"];
    for (const [i, v] of ALPHAS_ESSAI.entries()) await page.fill(`#vc-alpha${i + 1}`, v);
    const avancee = await lancerEtude();
    exige(!avancee.derived_from_calculation_id,
          "une saisie detachee de son origine est partie comme variante");
    exige(avancee.status === "passed", `l'etude avancee n'a pas abouti: ${avancee.status}`);
    const entreesAvancees = {
      exposure_class: avancee.inputs?.exposure_class,
      w_max_associated_class: avancee.inputs?.w_max_associated_class,
      b_eff_over_b_w: avancee.inputs?.b_eff_over_b_w,
      anchorage_coefficients: avancee.inputs?.anchorage_coefficients,
      M_char: avancee.inputs?.M_char,
    };
    const attenduesAvancees = {
      exposure_class: "XF1", w_max_associated_class: "XC3", b_eff_over_b_w: 1,
      anchorage_coefficients: Object.fromEntries(
        ALPHAS.map((a, i) => [a, Number(ALPHAS_ESSAI[i])])),
      M_char: avancee.inputs?.M_char,
    };
    exige(String(avancee.inputs?.M_char ?? "").startsWith("150"),
          `M_char de l'etude avancee: « ${avancee.inputs?.M_char} », attendu 150 kN·m`);
    const ecartsAvancees = ecarts(attenduesAvancees, entreesAvancees);
    exige(ecartsAvancees.length === 0,
          `les parametres avances ne sont pas dans les entrees gelees: ${ecartsAvancees.join(", ")}`);
    exige(ecarts(attenduesAvancees.anchorage_coefficients,
                 avancee.request?.anchorage_coefficients).length === 0
          && avancee.request?.w_max_associated_class === "XC3"
          && avancee.request?.b_eff_over_b_w === 1,
          "la requete gelee de l'etude avancee ne porte pas les parametres avances");
    //: ET L'ECRAN LES MONTRE, dans les entrees de l'etude: rien de ce qui a
    //: servi au calcul n'est invisible.
    await page.evaluate(() => document.querySelectorAll("#synthese-etude details")
      .forEach((d) => { d.open = true; }));
    for (const [cle, attendu] of [["w_max_associated_class", "XC3"],
                                  ["b_eff_over_b_w", "1"],
                                  ["anchorage_coefficients.alpha_2", "0.9"]]) {
      const affichee = (await page.locator(`tr[data-entree="${cle}"] td`).innerText()).trim();
      exige(affichee === attendu,
            `entree « ${cle} »: affichee « ${affichee} », attendue « ${attendu} »`);
    }
    await attendreLignes(lignesAvant + 3);

    etape("C. sa variante identique: les champs avances repris, memes empreintes");
    await ouvrirVarianteDe(avancee.calculation_id, avancee.request);
    //: LES COEFFICIENTS REPRIS SONT DEPLIES: une valeur reprise ne se cache pas.
    await page.click("#etape-ferraillage");
    exige(await page.$eval("#ancrage-coefficients", (d) => d.open),
          "les coefficients d'ancrage repris ne sont pas deplies");
    const avanceeIdentique = await lancerEtude();
    exige(avanceeIdentique.derived_from_calculation_id === avancee.calculation_id,
          "la variante de l'etude avancee ne nomme pas son origine");
    exige(avanceeIdentique.engineering_inputs_hash === avancee.engineering_inputs_hash
          && avanceeIdentique.calculation_fingerprint === avancee.calculation_fingerprint,
          "la variante identique de l'etude avancee n'a pas ses empreintes");
    const ecartsAvanceeIdentique = ecarts(avancee.inputs, avanceeIdentique.inputs);
    exige(ecartsAvanceeIdentique.length === 0,
          `la variante de l'etude avancee a perdu: ${ecartsAvanceeIdentique.join(", ")}`);
    await attendreLignes(lignesAvant + 4);

    // -- D. L'HISTORIQUE DIT LA FILIATION, ET MENE DANS LES DEUX SENS ---------
    etape("D. « Rouvrir l'etude d'origine » depuis la synthese de la variante avancee");
    const relectureD = page.waitForResponse(
      (r) => r.url().includes(`/beam-verifications/${avancee.calculation_id}`)
             && r.request().method() === "GET", { timeout: 60000 });
    await page.click("#rouvrir-origine");
    exige((await relectureD).status() === 200, "la relecture de l'etude avancee a echoue");
    await page.waitForSelector(
      `#synthese-etude[data-calcul="${avancee.calculation_id}"][data-relue="oui"]`,
      { timeout: 30000 });

    etape("D. l'historique distingue etude initiale et variante, et compte les variantes");
    const ligneOrigine = `tr[data-calcul="${origineId}"]`;
    const ligneVariante = `tr[data-calcul="${variante.calculation_id}"]`;
    exige((await page.getAttribute(ligneVariante, "data-origine")) === origineId,
          "la ligne d'historique de la variante ne nomme pas son origine");
    exige((await page.getAttribute(ligneOrigine, "data-origine")) === null,
          "la ligne d'historique de l'etude initiale se dit variante");
    exige((await page.locator(`${ligneVariante} .etiquette`).innerText()).trim() === "variante",
          "la ligne de la variante ne porte pas l'etiquette « variante »");
    exige((await page.locator(`${ligneOrigine} .etiquette`).innerText()).trim() === "étude initiale",
          "la ligne de l'origine ne porte pas l'etiquette « étude initiale »");
    //: LE COMPTE VIENT DU SERVEUR: au moins la variante identique et la
    //: variante modifiee (davantage si ce parcours a deja tourne sur l'etude).
    const nbVariantes = Number(await page.getAttribute(ligneOrigine, "data-variantes"));
    exige(nbVariantes >= 2, `l'origine compte ${nbVariantes} variante(s), attendu au moins 2`);
    exige((await page.locator(`${ligneOrigine} details summary`).innerText()).trim()
            === `${nbVariantes} variantes`,
          "le nombre de variantes affiche n'est pas celui du serveur");
    exige((await page.locator(`${ligneVariante}`).innerText()).includes(origineId.slice(0, 8)),
          "la ligne de la variante ne montre pas l'identifiant court de son origine");

    etape("D. de la variante a l'origine par l'historique: ses verdicts du premier jour");
    const lancesAvantRetour = calculsLances;
    const relectureO = page.waitForResponse(
      (r) => r.url().includes(`/beam-verifications/${origineId}`)
             && r.request().method() === "GET", { timeout: 60000 });
    await page.click(`#origine-${variante.calculation_id}`);
    const origineRelue = await (await relectureO).json();
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

    etape("D. de l'origine a sa variante par l'historique: les verdicts de la variante");
    await page.click(`#variantes-${origineId} > summary`);
    const relectureV = page.waitForResponse(
      (r) => r.url().includes(`/beam-verifications/${variante.calculation_id}`)
             && r.request().method() === "GET", { timeout: 60000 });
    await page.click(`#rouvrir-variante-${variante.calculation_id}`);
    exige((await relectureV).status() === 200, "la relecture de la variante a echoue");
    await page.waitForSelector(
      `#synthese-etude[data-calcul="${variante.calculation_id}"][data-relue="oui"]`,
      { timeout: 30000 });
    await exigerChapitres(variante.sections.map((s) => ({
      key: s.key, status: s.status, utilisation: s.utilisation ?? null })));
    await page.waitForSelector(`#etude-derivee[data-origine="${origineId}"]`,
                               { timeout: 15000 });
    exige(calculsLances === lancesAvantRetour,
          "passer de la variante a l'origine et retour a lance un calcul");

    etape("D. changement de projet: l'ecran ne montre plus rien du dossier precedent");
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

    etape("D. deconnexion: plus de synthese, plus d'historique, plus de projet");
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
    const resume = (e) => ({
      calculation_id: e.calculation_id,
      derived_from_calculation_id: e.derived_from_calculation_id ?? null,
      engineering_inputs_hash: e.engineering_inputs_hash,
      calculation_fingerprint: e.calculation_fingerprint,
    });
    writeFileSync(ETAT, JSON.stringify({
      ...etat,
      variante_identique: {
        ...resume(identique),
        memes_entrees_que_l_origine: true,
      },
      variante: {
        creee_le: new Date().toISOString(),
        ...resume(variante),
        modification: "bars.count 4 -> 5",
        ecarts_avec_l_origine: ecartsEntrees,
        sections: variante.sections.map((s) => ({
          key: s.key, status: s.status, utilisation: s.utilisation ?? null,
        })),
        capture: captureVariante,
        pdf: { fichier: pdfVariante.fichier, taille: pdfVariante.taille,
               sha256: pdfVariante.sha256, deliverable_id: pdfVariante.deliverable_id },
      },
      etude_avancee: {
        ...resume(avancee),
        entrees: entreesAvancees,
        variante_identique: resume(avanceeIdentique),
      },
    }, null, 2) + "\n");
    console.log("");
    console.log(`A. variante identique ${identique.calculation_id}: memes entrees metier et `
                + "memes empreintes que l'origine, identifiant et lien differents.");
    console.log(`B. variante ${variante.calculation_id} depuis ${origineId}: seul bars.count `
                + "differe (4 -> 5); origine rouverte intacte.");
    console.log(`C. etude avancee ${avancee.calculation_id} (XF1 + XC3, b_eff/b_w = 1, `
                + `alpha_2 = 0,9, M_char 150) et sa variante identique ${avanceeIdentique.calculation_id}.`);
    console.log("D. changement de projet et deconnexion effacent l'ecran.");
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
