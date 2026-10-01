/**
 * LA LECTURE DES PLANS, DEPUIS UN NAVIGATEUR RÉEL.
 *
 * CE QUE CE PARCOURS ÉPROUVE, ET QUE `test_documents_postgres.py` NE PEUT PAS
 * --------------------------------------------------------------------------
 * Le harnais d'API construit ses requêtes lui-même : il ne dit rien de ce que
 * l'ÉCRAN envoie — un fichier en octets bruts, une décision sans nom ni date,
 * une étude dont la provenance ne survit qu'à des champs non modifiés —, ni de
 * ce qui reste après un F5.
 *
 * LES DOUZE FAITS
 * ----------------
 *   1. A se connecte et crée un projet ; le panneau des pièces dit qu'il n'y
 *      en a aucune, et l'étude guidée reste entière ;
 *   2. un fichier qui n'est ni PDF, ni DXF, ni DWG est refusé (415), avec un
 *      motif écrit, et n'apparaît pas dans la liste ;
 *   3. le plan PDF part en OCTETS BRUTS (`application/octet-stream`), et sa
 *      lecture propose des valeurs — aucune confirmée ;
 *   4. la revue s'ouvre et dit sous quel nom A décidera ;
 *   5. confirmer, corriger (avec motif), rejeter : chaque geste part sans nom
 *      ni date, et la ligne revient décidée, au nom de l'adhésion ;
 *   6. une ligne décidée n'offre plus de geste — la décision est définitive ;
 *   7. « Reporter dans l'étude » remplit les champs du repère P1 dans
 *      l'unité de chaque champ, et chaque champ reporté dit son origine ;
 *   8. le lancement envoie la provenance des seuls champs reportés, et le
 *      serveur la réécrit au nom de la décision enregistrée ;
 *   9. modifier un champ reporté retire son origine : la valeur redevient une
 *      saisie, et ne part plus comme extraite ;
 *  10. après un RECHARGEMENT COMPLET, la pièce et ses décomptes sont là ;
 *  11. la pièce téléchargée porte les octets exacts déposés ;
 *  12. la page ne crie nulle part, hors le refus 415 provoqué exprès.
 *
 * LES COMPTES ET LE PLAN SONT FICTIFS ; la base est détruite à la fin du
 * harnais. Aucune décision prise ici n'engage personne.
 */
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";

import { chargerChromium, cheminChromium } from "./playwright.mjs";

const WEB = process.env.EUROSTRUCT_WEB || "http://localhost:3000";
const API = process.env.EUROSTRUCT_API || "http://127.0.0.1:8000";
const PLAN = process.env.EUROSTRUCT_E2E_PLAN_PDF || "";
const FAUX = process.env.EUROSTRUCT_E2E_PIECE_REFUSEE || "";
const TELECHARGEMENTS = process.env.EUROSTRUCT_E2E_TELECHARGEMENTS || "/tmp";

const A = { courriel: "a@fictif.invalid", mdp: "FICTIF-A", nom: "FICTIF Ing. A" };

const echecs = [];
const exige = (ok, message) => { if (!ok) echecs.push(message); };
const bilan = [];
let etapeCourante = "demarrage";
const ici = (nom) => { etapeCourante = nom; };

if (!PLAN || !FAUX) {
  console.log("NON EXECUTE: EUROSTRUCT_E2E_PLAN_PDF et EUROSTRUCT_E2E_PIECE_REFUSEE "
              + "sont poses par db/test/parcours_livrable.sh.");
  process.exit(4);
}

const chromium = await chargerChromium();
const chrome = cheminChromium();
if (!chromium || !chrome) {
  console.log(`NON EXECUTE: ${!chromium ? "Playwright introuvable" : "aucun binaire Chromium"}.`);
  process.exit(4);
}

const nav = await chromium.launch({ executablePath: chrome, args: ["--no-sandbox"] });
const ctx = await nav.newContext({ acceptDownloads: true });
const page = await ctx.newPage();

// ------------------------------------------------- ce que la page a crié
//: TOUT EST COLLECTE, RIEN N'EST FILTRE A LA COLLECTE (meme regle que
//: `parcours_verification.mjs`). Le seul refus attendu — le 415 du faux
//: fichier — est consomme par le geste qui le provoque, sur son chemin.
const criees = [];
page.on("pageerror", (e) => criees.push({ texte: `erreur de page: ${e.message}`, url: "" }));
page.on("console", (m) => {
  if (m.type() !== "error") return;
  criees.push({ texte: `console: ${m.text()}`, url: m.location()?.url ?? "" });
});
const enClair = (c) => (c.url ? `${c.texte} [${c.url}]` : c.texte);

