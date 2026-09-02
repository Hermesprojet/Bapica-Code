/**
 * LA VÉRIFICATION COMPLÈTE, DEPUIS UN NAVIGATEUR RÉEL.
 *
 * CE QUE CE PARCOURS ÉPROUVE, ET QUE RIEN D'AUTRE NE PEUT ÉPROUVER
 * -----------------------------------------------------------------
 * `test_verification_complete.py` prouve que les routes tiennent sous identité
 * vérifiée et que PostgreSQL garde ce qu'on lui donne. Il construit ses
 * requêtes lui-même : il ne dit rien de ce que l'ÉCRAN envoie, ni de ce qu'un
 * ingénieur peut réellement faire avec sa souris, ni de ce qui reste après un
 * F5.
 *
 * LES DIX FAITS
 * --------------
 *   1. A se connecte et crée un projet BE / Wallonie ;
 *   2. le lancement reste fermé tant que φ(∞,t₀) et le système structural ne
 *      sont pas choisis, et l'écran ÉCRIT lesquels manquent ;
 *   3. en mode strict, AVANT toute confirmation, l'écran refuse et NOMME les
 *      onze paramètres nationaux manquants, avec le chapitre qui les réclame ;
 *   4. le quatre-yeux avec V confirme tout ce qui porte une valeur relevée
 *      dans l'annexe, et **s'arrête sur `w_max`** ;
 *   5. l'étude complète aboutit en exploratoire assumé : cinq chapitres, la
 *      mention obligatoire, et le motif de non-finalisation écrit ;
 *   6. la note PDF se produit et se télécharge ; ses octets portent
 *      l'empreinte que la base a enregistrée ;
 *   7. le PLAN DXF se produit **sans qu'aucun ferraillage ne parte du
 *      navigateur** — la requête observée sur le réseau ne porte que
 *      l'identifiant du calcul et le format ;
 *   8. l'aperçu montre le même modèle, et se dit non contractuel ;
 *   9. après un RECHARGEMENT COMPLET, l'étude se relit à l'identique et le
 *      même plan ressort avec les MÊMES OCTETS ;
 *  10. une étude en échec ferme les documents en écrivant pourquoi, et la
 *      route refuse aussi.
 *
 * ET UN ONZIÈME, QUI COURT SUR TOUS LES AUTRES
 * ----------------------------------------------
 * **La page ne crie nulle part.** Toute exception non rattrapée et toute
 * erreur de console font échouer ce parcours — au chargement initial, après
 * un F5, après une navigation, et sur l'ensemble du trajet.
 *
 * Ce contrôle-là est né d'un échec du contrôle précédent : les cris étaient
 * collectés puis imprimés **seulement quand une assertion tombait**. L'erreur
 * d'hydratation React #418 est donc restée présente à chaque chargement
 * pendant des semaines, sous les yeux d'un parcours vert qui la voyait et n'en
 * concluait rien.
 *
 * POURQUOI L'ÉTUDE COMPLÈTE EST EXPLORATOIRE, ET CE QUE CELA MESURE
 * ------------------------------------------------------------------
 * Ce n'est pas un contournement : c'est le seul chemin honnête aujourd'hui en
 * Belgique. Douze des treize paramètres que réclament les cinq chapitres
 * portent une valeur relevée dans la NBN EN 1992-1-1 ANB, et le quatre-yeux
 * les confirme. `w_max` n'en porte aucune — sa fiche dit « NON RELEVE dans le
 * Tableau 7.1N-ANB » — si bien que le confirmer signerait un blanc. La
 * passerelle le refuse en le nommant, le mode strict reste fermé pour une
 * vérification COMPLÈTE, et le parcours mesure exactement où ce mur se trouve.
 *
 * Un parcours qui aurait forcé ce vert-là aurait prouvé le contraire de ce
 * qu'on cherche.
 *
 * AUCUNE ÉTUDE PRODUITE ICI N'EST UNE VÉRIFICATION RÉELLE. Les comptes sont
 * fictifs, le registre national reste à 0/29, et la base est détruite à la fin
 * du harnais.
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

const REGION = "Wallonie";
const DATE_REF = "2024-03-01";

const echecs = [];
const exige = (ok, message) => { if (!ok) echecs.push(message); };

/** Ce que le parcours a produit, imprime a la fin quand il est vert. */
const bilan = [];

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

/**
 * CE QUE LA PAGE A CRIÉ, ET CE QUE LE PARCOURS EN FAIT.
 *
 * UNE ERREUR DE CONSOLE EST UN ÉCHEC, PAS UNE NOTE DE BAS DE PAGE.
 * -----------------------------------------------------------------
 * Elles étaient collectées puis imprimées seulement quand une assertion
 * tombait. L'erreur d'hydratation React #418 est donc restée présente à chaque
 * chargement pendant des semaines, sous les yeux d'un parcours vert : il la
 * voyait, et n'en concluait rien.
 *
 * Toute exception non rattrapée (`pageerror`) et toute erreur de console font
 * désormais échouer le parcours.
 *
 * RIEN N'EST FILTRÉ À LA COLLECTE, ET C'EST LE POINT
 * ----------------------------------------------------
 * Le navigateur inscrit dans la console **toute** réponse non-2xx, y compris
 * celles que ce parcours provoque EXPRÈS : un refus de préflight strict, un
 * document demandé sur une étude en échec, une route inconnue visitée pour
 * éprouver le retour.
 *
 * UNE PREMIÈRE RÉDACTION ÉCARTAIT CES LIGNES DANS LE COLLECTEUR :
 *
 *     if (REFUS_ATTENDU.test(texte)) return;   // 422, n'importe où
 *
 * Cela annonçait une tolérance « bornée aux gestes volontaires » et en
 * appliquait une **globale et aveugle au chemin** : n'importe quelle requête
 * secondaire, n'importe quelle régression rendant 422 sur n'importe quelle
 * route, à n'importe quel moment, disparaissait sans laisser de trace.
 *
 * Tout est donc collecté. La tolérance vit dans `consommerRefus`, qui borne
 * chaque exception à UN geste, UN statut, UN chemin et UN NOMBRE. Ce qu'aucun
 * geste ne réclame reste dans la liste et fait échouer le parcours.
 */
const criees = [];

