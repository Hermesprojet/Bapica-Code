/**
 * LA RECETTE : LA VERTICALE ENTIÈRE, SUR LA PILE DE PRODUCTION, EN DEUX TEMPS.
 *
 * CE QUE CE PARCOURS ÉPROUVE, ET QUE `parcours_verification.mjs` NE PEUT PAS
 * ---------------------------------------------------------------------------
 * `parcours_verification.mjs` pilote une pile montée à la main : `uvicorn` sur
 * l'hôte, un magasin qui est un répertoire, une base posée par le harnais. Il
 * prouve ce que fait l'écran ; il ne dit rien de ce que fait **l'image**.
 *
 * Celui-ci tourne sur la composition réelle — images construites depuis les
 * seuls fichiers versionnés, PostgreSQL et MinIO en conteneurs, `next build`
 * puis `next start` — et il ajoute le seul geste qu'aucun autre ne fait :
 *
 *     ON ARRÊTE L'API ET L'INTERFACE, ON LES REDÉMARRE, ET ON RELIT.
 *
 * D'où les deux phases. Le harnais lance la première, redémarre les deux
 * services, puis lance la seconde en lui passant l'état écrit par la première.
 * Rien ne survit entre les deux, sauf la base et le magasin : c'est
 * exactement ce qu'on veut mesurer.
 *
 * PHASE « avant »
 *   1. connexion ;  2. projet belge ;  3. saisie guidée en sept étapes ;
 *   4. refus strict, blocages nommés, `w_max` nommé, aucune ligne écrite ;
 *   5. étude exploratoire assumée, cinq chapitres ;
 *   6. aperçu SVG ;  7. note PDF ;  8. plan DXF ;  9. second plan DXF ;
 *  10. F5 et relecture ;  11. étude en échec : rien à produire, rien d'orphelin.
 *
 * PHASE « après » — le même navigateur, une pile redémarrée
 *  12. relecture du calcul : identifiant, empreintes, instantané normatif ;
 *  13. re-téléchargement du PDF et du DXF : mêmes octets ;
 *  14. troisième demande du plan : même empreinte, donc même objet ;
 *  15. l'étude exploratoire reste non finalisable.
 *
 * AUCUNE ÉTUDE PRODUITE ICI N'EST UNE VÉRIFICATION RÉELLE. Les comptes sont
 * fictifs, la composition est jetable, et le registre national reste à 0/29.
 */
import { createHash } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";

import { chargerChromium, cheminChromium } from "./playwright.mjs";

const WEB = process.env.EUROSTRUCT_WEB || "http://127.0.0.1:3031";
const API = process.env.EUROSTRUCT_API || "http://127.0.0.1:8031";
const TELECHARGEMENTS = process.env.EUROSTRUCT_E2E_TELECHARGEMENTS || "/tmp";
const ETAT = process.env.EUROSTRUCT_RECETTE_ETAT || "/tmp/recette-etat.json";
const PHASE = process.env.EUROSTRUCT_RECETTE_PHASE || "avant";

const A = { courriel: "a@fictif.invalid", mdp: "FICTIF-A" };
const REGION = "Wallonie";
const DATE_REF = "2024-03-01";

const echecs = [];
const exige = (ok, message) => { if (!ok) echecs.push(message); };
const bilan = [];

let etapeCourante = `demarrage (phase ${PHASE})`;
const ici = (nom) => { etapeCourante = `${PHASE}: ${nom}`; };

const chromium = await chargerChromium();
const chrome = cheminChromium();
if (!chromium || !chrome) {
  console.log(
    `NON EXECUTE: ${!chromium ? "Playwright introuvable" : "aucun Chromium"}.`);
  process.exit(4);
}

const nav = await chromium.launch({ executablePath: chrome, args: ["--no-sandbox"] });
const ctx = await nav.newContext({ acceptDownloads: true });
const page = await ctx.newPage();

