/**
 * LA GÉOMÉTRIE D'UN DXF, DEPUIS UN NAVIGATEUR RÉEL.
 *
 * CE QUE CE PARCOURS ÉPROUVE
 * ---------------------------
 * Un plan de coffrage DXF qui n'ÉCRIT NULLE PART une portée — ni « Portée P1 »,
 * ni « 6,00 m » — est déposé ; l'écran doit montrer que les portées viennent
 * des traits du dessin, d'où exactement, et les distinguer des valeurs lues
 * dans un texte. Puis une portée MESURÉE, décidée par une personne nommée,
 * entre dans l'étude et dans le calcul avec sa provenance.
 *
 * LES DOUZE FAITS
 * ----------------
 *   1. A se connecte et crée un projet ;
 *   2. le DXF part en octets bruts ; la liste relue dit qu'un modèle
 *      structurel a été reconstruit — poteaux, poutres, travées, dalles, unité ;
 *   3. la revue sépare les sources : « Géométrie du DXF » et « Texte ou cote
 *      du DXF », chacune avec son compte, égal à celui de la base ;
 *   4. le modèle est DESSINÉ : 6 poteaux, 3 poutres, 5 travées, et le tableau
 *      des travées dit P1 : A1 → B1, 600 cm entre axes, 570 cm nu à nu ;
 *   5. aucune portée ne vient d'un texte : filtrées par source, toutes les
 *      portées sont géométriques ;
 *   6. la ligne de P1 dit comment elle a été mesurée — entre quels appuis,
 *      et que la cote du dessin concorde ;
 *   7. « Voir sur le dessin » désigne la travée sur le plan ; un poteau cliqué
 *      sur le plan restreint la revue à ses valeurs, « Tout afficher » rend
 *      la liste entière ;
 *   8. une section de poteau mesurée est corroborée par le texte « C1 30x30 » ;
 *   9. A confirme la portée et la largeur de P1 ; le report remplit l_eff =
 *      6000 mm et b = 300 mm, et l'origine de l_eff dit « géométrie du DXF » et
 *      porte l'avertissement de la portée utile ;
 *  10. le lancement envoie ces deux provenances et le serveur les réécrit au
 *      nom de la décision, en disant la géométrie ;
 *  11. après un RECHARGEMENT COMPLET, le résumé du modèle et les décomptes
 *      sont là ;
 *  12. la page ne crie nulle part.
 *
 * LES COMPTES ET LE PLAN SONT FICTIFS ; la base est détruite à la fin du
 * harnais. Aucune décision prise ici n'engage personne.
 */
import { chargerChromium, cheminChromium } from "./playwright.mjs";

const WEB = process.env.EUROSTRUCT_WEB || "http://localhost:3000";
const API = process.env.EUROSTRUCT_API || "http://127.0.0.1:8000";
const PLAN = process.env.EUROSTRUCT_E2E_PLAN_DXF || "";
const NOM_DU_PLAN = "FICTIF-S-101-coffrage.dxf";
//: FACULTATIF: un dossier ou deposer une capture de la revue et du modele
//: dessine, pour la montrer. Le parcours ne juge rien sur l'image.
const CAPTURES = process.env.EUROSTRUCT_E2E_CAPTURES || "";

const A = { courriel: "a@fictif.invalid", mdp: "FICTIF-A", nom: "FICTIF Ing. A" };

const echecs = [];
const exige = (ok, message) => { if (!ok) echecs.push(message); };
const bilan = [];
let etapeCourante = "demarrage";
const ici = (nom) => { etapeCourante = nom; };

if (!PLAN) {
  console.log("NON EXECUTE: EUROSTRUCT_E2E_PLAN_DXF est pose par db/test/parcours_livrable.sh.");
  process.exit(4);
}

const chromium = await chargerChromium();
const chrome = cheminChromium();
if (!chromium || !chrome) {
  console.log(`NON EXECUTE: ${!chromium ? "Playwright introuvable" : "aucun binaire Chromium"}.`);
  process.exit(4);
}

const nav = await chromium.launch({ executablePath: chrome, args: ["--no-sandbox"] });
const ctx = await nav.newContext();
const page = await ctx.newPage();