/** Un cri, avec l'endroit d'où il vient : le chemin sert à la tolérance. */
function crier(texte, url = "") {
  criees.push({ texte, url });
}

const enClair = (c) => (c.url ? `${c.texte} [${c.url}]` : c.texte);

page.on("pageerror", (e) => crier(`erreur de page: ${e.message}`));
page.on("console", (m) => {
  if (m.type() !== "error") return;
  crier(`console: ${m.text()}`, m.location()?.url ?? "");
});

/**
 * Consomme les cris d'UN geste qui en provoque un nombre CONNU, sur un chemin
 * CONNU, avec un statut CONNU.
 *
 * QUATRE CHOSES SONT AFFIRMÉES, ET AUCUNE N'EST FACULTATIVE :
 *
 *   * le **statut** — un 500 là où on attend un 422 est un défaut, pas une
 *     variante ;
 *   * le **chemin** — un 422 sur `/deliverables` ne paie pas pour un 422
 *     attendu sur `/beam-verifications` ;
 *   * le **nombre** — deux refus là où le geste n'en provoque qu'un signale un
 *     appel en double, c'est-à-dire une requête que personne n'a demandée ;
 *   * **rien d'autre** — tout cri qui n'est pas celui-là fait échouer.
 *
 * ELLE ATTEND LE MESSAGE PLUTÔT QUE DE L'ESPÉRER. Chromium inscrit la ligne
 * après que la promesse du `fetch` a été tenue : regarder tout de suite
 * laisserait passer un geste dont le cri arriverait une milliseconde plus
 * tard — et ce cri-là tomberait ensuite dans le bilan d'un autre geste.
 */
async function consommerRefus(depuis, { statut, chemin, nombre = 1 }, quoi) {
  const motif = new RegExp(`status of ${statut}\\b`);
  const correspond = (c) => motif.test(c.texte) && c.url.includes(chemin);

  const limite = Date.now() + 8000;
  while (Date.now() < limite
         && criees.slice(depuis).filter(correspond).length < nombre) {
    await page.waitForTimeout(100);
  }
  //: UN BATTEMENT DE PLUS, POUR VOIR UN CRI DE TROP. Sans lui, un second refus
  //: inattendu arriverait juste apres la coupe et serait attribue au geste
  //: suivant.
  await page.waitForTimeout(250);

  const nouveaux = criees.slice(depuis);
  const attendus = nouveaux.filter(correspond);
  const autres = nouveaux.filter((c) => !correspond(c));

  exige(autres.length === 0,
        `${quoi}: cri(s) inattendu(s) — ${autres.slice(0, 3).map(enClair).join(" | ")}`);
  exige(attendus.length === nombre,
        `${quoi}: ${attendus.length} refus ${statut} sur « ${chemin} », `
        + `${nombre} attendu(s)`);

  //: ON NE RETIRE QUE CE QU'ON A RECONNU. Une troncature seche
  //: (`criees.length = depuis`) effacerait aussi les cris inattendus qu'on
  //: vient de signaler, et le bilan final ne les reverrait jamais.
  criees.length = depuis;
  for (const c of autres) criees.push(c);
}

/**
 * TOUT CE QUI PART VERS L'API, AVEC SON CORPS.
 *
 * LE CORPS EST LE POINT DE CE PARCOURS. Le fait décisif du lot — « aucune aire
 * d'acier ne vient du navigateur » — ne se constate pas dans le fichier
 * produit : un DXF correct ne dit pas d'où viennent ses barres. Il se constate
 * ICI, dans ce que la page a réellement envoyé.
 */
const requetes = [];
page.on("request", (r) => {
  const url = r.url();
  if (!url.startsWith(API)) return;
  requetes.push({
    methode: r.method(),
    url,
    autorisation: r.headers()["authorization"] ?? null,
    corps: r.postData() ?? null,
  });
});

