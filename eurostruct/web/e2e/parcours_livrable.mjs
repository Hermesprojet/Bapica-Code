/**
 * LE LIVRABLE DOIT SE PRODUIRE, SE FAIRE RELIRE ET S'ÉMETTRE DEPUIS L'ÉCRAN.
 *
 * CE QUE CE PARCOURS ÉPROUVE, ET QUE RIEN D'AUTRE NE PEUT ÉPROUVER
 * -----------------------------------------------------------------
 * `test_livrables.py` prouve que les huit routes et les sept primitives
 * tiennent sous identité vérifiée, et que PostgreSQL cloisonne. Il construit
 * ses requêtes lui-même : il ne dit rien de ce que l'ÉCRAN envoie, ni de ce
 * qu'un ingénieur peut réellement faire avec sa souris, ni de ce qui reste
 * après un F5.
 *
 * LES TREIZE FAITS
 * -----------------
 *   1. A se connecte ;
 *   2. il crée un projet BE / Wallonie / date de référence ;
 *   3. il enregistre un calcul **strict** qui aboutit ;
 *   4. il produit un brouillon de livrable depuis l'historique ;
 *   5. il le télécharge, et le sha256 des octets **reçus par le navigateur**
 *      est celui que la base a enregistré ;
 *   6. après un RECHARGEMENT COMPLET, les mêmes données et les MÊMES OCTETS ;
 *   7. il le soumet à la relecture — et son écran n'offre **aucun** panneau
 *      d'attestation, en disant pourquoi ;
 *   8. V, ingénieur validateur, atteste : son nom et son numéro d'inscription
 *      viennent de son adhésion, jamais de l'écran ;
 *   9. l'émission n'est possible qu'après cette attestation ;
 *   9 bis. elle PRODUIT un second PDF, qui se télécharge depuis l'écran, cite
 *      le SHA-256 de l'original dans ses octets, dit qu'il n'est pas une
 *      signature qualifiée — et l'original reste byte-identique ;
 *  10. un livrable émis ne se modifie plus ;
 *  11. une révision est créée, avec l'indice suivant ;
 *  12. B, de l'autre organisation, n'obtient ni lecture ni téléchargement.
 *
 * LES CONFIRMATIONS NORMATIVES SONT UN DÉCOR, ET LE PARCOURS LE DIT
 * -------------------------------------------------------------------
 * Une attestation ne peut porter que sur un calcul strict abouti, et le mode
 * strict ne s'ouvre que par le quatre-yeux. Le décor les fait passer par les
 * ROUTES DU PRODUIT, avec les jetons réels de A et de V, depuis le contexte de
 * la page — exactement comme le ferait l'écran d'autorité. Ce n'est pas ce que
 * ce parcours prouve ; c'est ce qui le rend possible.
 *
 * AUCUNE ATTESTATION PRODUITE ICI N'EST UNE VALIDATION RÉELLE. Les comptes
 * sont fictifs et la base est détruite à la fin du harnais.
 *
 * ON OBSERVE CE QUI PART ET CE QUI REVIENT, pas l'état de React.
 */
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";

import { chargerChromium, cheminChromium } from "./playwright.mjs";

const WEB = process.env.EUROSTRUCT_WEB || "http://localhost:3000";
const API = process.env.EUROSTRUCT_API || "http://127.0.0.1:8000";
const TELECHARGEMENTS = process.env.EUROSTRUCT_E2E_TELECHARGEMENTS || "/tmp";

const A = { courriel: "a@fictif.invalid", mdp: "FICTIF-A" };
const V = { courriel: "v@fictif.invalid", mdp: "FICTIF-V" };
const B = { courriel: "b@fictif.invalid", mdp: "FICTIF-B" };
const ACTEUR_A = process.env.EUROSTRUCT_E2E_ACTEUR_A || "";
const ACTEUR_V = process.env.EUROSTRUCT_E2E_ACTEUR_V || "";
const ACTEUR_B = process.env.EUROSTRUCT_E2E_ACTEUR_B || "";

const PAYS = "BE";
const REGION = "Wallonie";
const DATE_REF = "2024-03-01";

const echecs = [];
const exige = (ok, message) => {
  if (!ok) echecs.push(message);
};

let etapeCourante = "demarrage";
const ici = (nom) => { etapeCourante = nom; };

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

const criees = [];
page.on("pageerror", (e) => criees.push(`erreur de page: ${e.message}`));
page.on("console", (m) => {
  if (m.type() === "error") criees.push(`console: ${m.text()}`);
});
page.on("requestfailed", (r) => {
  criees.push(`requete echouee: ${r.method()} ${r.url()} — ${r.failure()?.errorText}`);
});

/** Tout ce qui part vers l'API : méthode, URL, en-tête. */
const requetes = [];
page.on("request", (r) => {
  const url = r.url();
  if (!url.startsWith(API)) return;
  requetes.push({
    methode: r.method(),
    url,
    autorisation: r.headers()["authorization"] ?? null,
  });
});

/**
 * Le `sub` d'un en-tête `Authorization: Bearer <jwt>`, ou `null`.
 *
 * ON NE VÉRIFIE RIEN ICI, ET C'EST VOLONTAIRE. La signature est vérifiée par
 * l'API ; ce parcours lit seulement QUI le navigateur a mis dans la requête.
 */