//: TOUT EST COLLECTE, RIEN N'EST FILTRE (meme regle que les autres parcours).
const criees = [];
page.on("pageerror", (e) => criees.push({ texte: `erreur de page: ${e.message}`, url: "" }));
page.on("console", (m) => {
  if (m.type() !== "error") return;
  criees.push({ texte: `console: ${m.text()}`, url: m.location()?.url ?? "" });
});
const enClair = (c) => (c.url ? `${c.texte} [${c.url}]` : c.texte);

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
  try { corps = await reponse.json(); } catch { /* corps illisible: dit plus bas */ }
  return { statut: reponse.status(), corps };
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

let projetId = "";

try {
  // 1 ─ CONNEXION ET PROJET ──────────────────────────────────────────────
  ici("connexion de A et creation du projet");
  await page.goto(WEB, { waitUntil: "domcontentloaded" });
  await page.waitForSelector("#connecter", { timeout: 20000 });
  await connecter(A);
  await page.click("text=Nouveau projet");
  await page.fill("#p-nom", "FICTIF — Géométrie d'un DXF");
  await page.fill("#p-ref", "FICTIF-GEO-NAV");
  await page.fill("#p-region", "Wallonie");
  await page.fill("#p-date", "2024-03-01");
  const cree = await corpsDe("/v1/projects", "POST", () => page.click("text=Créer le projet"));
  exige(cree.statut === 201, `la creation du projet a rendu ${cree.statut}`);
  projetId = cree.corps?.project_id ?? "";
  await page.selectOption("#projet", projetId);
  await page.waitForSelector("#documents-vide", { timeout: 15000 });

  // 2 ─ LE DXF PART EN OCTETS BRUTS ; LE MODELE EST RECONSTRUIT ────────────
  ici("depot du DXF");
  await page.selectOption("#depot-nature", "formwork_drawing");
  await page.setInputFiles("#depot-fichier", PLAN);
  const listeApresDepot = page.waitForResponse(
    (r) => new URL(r.url()).pathname === `/v1/projects/${projetId}/documents`
      && r.request().method() === "GET", { timeout: 90000 });
  //: LA REVUE S'OUVRE SEULE APRES LE DEPOT: sa liste est attendue des avant.
  const extractionsLues = page.waitForResponse(
    (r) => r.url().includes("/extractions?") && r.request().method() === "GET",
    { timeout: 90000 });
  const depot = await corpsDe("/documents", "POST", () => page.click("#depot-envoyer"));
  exige(depot.statut === 201, `le depot a rendu ${depot.statut}`);
  exige(derniere("/documents", "POST")?.entetes?.["content-type"] === "application/octet-stream",
        "le DXF n'est pas parti en octets bruts");
  const liste = await (await listeApresDepot).json().catch(() => null);
  const doc = (liste?.documents ?? []).find((d) => d.filename === NOM_DU_PLAN) ?? {};
  exige(doc.format === "dxf" && doc.analysis_status === "analyse",
        `format « ${doc.format} », statut « ${doc.analysis_status} »`);
  exige(doc.has_structure === true, "la liste ne dit pas qu'un modele a ete reconstruit");
  exige(!("structure" in (doc.analysis_report ?? {})),
        "la liste transporte le modele entier au lieu de son resume");
  const comptes = doc.structure_summary?.counts ?? {};
  exige(comptes.columns === 6 && comptes.beams === 3 && comptes.spans === 5
        && comptes.slabs === 2, `resume du modele: ${JSON.stringify(comptes)}`);
  const resume = await page.innerText(`#modele-resume-${doc.document_id}`);
  exige(/6 poteau/.test(resume) && /5 travée/.test(resume) && /cm/.test(resume),
        `le resume affiche ne dit pas le modele: « ${resume} »`);

  // 3 ─ LA REVUE SEPARE LES SOURCES ─────────────────────────────────────────
  ici("les sources dans la revue");
  await page.waitForSelector("#revue-tableau", { timeout: 15000 });
  const extractions = (await (await extractionsLues).json().catch(() => null))?.extractions ?? [];
  const geo = extractions.filter((x) => x.source_type === "geometry");
  const texteDxf = extractions.filter((x) => x.source_type === "cad_text");
  exige(geo.length > 0 && texteDxf.length > 0,
        `${geo.length} valeur(s) geometriques, ${texteDxf.length} de texte DXF`);
  exige(await page.locator('#revue-tableau tr[data-source="geometry"]').count() === geo.length,
        "la revue ne montre pas toutes les valeurs geometriques");
  const sources = await page.innerText("#revue-sources");
  exige(sources.includes(`Géométrie du DXF ${geo.length}`)
        && sources.includes(`Texte ou cote du DXF ${texteDxf.length}`),
        `le resume des sources dit « ${sources} »`);

  // 4 ─ LE MODELE EST DESSINE ──────────────────────────────────────────────
  ici("le modele dessine");
  await page.waitForSelector("#modele-plan", { timeout: 15000 });
  exige(await page.locator("#modele-plan .plan-poteau").count() === 6, "poteaux dessines");
  exige(await page.locator("#modele-plan .plan-poutre").count() === 3, "poutres dessinees");
  exige(await page.locator("#modele-plan .plan-travee").count() === 5, "travees dessinees");
  if (CAPTURES) {
    await page.setViewportSize({ width: 1400, height: 1000 });
    await page.locator("#revue-extractions").screenshot(
      { path: `${CAPTURES}/revue-geometrie-s101.png` });
    bilan.push(`capture     ${CAPTURES}/revue-geometrie-s101.png`);
  }
  const p1 = await page.innerText("#modele-span-1-1");
  exige(/P1/.test(p1) && /A1 → B1/.test(p1) && /600 cm/.test(p1) && /570 cm/.test(p1),
        `la ligne de la travee P1 dit « ${p1} »`);

  // 5 ─ AUCUNE PORTEE NE VIENT D'UN TEXTE ─────────────────────────────────
  ici("les portees viennent du dessin");
  const portees = extractions.filter((x) => x.kind === "beam_span");
  exige(portees.length === 5 && portees.every((x) => x.source_type === "geometry"),
        `portees: ${portees.map((x) => `${x.element_label}/${x.source_type}`).join(", ")}`);
  await page.selectOption("#revue-source", "geometry");
  exige(await page.locator('#revue-tableau tbody tr:not([data-source="geometry"])').count() === 0,
        "le filtre par source laisse passer d'autres sources");
  exige(await page.locator('#revue-tableau tr[data-categorie="beam_span"]').count() === 5,
        "les cinq portees geometriques ne sont pas toutes listees");

  // 6 ─ LA LIGNE DE P1 DIT COMMENT ELLE A ETE MESUREE ─────────────────────
  ici("la mesure expliquee");
  const spanP1 = portees.find((x) => x.element_label === "P1");
  const ligneP1 = page.locator(`#extraction-${spanP1?.extraction_id}`);
  const texteP1 = await ligneP1.innerText();
  exige(/entre les centres de poteau C1 en A1 et de poteau C1 en B1/.test(texteP1),
        `la ligne P1 ne dit pas ses appuis: « ${texteP1.slice(0, 300)} »`);
  exige(/cote du dessin \(« 600 »\) concorde/.test(texteP1),
        "la ligne P1 ne dit pas que la cote du dessin concorde");

  // 7 ─ LE DESSIN ET LA REVUE SE DESIGNENT L'UN L'AUTRE ─────────────────────
  ici("designation croisee");
  await page.click(`#voir-${spanP1?.extraction_id}`);
  exige(await page.locator('#modele-plan .plan-travee.choisi').count() === 1,
        "« Voir sur le dessin » ne designe pas la travee");
  await page.selectOption("#revue-source", "toutes");
  await page.locator("#modele-plan .plan-poteau").first().click();
  await page.waitForSelector("#revue-selection", { timeout: 5000 });
  const restreintes = await page.locator("#revue-tableau tbody tr").count();
  exige(restreintes > 0 && restreintes < extractions.length,
        `${restreintes} ligne(s) apres choix d'un poteau, sur ${extractions.length}`);
  await page.click("#revue-tout-afficher");
  exige(await page.locator("#revue-tableau tbody tr").count() === extractions.length,
        "« Tout afficher » ne rend pas la liste entiere");

  // 8 ─ UNE MESURE CORROBOREE PAR UN TEXTE ──────────────────────────────────
  ici("corroboration");
  const sectionC1 = extractions.find((x) => x.kind === "column_width"
    && x.source_type === "geometry" && x.element_label === "C1");
  const ligneC1 = await page.locator(`#extraction-${sectionC1?.extraction_id}`).innerText();
  exige(/Corroborée par 30 cm \(texte ou cote du dxf/.test(ligneC1),
        `la section de C1 ne dit pas sa corroboration: « ${ligneC1.slice(0, 300)} »`);

  // 9 ─ DECIDER ET REPORTER ────────────────────────────────────────────────
  ici("decision et report");
  const largeurP1 = extractions.find((x) => x.kind === "beam_width"
    && x.source_type === "geometry" && x.element_label === "P1");
  for (const x of [spanP1, largeurP1]) {
    const r = await corpsDe("/decision", "POST",
                            () => page.click(`#confirmer-${x?.extraction_id}`));
    exige(r.statut === 200 && r.corps?.confirmed_by_name === A.nom,
          `confirmer ${x?.kind} a rendu ${r.statut} / ${r.corps?.confirmed_by_name}`);
  }
  const rempli = await corpsDe("/extractions/prefill", "GET", () => page.click("#reporter-tout"));
  exige(rempli.statut === 200, `le preremplissage a rendu ${rempli.statut}`);
  await page.waitForSelector("#report-documents", { timeout: 15000 });
  await page.click("#etape-section");
  exige(await page.inputValue("#vc-leff") === "6000",
        `l_eff vaut ${await page.inputValue("#vc-leff")}, 6000 mm attendus`);
  exige(await page.inputValue("#vc-b") === "300", `b vaut ${await page.inputValue("#vc-b")}`);
  const origine = await page.innerText("#origine-l_eff");
  exige(/géométrie du dxf/i.test(origine) && origine.includes(A.nom),
        `l'origine de l_eff ne dit pas la geometrie: « ${origine} »`);
  exige(origine.includes("5.3.2.2"), "la portee reportee ne porte pas son avertissement");

  // 10 ─ LE CALCUL REECRIT LA PROVENANCE ───────────────────────────────────
  ici("lancement avec provenance geometrique");
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
  exige(chemins.join(",") === "geometry.b,geometry.l_eff",
        `provenance envoyee pour: ${chemins.join(", ")}`);
  const reecrite = etude.corps?.request?.provenance?.["geometry.l_eff"] ?? {};
  exige(reecrite.confirmed_by === A.nom && /géométrie du dxf/.test(reecrite.detail ?? "")
        && reecrite.extraction_id === spanP1?.extraction_id,
        `provenance rendue: ${JSON.stringify(reecrite).slice(0, 300)}`);

  // 11 ─ APRES F5 ──────────────────────────────────────────────────────────
  ici("rechargement complet");
  await page.reload({ waitUntil: "domcontentloaded" });
  await page.waitForSelector("#connecter", { timeout: 20000 });
  await connecter(A);
  await page.selectOption("#projet", projetId);
  const ligneDoc = page.locator(`#document-${doc.document_id}`);
  await ligneDoc.waitFor({ timeout: 15000 });
  exige(/5 travée/.test(await ligneDoc.innerText()), "le resume du modele a disparu apres F5");
  exige(/2 confirmée/.test(await ligneDoc.locator("td.decomptes").innerText()),
        "les decomptes apres F5 ne disent pas les deux decisions");
  bilan.push(`modele      ${JSON.stringify(comptes)}`);
  bilan.push(`sources     geometrie ${geo.length}, texte DXF ${texteDxf.length}`);
  bilan.push(`etude       ${etude.corps?.calculation_id} — l_eff et b mesures sur le dessin`);

  // 12 ─ LA PAGE N'A CRIE NULLE PART ───────────────────────────────────────
  exige(criees.length === 0, "la page a crie: " + criees.slice(0, 4).map(enClair).join(" | "));
} catch (cause) {
  echecs.push(`exception a l'etape « ${etapeCourante} »: ${cause}`);
  try {
    for (const sel of ["#documents-message", "#revue-message", "[role=alert]"]) {
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
  console.log("ROUGE — parcours geometrie d'un DXF depuis le navigateur");
  echecs.forEach((e) => console.log("   - " + e));
  process.exit(1);
}
console.log(
  "ok: un DXF qui n'ecrit aucune portee part en octets bruts; la liste dit "
  + "qu'un modele structurel a ete reconstruit; la revue separe la geometrie "
  + "du texte du DXF, comptes egaux a ceux de la base; le modele est dessine "
  + "(6 poteaux, 3 poutres, 5 travees) et P1 se lit A1 -> B1, 600 cm entre "
  + "axes, 570 cm nu a nu; toutes les portees sont geometriques; la ligne de "
  + "P1 dit ses appuis et la cote qui concorde; dessin et revue se designent; "
  + "la section de C1 est corroboree par le texte; la portee et la largeur "
  + "confirmees se reportent en l_eff = 6000 mm et b = 300 mm avec l'origine "
  + "« geometrie du DXF » et l'avertissement de la portee utile; le serveur "
  + "reecrit ces provenances au nom de la decision; apres F5 le resume et les "
  + "decomptes sont la; la page n'a crie nulle part.",
);
bilan.forEach((l) => console.log("   " + l));