async function consommerRefus(depuis, statut, chemin, quoi) {
  const motif = new RegExp(`status of ${statut}\\b`);
  const correspond = (c) => motif.test(c.texte) && c.url.includes(chemin);
  const limite = Date.now() + 8000;
  while (Date.now() < limite && !criees.slice(depuis).some(correspond)) {
    await page.waitForTimeout(100);
  }
  await page.waitForTimeout(250);
  const nouveaux = criees.slice(depuis);
  const attendus = nouveaux.filter(correspond);
  const autres = nouveaux.filter((c) => !correspond(c));
  exige(attendus.length === 1, `${quoi}: ${attendus.length} refus ${statut}, 1 attendu`);
  exige(autres.length === 0,
        `${quoi}: cri(s) inattendu(s) — ${autres.slice(0, 3).map(enClair).join(" | ")}`);
  criees.length = depuis;
  for (const c of autres) criees.push(c);
}

// --------------------------------------------------- ce qui part vers l'API
const requetes = [];
page.on("request", (r) => {
  if (!r.url().startsWith(API)) return;
  requetes.push({ methode: r.method(), url: r.url(), entetes: r.headers(),
                  corps: r.postData() ?? null });
});
function derniere(motif, methode) {
  for (let i = requetes.length - 1; i >= 0; i--) {
    if (requetes[i].url.includes(motif) && requetes[i].methode === methode) return requetes[i];
  }
  return null;
}

async function corpsDe(motif, methode, action) {
  const attente = page.waitForResponse(
    (r) => r.url().includes(motif) && r.request().method() === methode,
    { timeout: 90000 });
  await action();
  const reponse = await attente;
  let corps = null;
  let illisible = null;
  try {
    corps = await reponse.json();
  } catch (cause) {
    illisible = String(cause).split("\n")[0];
  }
  return { statut: reponse.status(), corps, illisible };
}

async function connecter({ courriel, mdp }) {
  await page.fill("#courriel", courriel);
  await page.fill("#mdp", mdp);
  const delivre = page.waitForResponse(
    (r) => r.url().includes("/auth/v1/token") && r.request().method() === "POST",
    { timeout: 15000 });
  await page.click("#connecter");
  await delivre;
  await page.waitForSelector("#deconnecter", { timeout: 15000 });
  await page.waitForSelector("#projet", { timeout: 15000 });
}

const ligne = (categorie, texte) =>
  page.locator(`#revue-tableau tr[data-categorie="${categorie}"]`
               + (texte ? `:has-text("${texte}")` : "")).first();

async function decider(categorie, texte, bouton, avant = async () => {}) {
  const l = ligne(categorie, texte);
  await l.locator(`button:has-text("${bouton}")`).click();
  await avant();
  return l;
}

let projetId = "";
const planOctets = await readFile(PLAN);
const planEmpreinte = createHash("sha256").update(planOctets).digest("hex");