function sujetDuJeton(entete) {
  if (typeof entete !== "string" || !entete.startsWith("Bearer ")) return null;
  const parts = entete.slice(7).split(".");
  if (parts.length !== 3) return null;
  try {
    return JSON.parse(
      Buffer.from(parts[1].replace(/-/g, "+").replace(/_/g, "/"),
                  "base64").toString("utf8")).sub ?? null;
  } catch {
    return null;
  }
}

const attenteJeton = (delai) =>
  page.waitForResponse(
    (r) => r.url().includes("/auth/v1/token") && r.request().method() === "POST",
    { timeout: delai },
  );

async function connecter({ courriel, mdp }) {
  await page.fill("#courriel", courriel);
  await page.fill("#mdp", mdp);
  const delivre = attenteJeton(15000);
  await page.click("#connecter");
  await delivre;
  await page.waitForSelector("#deconnecter", { timeout: 15000 });
  await page.waitForSelector("#projet", { timeout: 15000 });
}

async function deconnecter() {
  await page.click("#deconnecter");
  await page.waitForSelector("#connecter", { timeout: 15000 });
}

/** Attend la réponse d'un appel de l'atelier, et rend son corps. */
async function corpsDe(motif, methode, action) {
  const attente = page.waitForResponse(
    (r) => r.url().includes(motif) && r.request().method() === methode,
    { timeout: 60000 },
  );
  await action();
  const reponse = await attente;
  return { statut: reponse.status(), corps: await reponse.json().catch(() => null) };
}

/**
 * LE JETON QUE LE NAVIGATEUR VIENT D'EMPLOYER, OBSERVÉ SUR LE RÉSEAU.
 *
 * ON NE LE LIT NI DANS `localStorage`, NI DANS UNE VARIABLE GLOBALE — le
 * parcours vérifie plus bas qu'il n'est persisté nulle part, et un produit qui
 * l'exposerait pour les besoins d'un test aurait été modifié par son test. On
 * le prend là où il passe déjà : dans l'en-tête d'une requête que l'écran a
 * envoyée de lui-même.
 */
function jetonObserve() {
  for (let i = requetes.length - 1; i >= 0; i--) {
    const e = requetes[i].autorisation;
    if (typeof e === "string" && e.startsWith("Bearer ") && e.length > 30) {
      return e.slice(7);
    }
  }
  return "";
}

/**
 * Un appel à l'API **depuis la page**, avec le jeton que l'écran vient
 * d'employer.
 *
 * IL NE CONTOURNE PAS L'AUTHENTIFICATION, IL S'EN SERT. C'est le seul moyen
 * d'atteindre une route qu'aucun bouton n'expose — soit parce qu'elle est un
 * décor (les confirmations normatives), soit parce que le produit refuse de
 * l'exposer (modifier un livrable émis, attester sans habilitation). Un
 * attaquant qui atteindrait l'API ne passerait pas par les boutons non plus.
 */
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

const decisions = [];

/**
 * LES FICHES DU REGISTRE NATIONAL, prises là où l'écran d'autorité les prend.
 *
 * Le rapport de préflight nomme les CLÉS bloquantes et rien de plus : il n'a
 * aucune raison de porter l'empreinte du document source ni son édition. Le
 * plan de charge, lui, les porte — c'est le même appel public que le repli
 * « où en est ce pays » de l'écran.
 *
 * AUCUNE VALEUR N'EST FABRIQUÉE ICI. Le parcours transporte ce que l'API rend,
 * exactement comme le navigateur le fait.
 */
async function fichesDuRegistre() {
  const r = await page.evaluate(async (api) => {
    const rep = await fetch(`${api}/v1/ndp/BE/parameters`);
    return { statut: rep.status, corps: await rep.json().catch(() => null) };
  }, API);
  if (r.statut !== 200) return null;
  const par = new Map();
  for (const f of r.corps?.parameters ?? []) par.set(f.key, f);
  return par;
}

/**
 * A propose la confirmation de chaque règle que le préflight bloque.
 *
 * C'EST UN DÉCOR, ET IL PASSE PAR LES ROUTES DU PRODUIT. Composer le dossier
 * côté serveur, le proposer sans y toucher — puis V l'approuve et le consomme,
 * dans SA session. Écrire une confirmation à la main prouverait que la
 * validation fonctionne sur une base où n'importe qui peut en fabriquer une.
 *
 * Rend `true` quand plus rien ne bloque, `"attente-du-second-regard"` quand des
 * propositions attendent V, et un message quand quelque chose a échoué.
 */
async function proposerLesConfirmations(projetId, corpsDeCalcul, fiches) {
  const essai = await depuisLaPage(
    `/v1/projects/${projetId}/calculations/ec2/beam-flexure`, "POST",
    { ...corpsDeCalcul, strict_ndp: true });
  if (essai.statut === 201) return true;

  const bloquants = (essai.corps?.detail?.preflight?.blocking
                     ?? essai.corps?.preflight?.blocking ?? []);
  if (!bloquants.length) {
    return `le calcul strict a rendu ${essai.statut} sans blocage nomme: `
         + `${(essai.texte ?? "").slice(0, 300)}`;
  }

  for (const b of bloquants) {
    const f = fiches.get(b.key);
    if (!f) return `la cle ${b.key} n'est pas au plan de charge`;

    const paquet = await depuisLaPage("/v1/authority/review-packages", "POST", {
      country_code: f.country_code,
      rule_id: f.key,
      statement: `FICTIF — dossier de revue de ${f.key} (base jetable).`,
      citations: [{
        document_digest: f.source_doc_id,
        quote: `FICTIF — citation relevee pour ${f.key}.`,
        page_printed: f.source_page ?? 1,
      }],
    });
    if (paquet.statut !== 200) {
      return `composition du dossier ${f.key}: ${paquet.statut} `
           + `${(paquet.texte ?? "").slice(0, 300)}`;
    }

    const propose = await depuisLaPage("/v1/authority/decisions", "POST", {
      subject_kind: "ndp_parameter",
      subject_id: f.key,
      org_id: null,
      country_code: f.country_code,
      standard_family: f.standard_family,
      part: f.part,
      edition: f.edition,
      permission: "can_validate_normative_reference",
      reason: `FICTIF revue de ${f.key}`,
      review_package: paquet.corps.package,
    });
    if (propose.statut !== 201) {
      return `proposition ${f.key}: ${propose.statut} `
           + `${(propose.texte ?? "").slice(0, 300)}`;
    }
    decisions.push({ id: propose.corps.decision_id, cle: f.key });
  }
  return "attente-du-second-regard";
}