// ---------------------------------------------------------------------------
// LES CRIS DE LA PAGE — collectés sans filtre, tolérés geste par geste.
//
// Aucun filtrage à la collecte: une tolérance globale sur un statut ferait
// disparaître, en même temps que les refus voulus, n'importe quelle
// régression rendant ce statut ailleurs.
// ---------------------------------------------------------------------------
const criees = [];
const enClair = (c) => (c.url ? `${c.texte} [${c.url}]` : c.texte);
page.on("pageerror", (e) => criees.push({ texte: `erreur de page: ${e.message}`, url: "" }));
page.on("console", (m) => {
  if (m.type() !== "error") return;
  criees.push({ texte: `console: ${m.text()}`, url: m.location()?.url ?? "" });
});

/** Consomme les cris d'UN geste: un statut, un chemin, un nombre, rien d'autre. */
async function consommerRefus(depuis, { statut, chemin, nombre = 1 }, quoi) {
  const motif = new RegExp(`status of ${statut}\\b`);
  const correspond = (c) => motif.test(c.texte) && c.url.includes(chemin);
  const limite = Date.now() + 8000;
  while (Date.now() < limite
         && criees.slice(depuis).filter(correspond).length < nombre) {
    await page.waitForTimeout(100);
  }
  await page.waitForTimeout(250);
  const nouveaux = criees.slice(depuis);
  const attendus = nouveaux.filter(correspond);
  const autres = nouveaux.filter((c) => !correspond(c));
  exige(autres.length === 0,
        `${quoi}: cri(s) inattendu(s) — ${autres.slice(0, 3).map(enClair).join(" | ")}`);
  exige(attendus.length === nombre,
        `${quoi}: ${attendus.length} refus ${statut} sur « ${chemin} », ${nombre} attendu(s)`);
  criees.length = depuis;
  for (const c of autres) criees.push(c);
}

async function silence(quoi) {
  await page.waitForTimeout(700);
  exige(criees.length === 0,
        `${quoi}: la page a crie — ${criees.slice(0, 3).map(enClair).join(" | ")}`);
}

// ---------------------------------------------------------------------------
// LES OUTILS DU PARCOURS
// ---------------------------------------------------------------------------
const requetes = [];
page.on("request", (r) => {
  if (!r.url().startsWith(API)) return;
  requetes.push({
    methode: r.method(), url: r.url(),
    autorisation: r.headers()["authorization"] ?? null,
    corps: r.postData() ?? null,
  });
});

function derniereRequete(motif, methode) {
  for (let i = requetes.length - 1; i >= 0; i--) {
    if (requetes[i].url.includes(motif) && requetes[i].methode === methode) {
      return requetes[i];
    }
  }
  return null;
}

async function connecter({ courriel, mdp }) {
  await page.fill("#courriel", courriel);
  await page.fill("#mdp", mdp);
  const delivre = page.waitForResponse(
    (r) => r.url().includes("/auth/v1/token") && r.request().method() === "POST",
    { timeout: 20000 });
  await page.click("#connecter");
  await delivre;
  await page.waitForSelector("#deconnecter", { timeout: 20000 });
  await page.waitForSelector("#projet", { timeout: 20000 });
}

async function corpsDe(motif, methode, action) {
  const attente = page.waitForResponse(
    (r) => r.url().includes(motif) && r.request().method() === methode,
    { timeout: 90000 });
  await action();
  const reponse = await attente;
  return { statut: reponse.status(), corps: await reponse.json().catch(() => null) };
}

function jetonObserve() {
  for (let i = requetes.length - 1; i >= 0; i--) {
    const e = requetes[i].autorisation;
    if (typeof e === "string" && e.startsWith("Bearer ") && e.length > 30) {
      return e.slice(7);
    }
  }
  return "";
}