try {
  // 1 ─ CONNEXION, PROJET, PANNEAU VIDE ────────────────────────────────────
  ici("connexion de A et creation du projet");
  await page.goto(WEB, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#connecter", { timeout: 20000 });
  await page.waitForTimeout(1000);
  exige(criees.length === 0, "la page a crie au chargement: "
        + criees.slice(0, 3).map(enClair).join(" | "));
  await connecter(A);
  await page.click("text=Nouveau projet");
  await page.fill("#p-nom", "FICTIF — Lecture des plans");
  await page.fill("#p-ref", "FICTIF-LDP-NAV");
  await page.fill("#p-region", "Wallonie");
  await page.fill("#p-date", "2024-03-01");
  const cree = await corpsDe("/v1/projects", "POST", () => page.click("text=Créer le projet"));
  exige(cree.statut === 201, `la creation du projet a rendu ${cree.statut}`);
  projetId = cree.corps?.project_id ?? "";
  await page.selectOption("#projet", projetId);
  await page.waitForSelector("#documents-du-projet", { timeout: 15000 });
  await page.waitForSelector("#documents-vide", { timeout: 15000 });
  exige(await page.isVisible("#lancer-verification"),
        "l'etude guidee doit rester disponible sans aucune piece");

  // 2 ─ UN FORMAT INCONNU EST REFUSE, ET N'APPARAIT PAS ───────────────────
  ici("un format inconnu est refuse");
  const avantFaux = criees.length;
  await page.setInputFiles("#depot-fichier", FAUX);
  const refuse = await corpsDe("/documents", "POST", () => page.click("#depot-envoyer"));
  exige(refuse.statut === 415, `un faux PDF a rendu ${refuse.statut}, 415 attendu`);
  await page.waitForSelector("#documents-message", { timeout: 15000 });
  const motif415 = await page.innerText("#documents-message");
  exige(/PDF|DXF|DWG/.test(motif415), `le motif du refus ne nomme pas les formats: « ${motif415} »`);
  exige(await page.isVisible("#documents-vide"), "un depot refuse est apparu dans la liste");
  await consommerRefus(avantFaux, 415, "/documents", "depot d'un format inconnu");

  // 3 ─ LE PLAN PART EN OCTETS BRUTS, ET SA LECTURE PROPOSE ─────────────────
  ici("depot du plan PDF");
  await page.selectOption("#depot-nature", "formwork_drawing");
  await page.setInputFiles("#depot-fichier", PLAN);
  //: CE QUE LA BASE A RETENU, PAS SEULEMENT CE QUE LE DEPOT A REPONDU. La
  //: liste que l'ecran relit apres le depot vient de PostgreSQL; c'est elle
  //: qui porte les faits. Le corps de la reponse au depot est compare quand
  //: Chromium le rend lisible — il ne le rend pas toujours pour une requete
  //: dont le corps est un fichier, et le parcours le dit plutot que de le taire.
  const listeApresDepot = page.waitForResponse(
    (r) => new URL(r.url()).pathname === `/v1/projects/${projetId}/documents`
      && r.request().method() === "GET",
    { timeout: 90000 });
  const depot = await corpsDe("/documents", "POST", () => page.click("#depot-envoyer"));
  exige(depot.statut === 201, `le depot a rendu ${depot.statut}`);
  const envoye = derniere("/documents", "POST");
  exige(envoye?.entetes?.["content-type"] === "application/octet-stream",
        `le fichier n'est pas parti en octets bruts (${envoye?.entetes?.["content-type"]})`);
  exige(!(envoye?.entetes?.["content-type"] ?? "").includes("multipart"),
        "le depot ne doit pas etre un formulaire multipart");
  const liste = await (await listeApresDepot).json().catch(() => null);
  const doc = (liste?.documents ?? []).find((d) => d.filename === "FICTIF plan R+1.pdf") ?? {};
  exige((liste?.documents ?? []).length === 1,
        `${(liste?.documents ?? []).length} piece(s) en base apres le depot, 1 attendue`);
  exige(doc.analysis_status === "analyse", `statut d'analyse « ${doc.analysis_status} »`);
  exige(doc.proposed_count >= 15,
        `${doc.proposed_count} valeurs proposees en base, au moins 15 attendues`);
  exige(doc.confirmed_count === 0 && doc.corrected_count === 0 && doc.rejected_count === 0,
        "une valeur est decidee sans decision");
  if (depot.corps) {
    exige(depot.corps.extractions_created === doc.proposed_count
          && depot.corps.document?.document_id === doc.document_id,
          "la reponse au depot ne dit pas ce que la base a retenu");
  } else {
    bilan.push(`depot       corps de reponse non relu par Chromium (${depot.illisible})`);
  }

  // 4 ─ LA REVUE S'OUVRE ET DIT SOUS QUEL NOM ──────────────────────────────
  ici("ouverture de la revue");
  await page.waitForSelector("#revue-tableau", { timeout: 15000 });
  exige((await page.innerText("#revue-decideur")).trim() === A.nom,
        "la revue ne dit pas sous quel nom A decide");
  const aRevoir = await page.locator('#revue-tableau tr[data-statut="proposed"]').count();
  exige(aRevoir === doc.proposed_count,
        `${aRevoir} lignes a revoir, ${doc.proposed_count} proposees en base`);

  // 5 ─ CONFIRMER, CORRIGER, REJETER ───────────────────────────────────────
  ici("les decisions");
  const confirmer = async (categorie, texte) => {
    const r = await corpsDe("/decision", "POST",
                            () => decider(categorie, texte, "Confirmer"));
    exige(r.statut === 200, `confirmer ${categorie} a rendu ${r.statut}`);
    exige(r.corps?.confirmed_by_name === A.nom,
          `${categorie}: decide au nom de « ${r.corps?.confirmed_by_name} »`);
    const corps = JSON.parse(derniere("/decision", "POST")?.corps ?? "{}");
    exige(!("confirmed_by_name" in corps) && !("confirmed_at" in corps)
          && !("confirmed_by" in corps),
          `${categorie}: la decision est partie avec un nom ou une date`);
  };
  for (const [categorie, texte] of [
    ["beam_width", null], ["beam_span", null], ["concrete_class", "C30/37"],
    ["steel_grade", "B500B"], ["exposure_class", "XC3"], ["bar_count", null],
    ["bar_diameter", null], ["link_diameter", null], ["link_spacing", null],
  ]) {
    await confirmer(categorie, texte);
  }
  const corrige = await corpsDe("/decision", "POST", () => decider(
    "beam_depth", null, "Corriger", async () => {
      await page.fill("#correction-valeur", "65");
      await page.fill("#correction-unite", "cm");
      await page.fill("#correction-note", "FICTIF: hauteur lue sur la coupe A-A");
      await page.click("#correction-enregistrer");
    }));
  exige(corrige.statut === 200 && corrige.corps?.status === "corrected",
        `la correction a rendu ${corrige.statut} / ${corrige.corps?.status}`);
  exige(corrige.corps?.final_value?.value === 65, "la valeur corrigee n'est pas 65");
  const rejete = await corpsDe("/decision", "POST", () => decider(
    "concrete_cover", null, "Rejeter", async () => {
      await page.fill("#rejet-note", "FICTIF: enrobage du CCTP retenu");
      await page.click("#rejet-enregistrer");
    }));
  exige(rejete.statut === 200 && rejete.corps?.status === "rejected",
        `le rejet a rendu ${rejete.statut} / ${rejete.corps?.status}`);

  // 6 ─ UNE DECISION EST DEFINITIVE ───────────────────────────────────────
  ici("une ligne decidee n'offre plus de geste");
  const largeur = ligne("beam_width");
  exige(await largeur.locator('button:has-text("Confirmer")').count() === 0,
        "une ligne confirmee offre encore « Confirmer »");
  exige((await largeur.innerText()).includes(A.nom), "le nom du decideur n'est pas affiche");

  // 7 ─ LE REPORT DANS L'ETUDE ─────────────────────────────────────────────
  ici("report dans l'etude");
  const rempli = await corpsDe("/extractions/prefill", "GET", () => page.click("#reporter-tout"));
  exige(rempli.statut === 200, `le preremplissage a rendu ${rempli.statut}`);
  await page.waitForSelector("#report-documents", { timeout: 15000 });
  const reportes = await page.getAttribute("#report-documents", "data-reportes");
  exige(reportes === "10", `${reportes} champs reportes, 10 attendus`);
  await page.click("#etape-section");
  exige(await page.inputValue("#vc-b") === "300", `b vaut ${await page.inputValue("#vc-b")}`);
  exige(await page.inputValue("#vc-h") === "650", `h vaut ${await page.inputValue("#vc-h")}`);
  exige(await page.inputValue("#vc-leff") === "6000", "l_eff n'a pas ete reportee en mm");
  const origineB = await page.innerText("#origine-b");
  exige(origineB.includes(A.nom) && origineB.includes("page 1"),
        `l'origine de b ne dit ni la page ni la decision: « ${origineB} »`);
  exige((await page.innerText("#origine-l_eff")).includes("5.3.2.2"),
        "la portee reportee ne porte pas son avertissement");
  await page.click("#etape-ferraillage");
  exige(await page.inputValue("#vc-s") === "150",
        `l'espacement des cadres vaut ${await page.inputValue("#vc-s")}, 150 mm attendus`);
  exige(await page.inputValue("#vc-enrobage") === "40",
        "l'enrobage rejete a ete reporte");

  // 8 ─ LE LANCEMENT PORTE LA PROVENANCE, LE SERVEUR LA REECRIT ─────────────
  ici("lancement avec provenance");
  await page.click("#etape-service");
  await page.fill("#vc-phicreep", "2.0");
  await page.selectOption("#vc-systeme", "simply_supported");
  await page.click("#etape-mode");
  await page.uncheck("#vc-strict");
  await page.check("#vc-assume");
  const etude = await corpsDe("/beam-verifications", "POST",
                              () => page.click("#lancer-verification"));
  exige(etude.statut === 201, `l'etude a rendu ${etude.statut}`);
  const requete = JSON.parse(derniere("/beam-verifications", "POST")?.corps ?? "{}");
  const chemins = Object.keys(requete.provenance ?? {}).sort();
  exige(chemins.length === 10 && chemins.includes("geometry.b") && !chemins.includes("cover"),
        `provenance envoyee pour: ${chemins.join(", ")}`);
  exige(etude.corps?.request?.provenance?.["geometry.h"]?.confirmed_by === A.nom,
        "le serveur n'a pas rendu la provenance au nom de la decision");

  // 9 ─ MODIFIER UN CHAMP REPORTE EN FAIT UNE SAISIE ───────────────────────
  ici("modifier un champ reporte retire son origine");
  await page.click("#etape-section");
  await page.fill("#vc-b", "310");
  exige(await page.locator("#origine-b").count() === 0,
        "l'origine de b est restee apres modification");
  const seconde = await corpsDe("/beam-verifications", "POST",
                                () => page.click("#lancer-verification"));
  exige(seconde.statut === 201, `la seconde etude a rendu ${seconde.statut}`);
  const requete2 = JSON.parse(derniere("/beam-verifications", "POST")?.corps ?? "{}");
  exige(!("geometry.b" in (requete2.provenance ?? {})),
        "b modifie est reparti avec une provenance");
  exige("geometry.h" in (requete2.provenance ?? {}),
        "les autres champs reportes ont perdu leur provenance");

  // 10 ─ APRES F5, LA PIECE ET SES DECOMPTES ───────────────────────────────
  ici("rechargement complet");
  //: AUCUN JETON N'EST PERSISTE: le F5 coute la session, et se reconnecter en
  //: fait partie. Ce qui revient ensuite ne peut venir que de la base.
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.waitForSelector("#connecter", { timeout: 20000 });
  await connecter(A);
  await page.selectOption("#projet", projetId);
  const ligneDoc = page.locator(`#document-${doc.document_id}`);
  await ligneDoc.waitFor({ timeout: 15000 });
  const decomptes = await ligneDoc.locator("td.decomptes").innerText();
  exige(/9 confirmée/.test(decomptes) && /1 corrigée/.test(decomptes)
        && /1 rejetée/.test(decomptes), `decomptes apres F5: « ${decomptes} »`);

  // 11 ─ LA PIECE TELECHARGEE EST CELLE DEPOSEE ────────────────────────────
  ici("telechargement de la piece");
  const [telechargement] = await Promise.all([
    page.waitForEvent("download", { timeout: 15000 }),
    ligneDoc.locator("button.lien").click(),
  ]);
  const chemin = `${TELECHARGEMENTS}/piece-${Date.now()}.pdf`;
  await telechargement.saveAs(chemin);
  const recu = createHash("sha256").update(await readFile(chemin)).digest("hex");
  exige(recu === planEmpreinte && recu === doc.sha256,
        "les octets telecharges ne sont pas ceux deposes");
  bilan.push(`piece       sha256 ${recu} (${planOctets.length} octets)`);
  bilan.push(`etude       ${etude.corps?.calculation_id} — 10 entrees d'origine documentaire`);

  // 12 ─ LA PAGE N'A CRIE NULLE PART ───────────────────────────────────────
  exige(criees.length === 0, "la page a crie: " + criees.slice(0, 4).map(enClair).join(" | "));
} catch (cause) {
  echecs.push(`exception a l'etape « ${etapeCourante} »: ${cause}`);
  try {
    for (const sel of ["#documents-message", "#revue-message", "#pourquoi-bloque",
                       "[role=alert]"]) {
      const n = await page.locator(sel).count();
      for (let i = 0; i < Math.min(n, 3); i++) {
        echecs.push(`  ecran ${sel}: ${await page.locator(sel).nth(i).innerText()}`);
      }
    }
  } catch { /* la page peut etre morte */ }
} finally {
  await nav.close();
}

if (echecs.length) {
  console.log("ROUGE — parcours lecture des plans depuis le navigateur");
  echecs.forEach((e) => console.log("   - " + e));
  process.exit(1);
}
console.log(
  "ok: A cree un projet; le panneau des pieces dit qu'il n'y en a aucune et "
  + "l'etude reste entiere; un format inconnu est refuse (415) avec un motif "
  + "ecrit, sans apparaitre; le plan PDF part en octets bruts et sa lecture "
  + "propose des valeurs, aucune confirmee; la revue dit sous quel nom A "
  + "decide; confirmer, corriger avec motif et rejeter partent sans nom ni "
  + "date et reviennent au nom de l'adhesion; une ligne decidee n'offre plus "
  + "de geste; le report remplit dix champs du repere P1 dans l'unite de "
  + "chaque champ, chacun dit son origine, la portee porte son avertissement, "
  + "l'enrobage rejete n'est pas reporte; le lancement envoie la provenance "
  + "des seuls champs reportes et le serveur la rend au nom de la decision; "
  + "modifier b retire son origine et b repart comme saisie; apres F5 la piece "
  + "et ses decomptes sont la; la piece telechargee porte les octets deposes; "
  + "la page n'a crie nulle part hors le 415 provoque expres.",
);
bilan.forEach((l) => console.log("   " + l));