/**
 * V approuve puis consomme tout ce que A a proposé.
 *
 * LE SECOND REGARD N'EST PAS CELUI DU PREMIER, et le quatre-yeux le refuse.
 * C'est ce qui fait qu'une confirmation vaut autre chose qu'une case cochée.
 */
async function secondRegard() {
  for (const d of decisions) {
    const a = await depuisLaPage(`/v1/authority/decisions/${d.id}/approval`, "POST");
    if (a.statut !== 204) {
      return `approbation ${d.cle}: ${a.statut} ${(a.texte ?? "").slice(0, 300)}`;
    }
    const c = await depuisLaPage(`/v1/authority/decisions/${d.id}/consumption`, "POST");
    if (c.statut !== 200) {
      return `consommation ${d.cle}: ${c.statut} ${(c.texte ?? "").slice(0, 300)}`;
    }
  }
  decisions.length = 0;
  return null;
}

/** Le sha256 des octets qu'un téléchargement du navigateur a produits. */
async function empreinteDuTelechargement(declencher) {
  const attente = page.waitForEvent("download", { timeout: 30000 });
  await declencher();
  const fichier = await attente;
  const chemin = `${TELECHARGEMENTS}/${fichier.suggestedFilename()}`;
  await fichier.saveAs(chemin);
  const octets = await readFile(chemin);
  return {
    nom: fichier.suggestedFilename(),
    taille: octets.length,
    sha256: createHash("sha256").update(octets).digest("hex"),
    texte: octets.toString("utf8"),
  };
}

let projetId = "";
let livrableId = "";
let empreinteEnregistree = "";