async function depuisLaPage(chemin, methode = "GET", corps = null) {
  const jeton = jetonObserve();
  if (!jeton) return { statut: 0, corps: null, texte: "aucun jeton observe" };
  return page.evaluate(async ({ chemin, methode, corps, api, jeton }) => {
    const r = await fetch(api + chemin, {
      method: methode,
      headers: {
        Authorization: `Bearer ${jeton}`,
        ...(corps ? { "Content-Type": "application/json" } : {}),
      },
      ...(corps ? { body: JSON.stringify(corps) } : {}),
    });
    const texte = await r.text();
    let json = null;
    try { json = JSON.parse(texte); } catch { json = null; }
    return { statut: r.status, corps: json, texte: texte.slice(0, 4000) };
  }, { chemin, methode, corps, api: API, jeton });
}

async function empreinteDuTelechargement(declencher) {
  const attente = page.waitForEvent("download", { timeout: 90000 });
  await declencher();
  const fichier = await attente;
  const chemin = `${TELECHARGEMENTS}/${PHASE}-${fichier.suggestedFilename()}`;
  await fichier.saveAs(chemin);
  const octets = await readFile(chemin);
  return {
    nom: fichier.suggestedFilename(),
    taille: octets.length,
    sha256: createHash("sha256").update(octets).digest("hex"),
    texte: octets.toString("utf8"),
  };
}

/** Remplit les sept étapes de l'écran guidé, comme un ingénieur. */
async function remplirLesEtapes({ cadresDiametre = "10",
                                  cadresEspacement = "150" } = {}) {
  await page.click("#etape-section");
  for (const [sel, v] of [["#vc-b", "300"], ["#vc-h", "600"],
                          ["#vc-d", "550"], ["#vc-leff", "6000"]]) {
    await page.fill(sel, v);
  }
  await page.click("#etape-materiaux");
  await page.fill("#vc-beton", "C30/37");
  await page.fill("#vc-acier", "B500B");
  await page.selectOption("#vc-expo", "XC3");

  await page.click("#etape-sollicitations");
  for (const [sel, v] of [["#vc-med", "250"], ["#vc-ved", "300"],
                          ["#vc-mchar", "180"], ["#vc-mqp", "120"]]) {
    await page.fill(sel, v);
  }

  await page.click("#etape-ferraillage");
  await page.fill("#vc-nb", "4");
  await page.fill("#vc-phi", "20");
  await page.fill("#vc-branches", "2");
  await page.fill("#vc-phiw", cadresDiametre);
  await page.fill("#vc-s", cadresEspacement);
  await page.fill("#vc-enrobage", "40");
  await page.fill("#vc-cot", "1.5");
  await page.fill("#vc-ancrage", "800");

  await page.click("#etape-service");
  await page.fill("#vc-phicreep", "2.0");
  await page.selectOption("#vc-systeme", "simply_supported");
}

/** Le SHA-256 que la BASE a enregistré pour ce livrable. */
async function shaEnBase(projetId, livrableId) {
  const r = await depuisLaPage(
    `/v1/projects/${projetId}/deliverables/${livrableId}`);
  return { statut: r.statut, sha: r.corps?.sha256, taille: r.corps?.size_bytes };
}

/**
 * Le SHA-256 des OCTETS que le navigateur reçoit réellement du magasin.
 *
 * ON HACHE DANS LA PAGE, PAS DANS NODE. Le point de la comparaison est
 * « ce que l'utilisateur télécharge » : passer par un client HTTP du harnais
 * mesurerait un autre chemin que celui de l'écran — autre pile TLS, autres
 * en-têtes, autre cache. `crypto.subtle` est disponible parce que
 * `http://127.0.0.1` est un contexte sécurisé pour Chromium.
 */
async function shaTelecharge(projetId, livrableId) {
  const jeton = jetonObserve();
  if (!jeton) return { statut: 0 };
  return page.evaluate(async ({ api, projet, livrable, jeton }) => {
    const r = await fetch(
      `${api}/v1/projects/${projet}/deliverables/${livrable}/download`,
      { headers: { Authorization: `Bearer ${jeton}` } });
    if (!r.ok) return { statut: r.status };
    const octets = await r.arrayBuffer();
    const empreinte = await crypto.subtle.digest("SHA-256", octets);
    return {
      statut: r.status,
      taille: octets.byteLength,
      sha256: [...new Uint8Array(empreinte)]
        .map((b) => b.toString(16).padStart(2, "0")).join(""),
    };
  }, { api: API, projet: projetId, livrable: livrableId, jeton });
}