/** La dernière requête vers un chemin donné, ou `null`. */
function derniereRequete(motif, methode) {
  for (let i = requetes.length - 1; i >= 0; i--) {
    if (requetes[i].url.includes(motif) && requetes[i].methode === methode) {
      return requetes[i];
    }
  }
  return null;
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

/** Attend la réponse d'un appel, et rend son corps. */
async function corpsDe(motif, methode, action) {
  const attente = page.waitForResponse(
    (r) => r.url().includes(motif) && r.request().method() === methode,
    { timeout: 60000 },
  );
  await action();
  const reponse = await attente;
  return { statut: reponse.status(), corps: await reponse.json().catch(() => null) };
}

/** Le jeton que l'écran vient d'employer, observé sur le réseau. */
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
 * d'employer. Il ne contourne pas l'authentification, il s'en sert : c'est le
 * seul moyen d'atteindre le décor des confirmations, qu'aucun bouton n'expose.
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

/** Les fiches du registre national, prises là où l'écran d'autorité les prend. */
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
 * L'ÉTUDE DE RÉFÉRENCE, telle qu'un client l'envoie.
 *
 * Elle ne porte NI pays, NI région, NI date normative : les trois sont figés
 * sur le projet. C'est le contrat, et l'écran n'a pas d'autre moyen de les
 * envoyer même par erreur.
 */
function etudeDeReference(remplace = {}) {
  return {
    element: "P1",
    strict_ndp: true,
    geometry: {
      b: { value: 300, unit: "mm" }, h: { value: 600, unit: "mm" },
      d: { value: 550, unit: "mm" }, l_eff: { value: 6000, unit: "mm" },
    },
    materials: { concrete_grade: "C30/37", steel_grade: "B500B" },
    M_Ed: { value: 250, unit: "kN*m" },
    V_Ed: { value: 300, unit: "kN" },
    M_char: { value: 180, unit: "kN*m" },
    M_qp: { value: 120, unit: "kN*m" },
    phi_creep: 2.0,
    exposure_class: "XC3",
    structural_system: "simply_supported",
    supports_brittle_partitions: false,
    bars: { count: 4, diameter: { value: 20, unit: "mm" } },
    links: {
      legs: 2, diameter: { value: 10, unit: "mm" },
      spacing: { value: 150, unit: "mm" },
    },
    cot_theta: 1.5,
    cover: { value: 40, unit: "mm" },
    anchorage_available: { value: 800, unit: "mm" },
    ...remplace,
  };
}

/**
 * Ce que la route de vérification bloque, aujourd'hui, en mode strict.
 *
 * LE GESTE CONSOMME SON PROPRE CRI. Ce sondage provoque un 422 délibéré ; il
 * est donc responsable de le reconnaître, plutôt que de le laisser à un bilan
 * global qui ne saurait plus d'où il vient. Quand le préflight passe (201),
 * il n'y a rien à consommer — et rien n'est consommé.
 */
async function bloquantsStricts(projetId) {
  const depuis = criees.length;
  const essai = await depuisLaPage(
    `/v1/projects/${projetId}/beam-verifications`, "POST", etudeDeReference());
  if (essai.statut === 201) return { ouvert: true, cles: [] };
  await consommerRefus(
    depuis, { statut: essai.statut, chemin: "/beam-verifications" },
    "sondage du preflight strict");
  return {
    ouvert: false,
    statut: essai.statut,
    texte: essai.texte,
    //: LA CLE S'APPELLE `parameter`, PAS `key`. Le bloqueur de la verification
    //: complete nomme aussi le MODULE qui reclame — un meme `gamma_C` sert
    //: quatre modules sur cinq — et deux modules peuvent bloquer sur la meme
    //: cle: on ne la compte qu'une fois.
    cles: [...new Set((essai.corps?.detail?.blocking ?? [])
                        .map((b) => b.parameter))].sort(),
  };
}

/**
 * A propose la confirmation de chaque règle que le préflight des CINQ MODULES
 * bloque.
 *
 * LA LISTE VIENT DE LA ROUTE DE VÉRIFICATION, PAS DE CELLE DE FLEXION. Le
 * préflight de la flexion ne connaît que ses propres paramètres ; ouvrir le
 * mode strict sur eux seuls laisserait l'effort tranchant, l'ancrage, les
 * fissures et la flèche bloqués — et le parcours échouerait plus loin, sur un
 * message qui ne dirait pas pourquoi.
 *
 * CERTAINES CLÉS NE SE CONFIRMERONT JAMAIS, ET CE N'EST PAS UN ÉCHEC DE CE
 * DÉCOR. Une fiche dont la provenance est « national_annex_pending » ne porte
 * aucune valeur relevée dans l'annexe publiée : la confirmer signerait un
 * blanc, et la passerelle la refuse en le disant. Le parcours mesure donc ce
 * qui RESTE bloquant, il ne force rien.
 */
async function proposerLesConfirmations(projetId, fiches, bloquants) {
  for (const cle of bloquants) {
    const f = fiches.get(cle);
    if (!f) return `la cle ${cle} n'est pas au plan de charge`;

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
  return null;
}

/** V approuve puis consomme tout ce que A a proposé. */
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
  const attente = page.waitForEvent("download", { timeout: 60000 });
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

/**
 * Remplit les sept étapes de l'écran guidé.
 *
 * ON PASSE PAR LES ONGLETS, comme un ingénieur. Poser les valeurs par
 * `page.evaluate` court-circuiterait React et n'éprouverait rien de la
 * navigation entre étapes — or c'est précisément elle qui rend visible ce qui
 * manque.
 */
async function remplirLesEtapes({ phiCreep = "2.0", systeme = "simply_supported",
                                  cadresDiametre = "10",
                                  cadresEspacement = "150" } = {}) {
  await page.click("#etape-section");
  for (const [sel, valeur] of [["#vc-b", "300"], ["#vc-h", "600"],
                               ["#vc-d", "550"], ["#vc-leff", "6000"]]) {
    await page.fill(sel, valeur);
  }
  await page.click("#etape-materiaux");
  await page.fill("#vc-beton", "C30/37");
  await page.fill("#vc-acier", "B500B");
  await page.selectOption("#vc-expo", "XC3");

  await page.click("#etape-sollicitations");
  for (const [sel, valeur] of [["#vc-med", "250"], ["#vc-ved", "300"],
                               ["#vc-mchar", "180"], ["#vc-mqp", "120"]]) {
    await page.fill(sel, valeur);
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
  await page.fill("#vc-phicreep", phiCreep);
  if (systeme) await page.selectOption("#vc-systeme", systeme);
}

let projetId = "";
let calculId = "";
//: LES OCTETS RECUS PAR LE NAVIGATEUR. Ils sont renseignes a l'interieur de
//: `corpsDe`, dont l'action declenche le telechargement: la reponse du POST
//: arrive avant que le fichier ne soit ecrit, et les deux doivent etre
//: compares.
let noteRecue = null;
let planRecu = null;

try {
  // =======================================================================
  // 1 — A SE CONNECTE ET CRÉE UN PROJET
  // =======================================================================
  ici("ouverture de la page");
  await page.goto(WEB, { waitUntil: "domcontentloaded" });
  //: LE CHARGEMENT INITIAL EST UN CONTROLE, PAS UN PREALABLE.
  //:
  //: L'erreur d'hydratation React #418 se produisait ICI, avant toute
  //: interaction, a chaque chargement. On attend que le script d'hydratation
  //: ait tourne — l'apparition du formulaire de connexion le prouve — puis on
  //: laisse a React le temps de crier avant de regarder.
  await page.waitForSelector("#connecter", { timeout: 20000 });
  await page.waitForTimeout(1200);
  exige(criees.length === 0,
        "la page a crie au chargement initial (une erreur d'hydratation se "
        + "produit exactement la): " + criees.slice(0, 3).map(enClair).join(" | "));

  ici("connexion de A");
  const liste = await corpsDe("/v1/projects", "GET", () => connecter(A));
  exige(liste.statut === 200, `la liste des projets a rendu ${liste.statut}`);

  ici("creation du projet");
  await page.click("text=Nouveau projet");
  await page.fill("#p-nom", "FICTIF — Halle verification");
  await page.fill("#p-ref", "FICTIF-VC-NAV");
  await page.fill("#p-region", REGION);
  await page.fill("#p-date", DATE_REF);
  const cree = await corpsDe("/v1/projects", "POST",
                             () => page.click("text=Créer le projet"));
  exige(cree.statut === 201, `la creation a rendu ${cree.statut}`);
  projetId = cree.corps?.project_id ?? "";
  exige(/^[0-9a-f-]{36}$/i.test(projetId),
        `la creation n'a pas rendu d'identifiant (« ${projetId} »)`);
  await page.selectOption("#projet", projetId);

  // =======================================================================
  // 2 — LE LANCEMENT EST FERMÉ, ET L'ÉCRAN ÉCRIT CE QUI MANQUE
  // =======================================================================
  //: `phi_creep` ET LE SYSTEME STRUCTURAL N'ONT AUCUN DEFAUT, et c'est
  //: delibere: entre une console (K = 0,4) et une travee intermediaire
  //: (K = 1,5) il y a un facteur presque quatre sur la dispense de fleche. Un
  //: defaut y serait le plus cher des mensonges — il passerait inapercu.
  ici("le lancement est ferme tant que deux decisions manquent");
  await page.waitForSelector("#lancer-verification", { timeout: 15000 });
  exige(await page.isDisabled("#lancer-verification"),
        "le lancement est ouvert alors que phi(inf,t0) et le systeme "
        + "structural ne sont pas choisis");
  const motifVide = await page.locator("#pourquoi-bloque").innerText();
  exige(motifVide.includes("fluage"),
        `le motif ecrit ne nomme pas le fluage: « ${motifVide.slice(0, 200)} »`);
  exige(motifVide.includes("7.4N") || motifVide.includes("système structural"),
        `le motif ecrit ne nomme pas le systeme structural: `
        + `« ${motifVide.slice(0, 200)} »`);

  // =======================================================================
  // 3 — EN MODE STRICT, AVANT CONFIRMATION: UN REFUS QUI NOMME
  // =======================================================================
  ici("refus strict avant confirmation");
  await remplirLesEtapes();
  await page.click("#etape-mode");
  exige(await page.isChecked("#vc-strict"),
        "le mode strict n'est pas le defaut de l'ecran");
  exige(!(await page.isDisabled("#lancer-verification")),
        "le lancement reste ferme alors que les sept etapes sont remplies: "
        + `${await page.locator("#pourquoi-bloque").count()
             ? await page.locator("#pourquoi-bloque").innerText() : "sans motif"}`);

  const avantRefusStrict = criees.length;
  const refuse = await corpsDe(
    "/beam-verifications", "POST",
    () => page.click("#lancer-verification"));
  exige(refuse.statut === 422,
        `la verification stricte sans confirmation a rendu ${refuse.statut}`);
  await consommerRefus(
    avantRefusStrict, { statut: 422, chemin: "/beam-verifications" },
    "refus strict avant confirmation");
  await page.waitForSelector("#refus-verification", { timeout: 15000 });
  const texteRefus = await page.locator("#refus-verification").innerText();
  exige(texteRefus.includes("rien n'a été enregistré")
        || texteRefus.includes("rien n'a ete enregistre")
        || texteRefus.includes("Vérification refusée"),
        `le refus ne dit pas qu'il n'a rien ecrit: `
        + `« ${texteRefus.slice(0, 200)} »`);
  const nommes = await page.locator("#refus-verification ul.bloquants li").count();
  exige(nommes > 0,
        "le refus n'a nomme aucun parametre national: l'ingenieur n'a pas de "
        + "liste de travail");

  //: CHAQUE LIGNE PORTE UN NOM DE PARAMETRE, ET C'EST LE POINT.
  //:
  //: Mesure du 01/09: l'ecran lisait `key` sur des objets qui portent
  //: `parameter`. Onze lignes s'affichaient, chacune avec sa clause et son
  //: annexe — et un `<code>` VIDE a la place du nom. Le refus avait l'air
  //: complet et ne disait pas quoi faire confirmer. Compter les lignes
  //: n'aurait rien vu; il faut regarder ce qu'elles NOMMENT.
  const noms = await page.locator("#refus-verification ul.bloquants li code")
                         .allInnerTexts();
  exige(noms.length === nommes,
        `${nommes} bloquants affiches, ${noms.length} noms de parametre`);
  exige(noms.every((n) => n.trim().length > 0),
        "au moins un parametre bloquant s'affiche SANS NOM: le refus porte une "
        + "liste de travail que l'ingenieur ne peut pas suivre");
  //: ET IL DIT QUEL CHAPITRE LE RECLAME. Un meme parametre sert plusieurs
  //: modules: sans cela, on ne sait pas ce qu'on debloque en le confirmant.
  const premiere = await page.locator("#refus-verification ul.bloquants li")
                             .first().innerText();
  exige(premiere.includes("reclame par"),
        `le refus ne dit pas quel chapitre reclame le parametre: `
        + `« ${premiere.slice(0, 200)} »`);

  //: LE REFUS DE PREFLIGHT N'ECRIT RIEN. Aucun calcul n'a ete tente: une ligne
  //: « refused » laisserait croire que le moteur a repondu.
  const apresRefus = await depuisLaPage(
    `/v1/projects/${projetId}/calculations`);
  exige((apresRefus.corps?.calculations ?? []).length === 0,
        "un refus de preflight a laisse une ligne dans l'historique");

  // =======================================================================
  // 4 — LE QUATRE-YEUX OUVRE CE QU'IL PEUT, ET S'ARRÊTE OÙ LA DONNÉE MANQUE
  // =======================================================================
  //: CE PALIER EST UN FAIT MESURE SUR LA BELGIQUE, PAS UN CONTOURNEMENT.
  //:
  //: Douze des treize parametres que reclament les cinq chapitres portent une
  //: valeur relevee dans la NBN EN 1992-1-1 ANB: le quatre-yeux les confirme.
  //: `w_max` n'en porte AUCUNE — sa fiche dit « NON RELEVE dans le Tableau
  //: 7.1N-ANB » et sa provenance est `national_annex_pending`. Le confirmer
  //: reviendrait a signer un blanc, et la passerelle le refuse.
  //:
  //: Une verification COMPLETE stricte est donc impossible en Belgique
  //: aujourd'hui, et c'est le comportement voulu: la valeur manque dans le
  //: REGISTRE, aucun chemin d'autorite ne l'y met, et le produit ne l'invente
  //: pas. Ce parcours mesure exactement ou le mur se trouve.
  ici("decor: confirmations normatives (A propose)");
  const fiches = await fichesDuRegistre();
  exige(fiches !== null && fiches.size > 0,
        "le plan de charge national n'a pas pu etre lu");

  let reste = (await bloquantsStricts(projetId)).cles;
  const depart = reste.length;
  for (let tour = 0; tour < 6 && reste.length && fiches; tour++) {
    const r = await proposerLesConfirmations(projetId, fiches, reste);
    if (r !== null) { exige(false, `le decor de confirmation a echoue: ${r}`); break; }

    ici(`decor: second regard de V (tour ${tour + 1})`);
    await deconnecter();
    await connecter(V);
    const refusV = await secondRegard();
    if (refusV !== null) {
      exige(false, `le second regard a echoue: ${refusV}`);
      break;
    }
    await deconnecter();
    await connecter(A);
    await page.selectOption("#projet", projetId);

    const apres = (await bloquantsStricts(projetId)).cles;
    //: ON S'ARRETE QUAND LA LISTE NE DECROIT PLUS. Reproposer indefiniment ce
    //: qui ne peut pas etre confirme tournerait sans fin, et l'echec dirait
    //: « delai depasse » au lieu de nommer la cause.
    if (apres.length >= reste.length) { reste = apres; break; }
    reste = apres;
  }
  exige(depart > reste.length,
        `le quatre-yeux n'a debloque aucun parametre (${depart} au depart, `
        + `${reste.length} apres)`);
  exige(reste.join(",") === "EN 1992-1-1:w_max",
        "le mur belge n'est pas celui qu'on croit. Attendu le seul "
        + `« EN 1992-1-1:w_max », obtenu: ${reste.join(", ") || "(aucun)"}`);

  //: ET LE REFUS RESTANT EST UN REFUS, PAS UNE PANNE.
  //:
  //: Mesure du 01/09: `_jeu_superpose` forcait `CONFIRMED` sur cette fiche
  //: d'attente, `NationalParameter.__post_init__` levait, et l'ingenieur
  //: recevait un 500 sans en-tete CORS — donc, dans son navigateur, un
  //: « Failed to fetch » qui ne nommait rien.
  ici("le mur belge est un refus nomme, pas une panne");
  await remplirLesEtapes();
  await page.click("#etape-mode");
  const avantMur = criees.length;
  const mur = await corpsDe("/beam-verifications", "POST",
                            () => page.click("#lancer-verification"));
  exige(mur.statut === 422,
        `le refus restant a rendu ${mur.statut} et non 422`);
  await consommerRefus(avantMur, { statut: 422, chemin: "/beam-verifications" },
                       "le mur belge (w_max)");
  await page.waitForSelector("#refus-verification", { timeout: 15000 });
  const texteMur = await page.locator("#refus-verification").innerText();
  exige(texteMur.includes("w_max"),
        `le refus restant ne nomme pas w_max: « ${texteMur.slice(0, 300) }»`);

  // =======================================================================
  // 5 — L'ÉTUDE COMPLÈTE, EN MODE EXPLORATOIRE ASSUMÉ
  // =======================================================================
  //: LE SEUL CHEMIN HONNETE AUJOURD'HUI EN BELGIQUE. Le mode strict est ferme
  //: par `w_max`; l'exploratoire, lui, est ouvert — et il exige une case
  //: cochee en connaissance de cause, puis porte la mention obligatoire.
  ici("etude complete exploratoire assumee");
  await page.selectOption("#projet", projetId);
  await remplirLesEtapes();
  await page.click("#etape-mode");
  await page.uncheck("#vc-strict");
  exige(await page.isDisabled("#lancer-verification"),
        "decocher le mode strict suffit a lancer: l'exploratoire n'est pas un "
        + "choix assume");
  const motifExplo = await page.locator("#pourquoi-bloque").innerText();
  exige(motifExplo.includes("exploratoire"),
        `le motif ne nomme pas l'exploratoire: « ${motifExplo.slice(0, 200)} »`);
  await page.check("#vc-assume");

  const etude = await corpsDe(
    "/beam-verifications", "POST",
    () => page.click("#lancer-verification"));
  exige(etude.statut === 201, `l'etude a rendu ${etude.statut}`);
  exige(etude.corps?.status === "passed",
        `l'etude n'a pas abouti: ${etude.corps?.status}`);
  exige(etude.corps?.is_exploratory === true,
        "l'etude lancee sans mode strict n'est pas marquee exploratoire");
  exige(etude.corps?.may_be_finalised === false,
        "une etude exploratoire se declare finalisable");
  exige((etude.corps?.sections ?? []).length === 5,
        `l'etude porte ${(etude.corps?.sections ?? []).length} chapitre(s)`);
  calculId = etude.corps?.calculation_id ?? "";

  //: LES CINQ CHAPITRES SONT A L'ECRAN, ET CHACUN PORTE SON ETAT.
  ici("les cinq chapitres a l'ecran");
  await page.waitForSelector("#synthese-etude", { timeout: 20000 });
  for (const cle of ["flexure", "shear", "anchorage", "serviceability",
                     "deflection"]) {
    const ligne = page.locator(`#chapitre-${cle}`);
    exige(await ligne.count() === 1, `le chapitre « ${cle} » n'est pas affiche`);
    if (await ligne.count() === 1) {
      exige(await ligne.getAttribute("data-etat") === "passed",
            `le chapitre « ${cle} » est a l'etat `
            + `« ${await ligne.getAttribute("data-etat")} »`);
    }
  }
  //: ET L'ECRAN DIT POURQUOI ELLE NE SE FINALISERA PAS — sans quoi
  //: l'ingenieur chercherait la cause dans sa section, alors qu'aucune
  //: correction de section n'y changerait rien.
  await page.waitForSelector("#pourquoi-non-finalisable", { timeout: 20000 });
  const pourquoi = await page.locator("#pourquoi-non-finalisable").innerText();
  exige(pourquoi.includes("exploratoire"),
        `l'ecran n'explique pas que l'etude est exploratoire: `
        + `« ${pourquoi.slice(0, 200)} »`);
  const mention = await page.locator("#synthese-etude").innerText();
  exige(mention.includes("NON SIGNABLE"),
        "la mention obligatoire n'est pas affichee sur une etude exploratoire");

  //: LES QUATRE EMPREINTES SONT DISTINCTES, et aucune ne se substitue a une
  //: autre. Les confondre laisserait deux etudes identiques sous des annexes
  //: differentes partager une meme preuve.
  const empreintes = new Set([
    etude.corps?.engineering_inputs_hash, etude.corps?.ndp_snapshot_id,
    etude.corps?.calculation_fingerprint, etude.corps?.execution_identity,
  ]);
  exige(empreintes.size === 4 && !empreintes.has(undefined),
        `les quatre empreintes ne sont pas quatre: ${[...empreintes].length}`);

  // =======================================================================
  // 6 — LA NOTE PDF, TÉLÉCHARGÉE PAR LE NAVIGATEUR
  // =======================================================================
  ici("note PDF depuis l'ecran");
  const noteCree = await corpsDe("/deliverables", "POST", async () => {
    noteRecue = await empreinteDuTelechargement(
      () => page.click("#etude-note-pdf"));
  });
  exige(noteCree.statut === 201, `la note a rendu ${noteCree.statut}`);
  exige(noteCree.corps?.kind === "calculation_note_pdf",
        `la note enregistree est de nature « ${noteCree.corps?.kind} »`);
  exige(noteRecue.sha256 === noteCree.corps?.sha256,
        "les octets recus par le navigateur ne portent pas l'empreinte "
        + `enregistree (recu ${noteRecue.sha256?.slice(0, 12)}, `
        + `base ${noteCree.corps?.sha256?.slice(0, 12)})`);
  exige(noteRecue.texte.startsWith("%PDF-"),
        "le fichier telecharge n'est pas un PDF");

  // =======================================================================
  // 7 — LE PLAN, SANS AUCUN FERRAILLAGE VENU DU NAVIGATEUR
  // =======================================================================
  ici("plan DXF depuis l'ecran");
  const planCree = await corpsDe("/deliverables", "POST", async () => {
    planRecu = await empreinteDuTelechargement(
      () => page.click("#etude-plan-dxf"));
  });
  exige(planCree.statut === 201, `le plan a rendu ${planCree.statut}`);
  exige(planCree.corps?.kind === "rebar_drawing_dxf",
        `le plan enregistre est de nature « ${planCree.corps?.kind} »`);
  exige(planRecu.sha256 === planCree.corps?.sha256,
        "les octets du plan recus ne portent pas l'empreinte enregistree");
  exige(planRecu.texte.includes("SECTION") && planRecu.texte.includes("ENTITIES"),
        "le fichier telecharge n'a pas la structure d'un DXF");

  //: LE FAIT DECISIF DU LOT. Le corps envoye ne porte que l'identifiant du
  //: calcul et le format: ni barres, ni cadres, ni enrobage, ni aire d'acier.
  //: La coupe est gelee avec l'etude, et le serveur la relit.
  const envoi = derniereRequete("/deliverables", "POST");
  exige(envoi !== null, "aucune requete de creation de livrable observee");
  if (envoi) {
    let corpsEnvoye = null;
    try { corpsEnvoye = JSON.parse(envoi.corps ?? "null"); } catch { /* laisse null */ }
    exige(corpsEnvoye !== null,
          `le corps envoye n'est pas lisible: ${(envoi.corps ?? "").slice(0, 200)}`);
    if (corpsEnvoye) {
      exige(corpsEnvoye.reinforcement === undefined
            || corpsEnvoye.reinforcement === null,
            "L'ECRAN A RENVOYE UN FERRAILLAGE. L'etude le porte deja: une "
            + "seconde source divergera, et ce jour-la le plan montrera autre "
            + "chose que ce qui a ete verifie. Corps: "
            + `${JSON.stringify(corpsEnvoye).slice(0, 300)}`);
      exige(Object.keys(corpsEnvoye).sort().join(",") === "calculation_id,format",
            "le corps envoye porte autre chose que l'identifiant et le format: "
            + `${Object.keys(corpsEnvoye).sort().join(",")}`);
    }
  }

  // =======================================================================
  // 8 — L'APERÇU, DU MÊME MODÈLE, ET NON CONTRACTUEL
  // =======================================================================
  ici("apercu du plan");
  const apercu = await corpsDe("/deliverables/preview", "POST",
                               () => page.click("#etude-apercu"));
  exige(apercu.statut === 200, `l'apercu a rendu ${apercu.statut}`);
  await page.waitForSelector("#apercu-du-plan svg", { timeout: 20000 });
  const texteApercu = await page.locator("#apercu-du-plan").innerText();
  exige(texteApercu.includes("APERCU NON CONTRACTUEL"),
        "l'apercu ne se declare pas non contractuel DANS l'image");

  // =======================================================================
  // 9 — APRÈS UN RECHARGEMENT COMPLET: LES MÊMES OCTETS
  // =======================================================================
  ici("rechargement complet");
  await page.goto(WEB, { waitUntil: "domcontentloaded" });
  //: L'HYDRATATION EST OBSERVEE ICI, PAS SUPPOSEE. React signale un ecart
  //: entre le rendu du serveur et celui du client par une exception non
  //: rattrapee, quelques dizaines de millisecondes apres le chargement du
  //: script. Rendre la main tout de suite laisserait le parcours continuer
  //: avant qu'elle n'arrive, et un cri n'est pas un echec s'il tombe apres le
  //: dernier controle.
  await page.waitForSelector("#connecter", { timeout: 15000 });
  await page.waitForTimeout(1200);
  exige(criees.length === 0,
        "la page a crie pendant le rechargement: "
        + criees.slice(0, 3).map(enClair).join(" | "));

  await connecter(A);
  await page.selectOption("#projet", projetId);

  // =======================================================================
  // 9 bis — LA NAVIGATION, ALLER ET RETOUR
  // =======================================================================
  //: UNE PAGE INTROUVABLE FAIT PARTIE DU PRODUIT. Un lien peri­me, une URL
  //: recopiee de travers: l'ecran doit rendre quelque chose de lisible, et
  //: surtout ne rien casser au retour. C'est aussi le seul moyen d'eprouver
  //: que le routeur de Next remonte l'application proprement.
  ici("navigation vers une page absente puis retour");
  const avantNavigation = criees.length;
  const absente = await page.goto(`${WEB}/page-qui-n-existe-pas`,
                                  { waitUntil: "domcontentloaded" });
  exige(absente !== null && absente.status() === 404,
        `une route inconnue a rendu ${absente?.status()} et non 404`);

  await page.goBack({ waitUntil: "domcontentloaded" });
  await page.waitForSelector("#connecter", { timeout: 15000 });
  //: LE SEUL CRI TOLERE ICI EST CELUI QU'ON A PROVOQUE — le 404 de la route
  //: inconnue, sur CETTE url. Tout le reste est un echec, y compris une
  //: seconde 404 ailleurs.
  await consommerRefus(
    avantNavigation,
    { statut: 404, chemin: "/page-qui-n-existe-pas" },
    "navigation vers une route inconnue");
  //: LA SESSION NE SURVIT PAS A UN RECHARGEMENT, ET C'EST LE CONTRAT: aucun
  //: jeton n'est persiste. On se reconnecte donc, comme l'ingenieur le ferait.
  await connecter(A);
  await page.selectOption("#projet", projetId);

  const relue = await depuisLaPage(
    `/v1/projects/${projetId}/beam-verifications/${calculId}`);
  exige(relue.statut === 200, `la relecture a rendu ${relue.statut}`);
  for (const champ of ["engineering_inputs_hash", "ndp_snapshot_id",
                       "calculation_fingerprint", "execution_identity",
                       "status", "max_utilisation"]) {
    exige(relue.corps?.[champ] === etude.corps?.[champ],
          `« ${champ} » a change apres rechargement: `
          + `${JSON.stringify(relue.corps?.[champ])} != `
          + `${JSON.stringify(etude.corps?.[champ])}`);
  }

  //: LE MEME PLAN, DEPUIS UN PROCESSUS QUI N'A PLUS RIEN EN MEMOIRE. Il sort
  //: de la base seule — la coupe gelee — et pas d'un etat de React survivant.
  const replan = await depuisLaPage(
    `/v1/projects/${projetId}/deliverables`, "POST",
    { calculation_id: calculId, format: "dxf" });
  exige(replan.statut === 201,
        `le plan reproduit apres rechargement a rendu ${replan.statut}`);
  exige(replan.corps?.sha256 === planCree.corps?.sha256,
        "le plan reproduit apres rechargement n'a pas les memes octets");

  // =======================================================================
  // 10 — UNE ÉTUDE EN ÉCHEC FERME LES DOCUMENTS, EN DISANT POURQUOI
  // =======================================================================
  //: ON RESTE EN EXPLORATOIRE ASSUME: le mode strict est ferme par `w_max`, et
  //: le sujet ici n'est pas le referentiel mais le VERDICT. Des cadres de 6 a
  //: 300 mm ne reprennent pas 300 kN, l'etude echoue, et rien ne doit pouvoir
  //: en sortir qui se lise comme une conclusion.
  ici("etude en echec");
  await remplirLesEtapes({ cadresDiametre: "6", cadresEspacement: "300" });
  await page.click("#etape-mode");
  //: LE RECHARGEMENT A REMIS L'ECRAN A SON DEFAUT, ET C'EST BIEN CE QU'ON
  //: VEUT: le mode strict est le defaut, un F5 ne conserve pas un choix
  //: d'exploratoire. Il faut donc le reprendre explicitement — comme
  //: l'ingenieur le ferait.
  await page.uncheck("#vc-strict");
  await page.check("#vc-assume");
  const echouee = await corpsDe("/beam-verifications", "POST",
                                () => page.click("#lancer-verification"));
  exige(echouee.statut === 201,
        `l'etude en echec a rendu ${echouee.statut} au lieu d'etre enregistree`);
  exige(echouee.corps?.status === "failed",
        `l'etude aux cadres insuffisants a rendu « ${echouee.corps?.status} »`);
  await page.waitForSelector("#pourquoi-pas-de-document", { timeout: 20000 });
  exige(await page.isDisabled("#etude-note-pdf"),
        "une etude en echec laisse produire une note");
  exige(await page.isDisabled("#etude-plan-dxf"),
        "une etude en echec laisse produire un plan");
  const ferme = await page.locator("#pourquoi-pas-de-document").innerText();
  exige(ferme.includes("conclut"),
        `l'ecran ne dit pas pourquoi le document est ferme: `
        + `« ${ferme.slice(0, 200)} »`);

  //: ET LA ROUTE REFUSE AUSSI. L'ecran explique; il n'interdit pas.
  const avantForcee = criees.length;
  const forcee = await depuisLaPage(
    `/v1/projects/${projetId}/deliverables`, "POST",
    { calculation_id: echouee.corps?.calculation_id, format: "dxf" });
  exige(forcee.statut === 422,
        `la route a rendu ${forcee.statut} pour un calcul en echec`);
  await consommerRefus(avantForcee, { statut: 422, chemin: "/deliverables" },
                       "plan force sur une etude en echec");

  // =======================================================================
  // CONTRÔLE MUTANT — UN 422 HORS GESTE AUTORISÉ DOIT RESTER DANS LA LISTE
  // =======================================================================
  //: CE CONTROLE EPROUVE LE CONTROLE.
  //:
  //: Une premiere redaction ecartait les 422 DANS LE COLLECTEUR, globalement
  //: et sans regarder le chemin. Le parcours annoncait alors une tolerance
  //: « bornee aux gestes volontaires » et en appliquait une aveugle: n'importe
  //: quelle requete secondaire, n'importe quelle regression en 422, a
  //: n'importe quel moment, disparaissait sans laisser de trace.
  //:
  //: On injecte donc un 422 QU'AUCUN GESTE NE RECLAME — et sur la meme route
  //: que des refus tolerés ailleurs, pour que la seule chose qui le distingue
  //: soit l'absence de consommation. S'il n'atterrit pas dans la liste, la
  //: tolerance est redevenue globale et tout ce qui precede ne prouve rien.
  ici("controle mutant: un 422 non reclame fait tomber le parcours");
  const avantMutant = criees.length;
  const injecte = await depuisLaPage(
    `/v1/projects/${projetId}/beam-verifications`, "POST",
    { element: "MUTANT — corps volontairement incomplet" });
  exige(injecte.statut === 422,
        `l'injection a rendu ${injecte.statut} et non 422: le controle mutant `
        + "ne mesure rien");

  //: ON ATTEND LE CRI, puis on constate qu'il EST la.
  const limiteMutant = Date.now() + 8000;
  while (Date.now() < limiteMutant && criees.length === avantMutant) {
    await page.waitForTimeout(100);
  }
  const mutants = criees.slice(avantMutant);
  exige(mutants.length >= 1,
        "UN 422 NON RECLAME N'A PAS ETE COLLECTE. La tolerance est redevenue "
        + "globale: tout ce que ce parcours affirme sur les cris ne vaut plus.");
  exige(mutants.some((c) => /status of 422\b/.test(c.texte)),
        `le cri collecte n'est pas le refus injecte: `
        + `${mutants.slice(0, 2).map(enClair).join(" | ")}`);
  //: ET LE BILAN FINAL AURAIT ECHOUE — c'est ce que `criees.length !== 0` dit.
  exige(criees.length !== 0,
        "la liste est vide apres l'injection: le bilan final ne verrait rien");

  //: On le consomme maintenant, nommement, pour que le parcours puisse
  //: conclure. C'est le seul endroit ou un cri est consomme APRES avoir servi
  //: de preuve.
  await consommerRefus(avantMutant,
                       { statut: 422, chemin: "/beam-verifications" },
                       "controle mutant (injection assumee)");

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

  // =======================================================================
  // LE BILAN DES CRIS, SUR TOUT LE PARCOURS
  // =======================================================================
  //: LES CONTROLES INTERMEDIAIRES REGARDENT DES MOMENTS PRECIS — chargement,
  //: rechargement, navigation. Celui-ci regarde TOUT LE RESTE: la saisie, les
  //: sept etapes, la composition du PDF, la transcription du DXF, l'apercu.
  //: Sans lui, une erreur levee pendant un telechargement passerait entre deux
  //: points de controle.
  await page.waitForTimeout(600);
  exige(criees.length === 0,
        `la page a crie ${criees.length} fois pendant le parcours: `
        + criees.slice(0, 5).map(enClair).join(" | "));

  // =======================================================================
  // CE QUE CE PARCOURS A REELLEMENT PRODUIT
  // =======================================================================
  //: LES CHIFFRES SORTENT DU PARCOURS, PAS D'UN RAPPORT ECRIT A COTE.
  //:
  //: Un compte rendu qui affirme « le PDF fait tant d'octets » sans que rien
  //: ne l'ait mesure vieillit en silence: il reste vrai a l'ecrit longtemps
  //: apres avoir cesse de l'etre. Ces lignes sont produites par l'execution
  //: qui vient de reussir, et elles changent avec elle.
  //:
  //: L'EMPREINTE DU PDF EST LIEE A L'EXECUTION, celle du DXF ne l'est pas. La
  //: note porte la version du moteur et son build — que le harnais renouvelle
  //: a chaque lancement — tandis que le plan ne porte ni date ni build: il ne
  //: decrit qu'une geometrie. Deux executions donnent donc deux notes
  //: differentes et le MEME plan, et c'est ce qu'on veut des deux cotes.
  bilan.push(`etude       ${calculId}`);
  bilan.push(`  empreinte du calcul  ${etude.corps?.calculation_fingerprint}`);
  bilan.push(`  instantane normatif  ${etude.corps?.ndp_snapshot_id}`);
  bilan.push(`  identite d'execution ${etude.corps?.execution_identity}`);
  bilan.push(`note PDF    sha256 ${noteRecue?.sha256} `
             + `(${noteRecue?.taille} octets, ${noteRecue?.nom})`);
  bilan.push(`plan DXF    sha256 ${planRecu?.sha256} `
             + `(${planRecu?.taille} octets, ${planRecu?.nom})`);
} catch (cause) {
  echecs.push(`exception a l'etape « ${etapeCourante} »: ${cause}`);
  try {
    for (const sel of ["#refus-verification", "#pourquoi-bloque",
                       "#pourquoi-pas-de-document", "[role=alert]"]) {
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
  console.log("ROUGE — parcours verification complete depuis le navigateur");
  echecs.forEach((e) => console.log("   - " + e));
  if (criees.length) {
    console.log("   ce que la page a signale:");
    criees.slice(0, 12).forEach((c) => console.log("     · " + enClair(c)));
  }
  process.exit(1);
}
console.log(
  "ok: A cree un projet BE/Wallonie; l'ecran garde le lancement ferme tant que "
  + "le fluage et le systeme structural ne sont pas choisis, et ecrit "
  + "lesquels manquent; en mode strict avant confirmation, la verification est "
  + "refusee, les onze parametres nationaux manquants sont NOMMES a l'ecran "
  + "avec le chapitre qui les reclame, et AUCUNE ligne n'est ecrite; le "
  + "quatre-yeux avec V confirme tout ce qui porte une valeur relevee dans la "
  + "NBN EN 1992-1-1 ANB et s'arrete sur « EN 1992-1-1:w_max », que la fiche "
  + "declare NON RELEVE — un refus nomme, pas une panne, et le mode strict "
  + "reste donc ferme pour une verification COMPLETE en Belgique; l'etude "
  + "complete aboutit en exploratoire assume — cinq chapitres verifies, quatre "
  + "empreintes distinctes, mention « PROJET — NON SIGNABLE » et motif de "
  + "non-finalisation ecrit; la note PDF se telecharge et ses octets portent "
  + "l'empreinte enregistree; le plan DXF se produit avec un corps qui ne "
  + "porte QUE l'identifiant du calcul et le format — aucun ferraillage ne "
  + "part du navigateur; l'apercu sort du meme modele et se dit non "
  + "contractuel; apres un rechargement complet l'etude se relit a l'identique "
  + "et le meme plan ressort avec les memes octets; une etude en echec ferme "
  + "les documents en disant pourquoi, et la route refuse aussi; aucun jeton "
  + "persiste; et la page n'a crie NULLE PART — ni erreur d'hydratation, ni "
  + "exception non rattrapee, ni erreur de console, hors les refus 422 que ce "
  + "parcours provoque expres et le 404 de la route inconnue qu'il visite.",
);
if (bilan.length) {
  console.log("");
  bilan.forEach((l) => console.log("   " + l));
}