try {
  // =======================================================================
  // 1 à 2 — A SE CONNECTE ET CRÉE UN PROJET
  // =======================================================================
  ici("ouverture de la page");
  await page.goto(WEB, { waitUntil: "domcontentloaded" });

  ici("connexion de A");
  const liste = await corpsDe("/v1/projects", "GET", () => connecter(A));
  exige(liste.statut === 200, `la liste des projets a rendu ${liste.statut}`);

  ici("creation du projet");
  await page.click("text=Nouveau projet");
  await page.fill("#p-nom", "FICTIF — Halle livrable");
  await page.fill("#p-ref", "FICTIF-LIV-NAV");
  await page.fill("#p-region", REGION);
  await page.fill("#p-date", DATE_REF);
  const cree = await corpsDe("/v1/projects", "POST",
                             () => page.click("text=Créer le projet"));
  exige(cree.statut === 201, `la creation a rendu ${cree.statut}`);
  projetId = cree.corps?.project_id ?? "";
  exige(/^[0-9a-f-]{36}$/i.test(projetId),
        `la creation n'a pas rendu d'identifiant (« ${projetId} »)`);

  //: L'ECRAN SAIT QUE A N'EST PAS VALIDATEUR, ET LE DIT.
  exige(cree.corps?.member_role === "engineer",
        `le role rendu pour A est « ${cree.corps?.member_role} »`);

  // =======================================================================
  // DÉCOR — OUVRIR LE MODE STRICT PAR LE QUATRE-YEUX
  // =======================================================================
  ici("decor: confirmations normatives (A propose)");
  const corpsCalcul = {
    element: "P1",
    strict_ndp: true,
    section: { b: { value: 300, unit: "mm" }, h: { value: 500, unit: "mm" },
               d: { value: 450, unit: "mm" } },
    materials: { concrete_grade: "C30/37", steel_grade: "B500B" },
    M_Ed: { value: 180, unit: "kN*m" },
  };

  //: A PROPOSE, V APPROUVE ET CONSOMME. Deux sessions distinctes, parce que le
  //: quatre-yeux refuse l'auto-approbation — et c'est ce qui fait qu'une
  //: confirmation vaut autre chose qu'une case cochee.
  const fiches = await fichesDuRegistre();
  exige(fiches !== null && fiches.size > 0,
        "le plan de charge national n'a pas pu etre lu");

  let ouvert = false;
  for (let tour = 0; tour < 12 && !ouvert && fiches; tour++) {
    const r = await proposerLesConfirmations(projetId, corpsCalcul, fiches);
    if (r === true) { ouvert = true; break; }
    if (r !== "attente-du-second-regard") {
      exige(false, `le decor de confirmation a echoue: ${r}`);
      break;
    }

    ici(`decor: second regard de V (tour ${tour + 1})`);
    await deconnecter();
    await connecter(V);
    const refus = await secondRegard();
    if (refus !== null) { exige(false, `le second regard a echoue: ${refus}`); break; }

    await deconnecter();
    await connecter(A);
    await page.selectOption("#projet", projetId);
  }
  exige(ouvert, "le mode strict ne s'est pas ouvert: aucun calcul strict ne "
              + "peut aboutir, et aucune attestation ne peut donc porter.");

  // =======================================================================
  // 3 — UN CALCUL STRICT, ENREGISTRÉ DEPUIS L'ÉCRAN
  // =======================================================================
  ici("calcul strict enregistre depuis l'ecran");
  await page.selectOption("#projet", projetId);
  await page.check("#strict");
  const calcul = await corpsDe(
    "/calculations/ec2/beam-flexure", "POST",
    () => page.click("text=Calculer et enregistrer sur le projet"));
  exige(calcul.statut === 201, `le calcul a rendu ${calcul.statut}`);
  exige(calcul.corps?.status === "succeeded",
        `le calcul strict n'a pas abouti: ${calcul.corps?.status}`);
  exige(calcul.corps?.strict_ndp === true,
        "le calcul enregistre n'est pas en mode strict");
  const calculId = calcul.corps?.calculation_id ?? "";

  // =======================================================================
  // 4 — UN BROUILLON, PRODUIT PAR LE BOUTON DE L'HISTORIQUE
  // =======================================================================
  ici("production du brouillon");
  //: ON DESIGNE LA LIGNE DU CALCUL, PAS « le bouton ». L'historique porte
  //: plusieurs calculs aboutis — le decor en a produit un par tour — et un
  //: selecteur par texte ne designerait aucun d'eux en particulier.
  //:
  //: ET ON DESIGNE LA FORME PAR SON IDENTIFIANT, PAS PAR SON LIBELLE. Depuis
  //: que l'ecran offre HTML *et* PDF, « text=Produire un brouillon » designe
  //: DEUX boutons: Playwright refuse alors d'agir, et il a raison.
  const bouton = page.locator(`#brouillon-html-${calculId}`);
  await bouton.waitFor({ timeout: 20000 });
  const brouillon = await corpsDe(
    "/deliverables", "POST", () => bouton.click());
  exige(brouillon.statut === 201, `la production a rendu ${brouillon.statut}`);
  livrableId = brouillon.corps?.deliverable_id ?? "";
  empreinteEnregistree = brouillon.corps?.sha256 ?? "";
  exige(brouillon.corps?.state === "draft",
        `le livrable neuf est en « ${brouillon.corps?.state} »`);
  exige(/^[0-9a-f]{64}$/.test(empreinteEnregistree),
        `l'empreinte enregistree est « ${empreinteEnregistree} »`);
  //: UN CALCUL STRICT NE PORTE PAS « PROJET — NON SIGNABLE ».
  exige(brouillon.corps?.watermark === null,
        `un calcul strict a produit le filigrane « ${brouillon.corps?.watermark} »`);

  await page.waitForSelector("#table-livrables", { timeout: 15000 });

  // =======================================================================
  // 4 bis — LE MEME CALCUL, EN PDF, PAR L'AUTRE BOUTON
  // =======================================================================
  //: LA SUITE D'API PROUVE QUE LA ROUTE PRODUIT UN PDF. Elle ne prouve pas
  //: qu'un bouton l'atteint — c'est exactement la lecon du prevol CORS, ou
  //: 32 cas verts coexistaient avec un panneau inatteignable.
  ici("production du brouillon PDF");
  const boutonPdf = page.locator(`#brouillon-pdf-${calculId}`);
  await boutonPdf.waitFor({ timeout: 20000 });
  const brouillonPdf = await corpsDe(
    "/deliverables", "POST", () => boutonPdf.click());
  exige(brouillonPdf.statut === 201,
        `la production PDF a rendu ${brouillonPdf.statut}`);
  exige(brouillonPdf.corps?.kind === "calculation_note_pdf",
        `le PDF a ete enregistre comme « ${brouillonPdf.corps?.kind} »`);
  exige(brouillonPdf.corps?.media_type === "application/pdf",
        `type de media « ${brouillonPdf.corps?.media_type} »`);
  exige(String(brouillonPdf.corps?.filename ?? "").endsWith(".pdf"),
        `nom de fichier « ${brouillonPdf.corps?.filename} »`);
  //: DEUX DOCUMENTS DISTINCTS POUR UN MEME CALCUL: leurs empreintes different,
  //: donc leurs chemins aussi, donc aucun n'ecrase l'autre.
  exige(brouillonPdf.corps?.sha256 !== empreinteEnregistree,
        "le PDF et le HTML du meme calcul portent la meme empreinte");

  //: ET ON LE TELECHARGE, PAR LE NAVIGATEUR, POUR VERIFIER SES OCTETS.
  //: Constater que la reponse de creation annonce un PDF ne dit rien de ce
  //: qui sortira du magasin: le document traverse ensuite le depot, la
  //: relecture, le transport et le navigateur.
  const livrablePdfId = brouillonPdf.corps?.deliverable_id ?? "";
  await page.waitForSelector(`tr[data-livrable="${livrablePdfId}"]`,
                             { timeout: 15000 });
  const recuPdf = await empreinteDuTelechargement(
    () => page.click(`tr[data-livrable="${livrablePdfId}"] >> text=Télécharger`));
  exige(recuPdf.sha256 === brouillonPdf.corps?.sha256,
        `le sha256 du PDF recu (${recuPdf.sha256.slice(0, 16)}…) differe de `
        + `celui enregistre (${String(brouillonPdf.corps?.sha256).slice(0, 16)}…)`);
  exige(recuPdf.taille === brouillonPdf.corps?.size_bytes,
        `taille recue ${recuPdf.taille}, enregistree ${brouillonPdf.corps?.size_bytes}`);
  exige(recuPdf.nom.endsWith(".pdf"),
        `le navigateur a propose d'enregistrer « ${recuPdf.nom} »`);
  //: LES OCTETS SONT BIEN CEUX D'UN PDF, et le flux n'est pas comprime: la
  //: mention obligatoire se lit DANS le fichier, sans rien decompresser.
  exige(recuPdf.texte.startsWith("%PDF-"),
        "les octets recus ne commencent pas par %PDF-");
  exige(recuPdf.texte.includes("NON SIGNABLE") === false,
        "un calcul strict ne doit pas porter le filigrane");
  exige(recuPdf.texte.includes("livrable final"),
        "la mention obligatoire ne se lit pas dans les octets du PDF");

  // =======================================================================
  // 5 — LES OCTETS TÉLÉCHARGÉS SONT CEUX QUI ONT ÉTÉ ENREGISTRÉS
  // =======================================================================
  ici("telechargement du livrable");
  const recu = await empreinteDuTelechargement(
    () => page.click(`tr[data-livrable="${livrableId}"] >> text=Télécharger`));
  exige(recu.sha256 === empreinteEnregistree,
        `le sha256 des octets recus (${recu.sha256.slice(0, 16)}…) differe de `
        + `celui enregistre (${empreinteEnregistree.slice(0, 16)}…)`);
  exige(recu.taille === brouillon.corps?.size_bytes,
        `la taille recue (${recu.taille}) differe de celle enregistree `
        + `(${brouillon.corps?.size_bytes})`);
  //: LE DOCUMENT EST AUTONOME, ET IL PORTE DE QUOI LE RATTACHER A SON CALCUL.
  exige(!/<script/i.test(recu.texte), "le document telecharge contient un script");
  exige(recu.texte.includes(brouillon.corps.engine_build_sha),
        "le document ne porte pas le SHA exact du moteur");
  exige(recu.texte.includes(brouillon.corps.execution_identity),
        "le document ne porte pas l'identite d'execution");

  // =======================================================================
  // 5 bis — LE DOSSIER DE REVUE SE TÉLÉCHARGE, ET IL EST DÉTERMINISTE
  // =======================================================================
  ici("telechargement du dossier de revue");
  const dossier = await empreinteDuTelechargement(
    () => page.click(`tr[data-livrable="${livrableId}"] >> text=Dossier de revue`));
  exige(dossier.nom.endsWith(".zip"),
        `le dossier telecharge s'appelle « ${dossier.nom} »`);
  exige(dossier.taille > 0, "le dossier de revue est vide");
  //: DEUX TELECHARGEMENTS RENDENT LES MEMES OCTETS. Un dossier dont
  //: l'empreinte change a chaque appel ne permet pas de dire « voici le
  //: dossier que j'ai relu ».
  const dossierBis = await empreinteDuTelechargement(
    () => page.click(`tr[data-livrable="${livrableId}"] >> text=Dossier de revue`));
  exige(dossierBis.sha256 === dossier.sha256,
        "deux telechargements du dossier de revue rendent des octets differents");

  // =======================================================================
  // 6 — F5 : LES MÊMES DONNÉES ET LES MÊMES OCTETS
  // =======================================================================
  ici("rechargement complet");
  //: UN VRAI RECHARGEMENT, PAS UN CLIC. Tout l'etat React disparait — et la
  //: SESSION AUSSI, parce qu'aucun jeton n'est persiste. Se reconnecter fait
  //: donc partie du F5: ce qui revient ensuite ne peut venir que de la base.
  await page.reload({ waitUntil: "domcontentloaded" });
  const apresRechargement = await corpsDe("/v1/projects", "GET",
                                          () => connecter(A));
  const revu = (apresRechargement.corps?.projects ?? [])
    .find((p) => p.project_id === projetId);
  exige(!!revu, "le projet a disparu apres rechargement complet");

  const listeApresF5 = await corpsDe(
    `/v1/projects/${projetId}/deliverables`, "GET",
    () => page.selectOption("#projet", projetId));
  exige(listeApresF5.statut === 200,
        `la liste des livrables a rendu ${listeApresF5.statut} apres F5`);
  const retrouve = (listeApresF5.corps?.deliverables ?? [])
    .find((d) => d.deliverable_id === livrableId);
  exige(!!retrouve, "le livrable a disparu apres rechargement complet");
  exige(retrouve?.sha256 === empreinteEnregistree,
        "l'empreinte enregistree a change apres rechargement");
  await page.waitForSelector("#table-livrables", { timeout: 20000 });

  const apresF5 = await empreinteDuTelechargement(
    () => page.click(`tr[data-livrable="${livrableId}"] >> text=Télécharger`));
  exige(apresF5.sha256 === empreinteEnregistree,
        "apres rechargement, les octets telecharges ont change");

  // =======================================================================
  // 7 — SOUMISSION À LA RELECTURE, ET CE QUE A NE PEUT PAS FAIRE
  // =======================================================================
  ici("soumission a la relecture");
  const soumis = await corpsDe(
    "/review", "POST",
    () => page.click(`tr[data-livrable="${livrableId}"] >> text=Soumettre à la relecture`));
  exige(soumis.statut === 200, `la soumission a rendu ${soumis.statut}`);
  exige(soumis.corps?.state === "review",
        `apres soumission l'etat est « ${soumis.corps?.state} »`);

  //: L'ECRAN DE A N'OFFRE AUCUN PANNEAU D'ATTESTATION, ET IL DIT POURQUOI.
  await page.click(`tr[data-livrable="${livrableId}"] >> text=Détail`);
  await page.waitForSelector("#detail-livrable", { timeout: 15000 });
  exige(await page.locator("#panneau-attestation").count() === 0,
        "le panneau d'attestation est offert a un ingenieur non habilite");
  const explication = await page.locator("#pourquoi-ferme").innerText();
  exige(/validating_engineer/.test(explication),
        `l'ecran n'explique pas pourquoi la validation est fermee: ${explication}`);

  //: ET LA ROUTE REFUSE AUSSI, avec le jeton reel de A. Cacher un bouton n'a
  //: jamais protege quoi que ce soit: la frontiere est en base.
  const refusA = await depuisLaPage(
    `/v1/projects/${projetId}/deliverables/${livrableId}/validation`, "POST",
    { statement: "FICTIF — je valide." });
  exige(refusA.statut === 422,
        `A a obtenu ${refusA.statut} sur l'attestation, au lieu d'un refus`);
  exige(/engineer/.test(refusA.texte ?? ""),
        `le refus ne nomme pas le role: ${refusA.texte}`);

  // =======================================================================
  // 8 et 9 — V ATTESTE, PUIS ÉMET
  // =======================================================================
  ici("attestation par V");
  await deconnecter();
  await connecter(V);
  await page.selectOption("#projet", projetId);
  await page.waitForSelector("#table-livrables", { timeout: 20000 });
  await page.click(`tr[data-livrable="${livrableId}"] >> text=Détail`);
  await page.waitForSelector("#panneau-attestation", { timeout: 15000 });

  await page.fill("#attestation",
                  "FICTIF — j'ai relu les hypotheses, les charges et le "
                  + "ferraillage de cette poutre.");
  await page.fill("#reserves",
                  "FICTIF — sous reserve du controle de l'enrobage.");
  const atteste = await corpsDe(
    "/validation", "POST", () => page.click("text=Attester ce calcul"));
  exige(atteste.statut === 200, `l'attestation a rendu ${atteste.statut}`);
  exige(atteste.corps?.state === "validated",
        `apres attestation l'etat est « ${atteste.corps?.state} »`);

  //: LE NOM ET LE NUMERO VIENNENT DE L'ADHESION, PAS DE L'ECRAN. Le corps
  //: envoye ne portait que le texte: aucun champ n'existe pour les nommer.
  exige(atteste.corps?.validator_name === "FICTIF Ing. V (compte de test)",
        `le nom atteste est « ${atteste.corps?.validator_name} »`);
  exige(atteste.corps?.professional_id === "FICTIF-ORDRE-0001",
        `le numero d'inscription est « ${atteste.corps?.professional_id} »`);
  exige(atteste.corps?.validator_role === "validating_engineer",
        `le role atteste est « ${atteste.corps?.validator_role} »`);
  const envoye = requetes.filter((r) => r.url.includes("/validation")).pop();
  exige(sujetDuJeton(envoye?.autorisation) === ACTEUR_V,
        `l'attestation est partie sous « ${sujetDuJeton(envoye?.autorisation)} » `
        + `et non sous V (${ACTEUR_V})`);

  ici("emission");
  const emis = await corpsDe(
    "/final", "POST",
    () => page.click(`tr[data-livrable="${livrableId}"] >> text=Émettre`));
  exige(emis.statut === 200, `l'emission a rendu ${emis.statut}`);
  exige(emis.corps?.state === "final",
        `apres emission l'etat est « ${emis.corps?.state} »`);

  // =======================================================================
  // 9 bis — L'ÉMISSION A PRODUIT UN SECOND DOCUMENT, ET IL CIRCULE
  // =======================================================================
  //: LE DEFAUT QUE CETTE SECTION FERME.
  //:
  //: Le parcours s'arretait a `state === "final"`. Il constatait donc que
  //: l'emission avait REPONDU — jamais qu'elle avait PRODUIT quelque chose.
  //: Or le PDF atteste est precisement ce qu'on transmet au client, et rien
  //: ne l'exercait depuis un navigateur: la seule preuve de bout en bout
  //: vivait dans pytest, cote serveur.
  ici("le document emis apparait dans la liste");
  const apresEmission = await depuisLaPage(
    `/v1/projects/${projetId}/deliverables`, "GET");
  exige(apresEmission.statut === 200,
        `la liste apres emission a rendu ${apresEmission.statut}`);

  const pieces = apresEmission.corps?.deliverables ?? [];
  const docEmis = pieces.find((d) => d.kind === "issued_calculation_note_pdf");
  exige(!!docEmis, "l'emission n'a produit aucun document atteste");
  exige(docEmis?.state === "final",
        `le document emis est en « ${docEmis?.state} » et non « final »`);
  //: IL DERIVE, IL NE REMPLACE PAS. `supersedes_id` dirait « l'original est
  //: perime »; c'est faux, et c'est l'original qui fait foi.
  exige(docEmis?.derived_from_id === livrableId,
        `le document emis derive de « ${docEmis?.derived_from_id } » `
        + `et non de l'original`);
  exige(!docEmis?.supersedes_id,
        "le document emis se declare successeur de l'original: il en derive");

  //: LES QUATRE PIECES SE DISTINGUENT DANS L'ECRAN, PAS SEULEMENT DANS L'API.
  //: Rangees cote a cote, la note attestee et le document qui porte
  //: l'attestation sont deux PDF; c'est le second qu'on transmet.
  ici("l'ecran nomme chaque piece");
  const ligneEmise = page.locator(`tr[data-livrable="${docEmis.deliverable_id}"]`);
  await ligneEmise.waitFor({ timeout: 20000 });
  exige(await ligneEmise.locator("text=PDF émis avec attestation").count() > 0,
        "l'ecran ne nomme pas le document emis « PDF émis avec attestation »");

  ici("telechargement du document emis");
  const recuEmis = await empreinteDuTelechargement(
    () => ligneEmise.locator("text=Télécharger").click());
  exige(recuEmis.texte.startsWith("%PDF-"),
        "les octets du document emis ne commencent pas par %PDF-");
  exige(recuEmis.taille === docEmis.size_bytes,
        `la taille recue (${recuEmis.taille}) differe de celle enregistree `
        + `(${docEmis.size_bytes})`);
  exige(recuEmis.sha256 === docEmis.sha256,
        "le sha256 des octets recus differe de celui enregistre en base");

  //: LE CAS DECISIF DE TOUTE CETTE FONCTIONNALITE.
  //:
  //: L'attestation porte sur des octets. Si le document emis ne CITE pas
  //: l'empreinte de l'original, il n'atteste rien de verifiable: le
  //: destinataire ne peut pas rattacher la declaration au fichier qu'il tient.
  exige(recuEmis.texte.includes(empreinteEnregistree),
        "le document emis ne cite pas le SHA-256 de l'original dans ses octets");
  exige(recuEmis.sha256 !== empreinteEnregistree,
        "le document emis a la meme empreinte que l'original");
  //: ET IL DIT CE QU'IL N'EST PAS. Une attestation metier n'est pas une
  //: signature qualifiee; le document le porte, en toutes lettres.
  exige(/signature .lectronique qualifi/i.test(recuEmis.texte),
        "le document emis ne dit pas qu'il n'est pas une signature qualifiee");

  ici("l'original n'a pas bouge d'un octet");
  //: LE PDF INITIAL RESTE BYTE-IDENTIQUE. Y ajouter l'attestation aurait
  //: detruit le lien qu'elle etablit: son empreinte est ce sur quoi elle
  //: porte. On le retelecharge APRES emission, et on le compare a l'empreinte
  //: relevee AVANT.
  const originalApres = await empreinteDuTelechargement(
    () => page.click(`tr[data-livrable="${livrableId}"] >> text=Télécharger`));
  exige(originalApres.sha256 === empreinteEnregistree,
        `l'emission a modifie l'original: ${originalApres.sha256.slice(0, 16)}… `
        + `au lieu de ${empreinteEnregistree.slice(0, 16)}…`);

  // =======================================================================
  // 10 — UN LIVRABLE ÉMIS NE SE MODIFIE PLUS
  // =======================================================================
  ici("refus de modification du livrable emis");
  //: L'ECRAN N'OFFRE PLUS NI SOUMISSION NI RETOUR, et la route refuse aussi.
  //: Les deux comptent: le bouton absent evite l'erreur, la route la rend
  //: impossible.
  const ligne = page.locator(`tr[data-livrable="${livrableId}"]`);
  exige(await ligne.locator("text=Soumettre à la relecture").count() === 0,
        "un livrable emis offre encore « Soumettre à la relecture »");

  //: CHAQUE TRANSITION EST DEMANDEE PAR QUI A LA CAPACITE DE LA DEMANDER, et
  //: c'est ce qui rend le refus concluant. Un retour au brouillon demande par
  //: le redacteur serait refuse sur le ROLE, et ne dirait rien de
  //: l'immuabilite d'un livrable emis. V a la capacite de valider: son refus
  //: ne peut donc venir que de l'etat.
  const retour = await depuisLaPage(
    `/v1/projects/${projetId}/deliverables/${livrableId}/draft`,
    "POST", { reason: "FICTIF" });
  exige(retour.statut === 422,
        `le retour au brouillon d'un livrable emis a rendu ${retour.statut}`);

  // =======================================================================
  // 11 — LA RÉVISION, PAR LE RÉDACTEUR
  // =======================================================================
  //: REVISER EST UN GESTE DE REDACTION (0023): l'ecran de V n'offre donc pas
  //: le bouton, et c'est A qui reprend la main. La separation joue jusqu'au
  //: bout — celui qui repond du calcul ne redige pas l'indice suivant.
  ici("l'ecran du validateur n'offre pas la revision");
  exige(await ligne.locator("text=Créer une révision").count() === 0,
        "l'ecran du validateur offre « Créer une révision »");

  ici("retour du redacteur");
  await deconnecter();
  await connecter(A);
  await page.selectOption("#projet", projetId);
  await page.waitForSelector("#table-livrables", { timeout: 20000 });

  //: ET SOUS SON IDENTITE, LA SOUMISSION D'UN LIVRABLE EMIS EST REFUSEE PAR
  //: L'ETAT, PAS PAR LE ROLE: A a la capacite de rediger.
  const soumission = await depuisLaPage(
    `/v1/projects/${projetId}/deliverables/${livrableId}/review`, "POST");
  exige(soumission.statut === 422,
        `la soumission d'un livrable emis a rendu ${soumission.statut}`);

  ici("creation d'une revision");
  const revision = await corpsDe(
    "/revision", "POST",
    () => page.click(`tr[data-livrable="${livrableId}"] >> text=Créer une révision`));
  exige(revision.statut === 201, `la revision a rendu ${revision.statut}`);
  exige(revision.corps?.state === "draft",
        `la revision est en « ${revision.corps?.state} »`);
  exige(revision.corps?.revision === 2,
        `l'indice de la revision est ${revision.corps?.revision}`);
  exige(revision.corps?.supersedes_id === livrableId,
        "la revision ne reference pas le livrable qu'elle remplace");

  // =======================================================================
  // 12 — B N'OBTIENT NI LECTURE NI TÉLÉCHARGEMENT
  // =======================================================================
  ici("isolation inter-organisations");
  await deconnecter();
  await connecter(B);

  //: LE PROJET N'APPARAIT MEME PAS DANS SA LISTE.
  const optionsDeB = await page.locator("#projet option").evaluateAll(
    (n) => n.map((o) => o.value));
  exige(!optionsDeB.includes(projetId),
        "le projet de A apparait dans la liste de B");

  //: ET AVEC SON PROPRE JETON, VALIDE, SIGNE DE LA MEME CLE, LES ROUTES
  //: REFUSENT. Il n'est simplement membre d'aucune organisation du projet.
  for (const [chemin, methode] of [
    [`/v1/projects/${projetId}/deliverables`, "GET"],
    [`/v1/projects/${projetId}/deliverables/${livrableId}`, "GET"],
    [`/v1/projects/${projetId}/deliverables/${livrableId}/download`, "GET"],
  ]) {
    const r = await depuisLaPage(chemin, methode);
    exige(r.statut === 422, `B a obtenu ${r.statut} sur ${methode} ${chemin}`);
    const envoyee = requetes.filter((q) => q.url.includes(chemin)).pop();
    exige(sujetDuJeton(envoyee?.autorisation) === ACTEUR_B,
          `la requete de B est partie sous « ${sujetDuJeton(envoyee?.autorisation)} »`);
    //: ET LE REFUS NE LAISSE RIEN FILTRER du dossier de l'autre bureau.
    for (const secret of ["FICTIF — Halle livrable", "FICTIF Bureau A",
                          "FICTIF Ing. V (compte de test)",
                          empreinteEnregistree]) {
      exige(!(r.texte ?? "").includes(secret),
            `le refus servi a B laisse filtrer « ${secret} »`);
    }
  }

  // =======================================================================
  // AUCUN JETON N'EST PERSISTÉ
  // =======================================================================
  ici("balayage des stockages");
  const tout = await page.evaluate(() => {
    const l = [];
    for (let i = 0; i < localStorage.length; i++) {
      l.push(localStorage.key(i), localStorage.getItem(localStorage.key(i)));
    }
    for (let i = 0; i < sessionStorage.length; i++) {
      l.push(sessionStorage.key(i), sessionStorage.getItem(sessionStorage.key(i)));
    }
    l.push(document.cookie, location.href);
    return l.join("\n");
  });
  exige(!/eyJ[A-Za-z0-9_-]{10,}/.test(tout),
        "quelque chose qui ressemble a un JWT est persiste dans le navigateur");
} catch (cause) {
  echecs.push(`exception a l'etape « ${etapeCourante} »: ${cause}`);
  //: CE QUE L'ECRAN DISAIT AU MOMENT DE LA CASSE. Sans cela, un refus affiche
  //: par le produit — « aucun magasin d'objets », « votre role ne porte pas la
  //: validation » — reste invisible, et le diagnostic ne parle que de
  //: Playwright.
  try {
    for (const sel of ["#refus-livrable", "#pourquoi-ferme", "[role=alert]"]) {
      const n = await page.locator(sel).count();
      for (let i = 0; i < Math.min(n, 3); i++) {
        echecs.push(`  ecran ${sel}: ${await page.locator(sel).nth(i).innerText()}`);
      }
    }
  } catch { /* la page peut etre morte: le diagnostic est un plus, pas un du */ }
} finally {
  await nav.close();
}

if (echecs.length) {
  console.log("ROUGE — parcours livrable depuis le navigateur");
  echecs.forEach((e) => console.log("   - " + e));
  if (criees.length) {
    console.log("   ce que la page a signale:");
    criees.slice(0, 12).forEach((c) => console.log("     · " + c));
  }
  process.exit(1);
}
console.log(
  "ok: A cree un projet BE/Wallonie, ouvre le mode strict par le quatre-yeux "
  + "avec V, enregistre un calcul strict, produit un brouillon HTML puis un "
  + "brouillon PDF — deux documents distincts, aux empreintes differentes — "
  + "dont les octets "
  + "telecharges portent l'empreinte enregistree et la conservent apres un "
  + "rechargement complet; le dossier de revue se telecharge et deux "
  + "telechargements rendent les memes octets; l'ecran de A n'offre aucun "
  + "panneau d'attestation et "
  + "dit pourquoi, la route le refuse aussi; V atteste sous le nom et le "
  + "numero d'inscription de SON adhesion, emet, et le livrable emis ne se "
  + "modifie plus — ni par bouton, ni par route; une revision d'indice 2 le "
  + "remplace; B ne voit pas le projet et obtient un refus qui ne laisse rien "
  + "filtrer; aucun jeton persiste.",
);