let etat = {};

try {
  if (PHASE === "apres") {
    etat = JSON.parse(await readFile(ETAT, "utf8"));
  }

  // =====================================================================
  // 1 — LA PAGE S'OUVRE SANS CRIER
  // =====================================================================
  ici("ouverture");
  await page.goto(WEB, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#connecter", { timeout: 30000 });
  await silence("chargement initial");

  ici("connexion");
  await connecter(A);
  await silence("connexion");

  if (PHASE === "avant") {
    // ===================================================================
    // 2 — UN PROJET BELGE
    // ===================================================================
    ici("creation du projet");
    await page.click("text=Nouveau projet");
    await page.fill("#p-nom", "FICTIF — Recette de production");
    await page.fill("#p-ref", "FICTIF-RECETTE");
    await page.fill("#p-region", REGION);
    await page.fill("#p-date", DATE_REF);
    const cree = await corpsDe("/v1/projects", "POST",
                               () => page.click("text=Créer le projet"));
    exige(cree.statut === 201, `la creation a rendu ${cree.statut}`);
    etat.projetId = cree.corps?.project_id ?? "";
    exige(/^[0-9a-f-]{36}$/i.test(etat.projetId),
          `pas d'identifiant de projet: « ${etat.projetId} »`);
    await page.selectOption("#projet", etat.projetId);

    // ===================================================================
    // 3 et 4 — SAISIE GUIDEE, PUIS REFUS STRICT QUI NOMME
    // ===================================================================
    ici("saisie guidee et refus strict");
    await remplirLesEtapes();
    await page.click("#etape-mode");
    exige(await page.isChecked("#vc-strict"),
          "le mode strict n'est pas le defaut");

    const avantRefus = criees.length;
    const refuse = await corpsDe("/beam-verifications", "POST",
                                 () => page.click("#lancer-verification"));
    exige(refuse.statut === 422,
          `la verification stricte a rendu ${refuse.statut}`);
    await consommerRefus(avantRefus,
                         { statut: 422, chemin: "/beam-verifications" },
                         "refus strict");

    await page.waitForSelector("#refus-verification", { timeout: 20000 });
    const texteRefus = await page.locator("#refus-verification").innerText();
    const noms = await page.locator("#refus-verification ul.bloquants li code")
                           .allInnerTexts();
    exige(noms.length > 0 && noms.every((n) => n.trim().length > 0),
          `des parametres bloquants s'affichent sans nom: ${JSON.stringify(noms)}`);

    //: LE MESSAGE EXACT SUR `w_max`, SANS VALEUR INVENTEE.
    //:
    //: La fiche belge de `w_max` dit « NON RELEVE dans le Tableau 7.1N-ANB ».
    //: L'ecran doit le nommer et dire qu'aucune valeur n'y a ete relevee — pas
    //: en proposer une, pas en deduire une de l'EN.
    exige(noms.includes("EN 1992-1-1:w_max"),
          `le refus ne nomme pas w_max: ${JSON.stringify(noms)}`);
    const ligneWmax = await page
      .locator("#refus-verification ul.bloquants li")
      .filter({ hasText: "w_max" }).first().innerText();
    exige(/non relevee/i.test(ligneWmax),
          `la ligne w_max ne dit pas que la valeur n'a pas ete relevee: `
          + `« ${ligneWmax.slice(0, 220)} »`);
    exige(/pending_verification/.test(ligneWmax),
          `la ligne w_max ne donne pas son statut: « ${ligneWmax.slice(0, 220)} »`);
    etat.messageWmax = ligneWmax.replace(/\s+/g, " ").trim();

    //: UN REFUS DE PREFLIGHT N'ECRIT RIEN.
    const apresRefus = await depuisLaPage(
      `/v1/projects/${etat.projetId}/calculations`);
    exige((apresRefus.corps?.calculations ?? []).length === 0,
          "un refus de preflight a laisse une ligne dans l'historique");

    // ===================================================================
    // 5 — L'ETUDE EXPLORATOIRE, CINQ CHAPITRES
    // ===================================================================
    ici("etude exploratoire");
    await remplirLesEtapes();
    await page.click("#etape-mode");
    await page.uncheck("#vc-strict");
    exige(await page.isDisabled("#lancer-verification"),
          "l'exploratoire n'exige pas de choix assume");
    await page.check("#vc-assume");

    const etude = await corpsDe("/beam-verifications", "POST",
                                () => page.click("#lancer-verification"));
    exige(etude.statut === 201, `l'etude a rendu ${etude.statut}`);
    exige(etude.corps?.status === "passed",
          `l'etude n'a pas abouti: ${etude.corps?.status}`);
    exige((etude.corps?.sections ?? []).length === 5,
          `${(etude.corps?.sections ?? []).length} chapitre(s) au lieu de cinq`);
    exige(etude.corps?.is_exploratory === true, "l'etude n'est pas exploratoire");
    exige(etude.corps?.may_be_finalised === false,
          "une etude exploratoire se declare finalisable");

    etat.calculId = etude.corps?.calculation_id;
    etat.empreintes = {
      engineering_inputs_hash: etude.corps?.engineering_inputs_hash,
      ndp_snapshot_id: etude.corps?.ndp_snapshot_id,
      calculation_fingerprint: etude.corps?.calculation_fingerprint,
      execution_identity: etude.corps?.execution_identity,
      max_utilisation: etude.corps?.max_utilisation,
      status: etude.corps?.status,
    };

    await page.waitForSelector("#synthese-etude", { timeout: 30000 });
    for (const cle of ["flexure", "shear", "anchorage", "serviceability",
                       "deflection"]) {
      const ligne = page.locator(`#chapitre-${cle}`);
      exige(await ligne.count() === 1, `chapitre « ${cle} » absent`);
    }
    const pourquoi = await page.locator("#pourquoi-non-finalisable").innerText();
    exige(/exploratoire/.test(pourquoi),
          `l'ecran n'explique pas la non-finalisation: « ${pourquoi.slice(0, 200)} »`);
    exige((await page.locator("#synthese-etude").innerText())
            .includes("NON SIGNABLE"),
          "la mention obligatoire n'est pas affichee");
    exige(await page.locator("#etude-finalisable").count() === 0,
          "l'ecran declare finalisable une etude exploratoire");

    // ===================================================================
    // 6 — L'APERCU SVG
    // ===================================================================
    ici("apercu SVG");
    const apercu = await corpsDe("/deliverables/preview", "POST",
                                 () => page.click("#etude-apercu"));
    exige(apercu.statut === 200, `l'apercu a rendu ${apercu.statut}`);
    await page.waitForSelector("#apercu-du-plan svg", { timeout: 30000 });
    exige((await page.locator("#apercu-du-plan").innerText())
            .includes("APERCU NON CONTRACTUEL"),
          "l'apercu ne se declare pas non contractuel");

    // ===================================================================
    // 7 — LA NOTE PDF
    // ===================================================================
    ici("note PDF");
    let notePdf = null;
    const noteCree = await corpsDe("/deliverables", "POST", async () => {
      notePdf = await empreinteDuTelechargement(
        () => page.click("#etude-note-pdf"));
    });
    exige(noteCree.statut === 201, `la note a rendu ${noteCree.statut}`);
    exige(noteCree.corps?.kind === "calculation_note_pdf",
          `nature « ${noteCree.corps?.kind} »`);
    exige(notePdf.sha256 === noteCree.corps?.sha256,
          "les octets du PDF ne portent pas l'empreinte enregistree");
    exige(notePdf.texte.startsWith("%PDF-"), "le fichier n'est pas un PDF");
    exige(notePdf.taille > 10000,
          `le PDF ne fait que ${notePdf.taille} octets: il est vide ou tronque`);

    //: LES CINQ CHAPITRES SONT DANS LES OCTETS, pas seulement a l'ecran.
    //: Le PDF est ecrit a la main, en WinAnsi non compresse: ses chaines sont
    //: lisibles telles quelles.
    for (const titre of ["Flexion", "Effort tranchant", "Ancrage",
                         "fissures", "che"]) {
      exige(notePdf.texte.includes(titre),
            `le PDF ne porte pas « ${titre} »`);
    }
    exige(notePdf.texte.includes("NON SIGNABLE"),
          "le PDF ne porte pas la mention obligatoire");
    etat.notePdf = { id: noteCree.corps?.deliverable_id,
                     sha256: notePdf.sha256, taille: notePdf.taille };

    // ===================================================================
    // 8 et 9 — LE PLAN DXF, DEUX FOIS
    // ===================================================================
    ici("plan DXF");
    let planDxf = null;
    const planCree = await corpsDe("/deliverables", "POST", async () => {
      planDxf = await empreinteDuTelechargement(
        () => page.click("#etude-plan-dxf"));
    });
    exige(planCree.statut === 201, `le plan a rendu ${planCree.statut}`);
    exige(planCree.corps?.kind === "rebar_drawing_dxf",
          `nature « ${planCree.corps?.kind} »`);
    exige(planDxf.sha256 === planCree.corps?.sha256,
          "les octets du DXF ne portent pas l'empreinte enregistree");
    exige(planDxf.texte.includes("SECTION") && planDxf.texte.includes("ENTITIES"),
          "le fichier n'a pas la structure d'un DXF");
    exige(planDxf.taille > 10000,
          `le DXF ne fait que ${planDxf.taille} octets`);

    //: AUCUN FERRAILLAGE NE PART DU NAVIGATEUR.
    const envoi = derniereRequete("/deliverables", "POST");
    let corpsEnvoye = null;
    try { corpsEnvoye = JSON.parse(envoi?.corps ?? "null"); } catch { /* null */ }
    exige(corpsEnvoye
          && Object.keys(corpsEnvoye).sort().join(",") === "calculation_id,format",
          "le corps envoye porte autre chose que l'identifiant et le format: "
          + `${JSON.stringify(corpsEnvoye).slice(0, 200)}`);

    //: SECONDE DEMANDE: meme empreinte, autre ligne. Un seul objet.
    const planBis = await depuisLaPage(
      `/v1/projects/${etat.projetId}/deliverables`, "POST",
      { calculation_id: etat.calculId, format: "dxf" });
    exige(planBis.statut === 201, `le second plan a rendu ${planBis.statut}`);
    exige(planBis.corps?.sha256 === planCree.corps?.sha256,
          "deux demandes du meme plan donnent deux empreintes");
    exige(planBis.corps?.deliverable_id !== planCree.corps?.deliverable_id,
          "la seconde demande n'a pas cree sa propre ligne");
    etat.planDxf = { id: planCree.corps?.deliverable_id,
                     idBis: planBis.corps?.deliverable_id,
                     sha256: planDxf.sha256, taille: planDxf.taille };

    // ===================================================================
    // 10 — F5 ET RELECTURE
    // ===================================================================
    ici("rechargement complet");
    await page.goto(WEB, { waitUntil: "domcontentloaded" });
    await page.waitForSelector("#connecter", { timeout: 30000 });
    await silence("apres F5");
    await connecter(A);
    await page.selectOption("#projet", etat.projetId);

    const relue = await depuisLaPage(
      `/v1/projects/${etat.projetId}/beam-verifications/${etat.calculId}`);
    exige(relue.statut === 200, `la relecture a rendu ${relue.statut}`);
    for (const [champ, attendu] of Object.entries(etat.empreintes)) {
      exige(relue.corps?.[champ] === attendu,
            `« ${champ} » a change apres F5`);
    }

    // ===================================================================
    // 11 — UNE ETUDE EN ECHEC NE PRODUIT RIEN, ET NE LAISSE RIEN
    // ===================================================================
    ici("etude en echec");
    await remplirLesEtapes({ cadresDiametre: "6", cadresEspacement: "300" });
    await page.click("#etape-mode");
    await page.uncheck("#vc-strict");
    await page.check("#vc-assume");
    const echouee = await corpsDe("/beam-verifications", "POST",
                                  () => page.click("#lancer-verification"));
    exige(echouee.statut === 201,
          `l'etude en echec a rendu ${echouee.statut}`);
    exige(echouee.corps?.status === "failed",
          `l'etude aux cadres insuffisants a rendu « ${echouee.corps?.status} »`);
    await page.waitForSelector("#pourquoi-pas-de-document", { timeout: 30000 });
    exige(await page.isDisabled("#etude-note-pdf"),
          "une etude en echec laisse produire une note");
    exige(await page.isDisabled("#etude-plan-dxf"),
          "une etude en echec laisse produire un plan");

    const avantForcee = criees.length;
    const forcee = await depuisLaPage(
      `/v1/projects/${etat.projetId}/deliverables`, "POST",
      { calculation_id: echouee.corps?.calculation_id, format: "dxf" });
    exige(forcee.statut === 422,
          `la route a rendu ${forcee.statut} pour un calcul en echec`);
    await consommerRefus(avantForcee, { statut: 422, chemin: "/deliverables" },
                         "plan force sur une etude en echec");

    //: LE COMPTE DES LIGNES, POUR QUE LE HARNAIS COMPARE LES OBJETS.
    const liste = await depuisLaPage(
      `/v1/projects/${etat.projetId}/deliverables`);
    etat.nbLignes = (liste.corps?.deliverables ?? []).length;
    exige(etat.nbLignes === 3,
          `${etat.nbLignes} ligne(s) de livrable au lieu de 3 `
          + "(note PDF + deux demandes du plan)");

    await writeFile(ETAT, JSON.stringify(etat, null, 2), "utf8");
    bilan.push(`projet      ${etat.projetId}`);
    bilan.push(`etude       ${etat.calculId}`);
    for (const [k, v] of Object.entries(etat.empreintes)) {
      bilan.push(`  ${k.padEnd(24)} ${v}`);
    }
    bilan.push(`note PDF    ${etat.notePdf.sha256} (${etat.notePdf.taille} o)`);
    bilan.push(`plan DXF    ${etat.planDxf.sha256} (${etat.planDxf.taille} o)`);
  } else {
    // ===================================================================
    // 12 — APRES REDEMARRAGE: LE CALCUL EST LE MEME
    // ===================================================================
    ici("relecture apres redemarrage");
    await page.selectOption("#projet", etat.projetId);

    const relue = await depuisLaPage(
      `/v1/projects/${etat.projetId}/beam-verifications/${etat.calculId}`);
    exige(relue.statut === 200,
          `la relecture apres redemarrage a rendu ${relue.statut}`);
    exige(relue.corps?.calculation_id === etat.calculId,
          "l'identifiant du calcul a change apres redemarrage");
    for (const [champ, attendu] of Object.entries(etat.empreintes)) {
      exige(relue.corps?.[champ] === attendu,
            `« ${champ} » a change apres redemarrage: `
            + `${JSON.stringify(relue.corps?.[champ])} != ${JSON.stringify(attendu)}`);
    }
    exige(relue.corps?.may_be_finalised === false,
          "l'etude exploratoire est devenue finalisable apres redemarrage");
    exige(relue.corps?.is_exploratory === true,
          "l'etude a perdu son caractere exploratoire");

    // ===================================================================
    // 13 — LES MEMES OCTETS, DEPUIS LA BASE ET DEPUIS LE MAGASIN
    // ===================================================================
    ici("re-telechargement des livrables");
    for (const [nom, ref] of [["note PDF", etat.notePdf],
                              ["plan DXF", etat.planDxf]]) {
      const enBase = await shaEnBase(etat.projetId, ref.id);
      exige(enBase.statut === 200,
            `${nom}: la relecture de la ligne a rendu ${enBase.statut}`);
      exige(enBase.sha === ref.sha256,
            `${nom}: le SHA en base a change apres redemarrage`);
      exige(enBase.taille === ref.taille,
            `${nom}: la taille en base a change apres redemarrage`);

      //: ET LES OCTETS EUX-MEMES, tels que le navigateur les recoit.
      const recu = await shaTelecharge(etat.projetId, ref.id);
      exige(recu.statut === 200,
            `${nom}: le telechargement a rendu ${recu.statut}`);
      exige(recu.sha256 === ref.sha256,
            `${nom}: les octets telecharges apres redemarrage ont change `
            + `(${recu.sha256?.slice(0, 12)} vs ${ref.sha256.slice(0, 12)})`);
      exige(recu.taille === ref.taille,
            `${nom}: la taille telechargee a change `
            + `(${recu.taille} vs ${ref.taille})`);
    }

    // ===================================================================
    // 14 — TROISIEME DEMANDE DU PLAN: MEME EMPREINTE
    // ===================================================================
    ici("troisieme demande du plan");
    const planTer = await depuisLaPage(
      `/v1/projects/${etat.projetId}/deliverables`, "POST",
      { calculation_id: etat.calculId, format: "dxf" });
    exige(planTer.statut === 201,
          `le plan reproduit apres redemarrage a rendu ${planTer.statut}`);
    exige(planTer.corps?.sha256 === etat.planDxf.sha256,
          "LE PLAN A CHANGE APRES REDEMARRAGE DE L'API. "
          + `${planTer.corps?.sha256?.slice(0, 16)} au lieu de `
          + `${etat.planDxf.sha256.slice(0, 16)}: un processus neuf ne rend `
          + "pas les memes octets, et le magasin gardera les deux.");
    etat.planTerId = planTer.corps?.deliverable_id;

    bilan.push(`etude relue ${relue.corps?.calculation_id}`);
    bilan.push(`  empreinte du calcul  ${relue.corps?.calculation_fingerprint}`);
    bilan.push(`  instantane normatif  ${relue.corps?.ndp_snapshot_id}`);
    bilan.push(`note PDF    ${etat.notePdf.sha256} (inchangee)`);
    bilan.push(`plan DXF    ${etat.planDxf.sha256} (inchangee, 3 demandes)`);
    await writeFile(ETAT, JSON.stringify(etat, null, 2), "utf8");
  }

  // =====================================================================
  // LE SILENCE, SUR TOUT LE TRAJET
  // =====================================================================
  ici("bilan des cris");
  await silence("l'ensemble du parcours");
} catch (cause) {
  echecs.push(`exception a l'etape « ${etapeCourante} »: ${cause}`);
  try {
    for (const sel of ["#refus-verification", "#pourquoi-bloque",
                       "#pourquoi-pas-de-document", "[role=alert]"]) {
      const n = await page.locator(sel).count();
      for (let i = 0; i < Math.min(n, 2); i++) {
        echecs.push(`  ecran ${sel}: ${await page.locator(sel).nth(i).innerText()}`);
      }
    }
  } catch { /* la page peut etre morte */ }
} finally {
  await nav.close();
}

if (echecs.length) {
  console.log(`ROUGE — recette de production, phase « ${PHASE} »`);
  echecs.forEach((e) => console.log("   - " + e));
  if (criees.length) {
    console.log("   ce que la page a signale:");
    criees.slice(0, 10).forEach((c) => console.log("     · " + enClair(c)));
  }
  process.exit(1);
}
console.log(`ok: recette de production, phase « ${PHASE} »`);
bilan.forEach((l) => console.log("   " + l));
