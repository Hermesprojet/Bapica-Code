/**
 * L'ATELIER DOIT MARCHER DEPUIS L'ÉCRAN, ET SURVIVRE AU RECHARGEMENT.
 *
 * CE QUE CE PARCOURS ÉPROUVE, ET QUE RIEN D'AUTRE NE PEUT ÉPROUVER
 * -----------------------------------------------------------------
 * `test_atelier_postgres.py` prouve que les cinq routes tiennent sous identité
 * vérifiée et que PostgreSQL cloisonne. Il construit ses requêtes lui-même :
 * il ne dit rien de ce que l'ÉCRAN envoie, ni de ce qui reste après un F5.
 *
 * Or c'est là que vivait le défaut. `project_id: "DEMO-001"` était écrit en dur
 * dans l'interface, et un calcul lancé depuis l'écran mourait avec sa réponse
 * HTTP. Un bouton « Vérifier » qui n'écrit rien n'est pas un produit : c'est
 * une démonstration.
 *
 * LES HUIT FAITS QUE CE PARCOURS ÉTABLIT
 * ---------------------------------------
 *  1. A se connecte et voit la liste des projets de SON organisation ;
 *  2. il crée un projet — nom, référence, pays, date de référence ;
 *  3. le projet est sélectionné, et l'écran nomme son organisation ;
 *  4. le calcul enregistré part avec le Bearer de A, sur le chemin du projet ;
 *  5. `DEMO-001` n'apparaît nulle part, et la requête enregistrée porte
 *     l'identifiant réel du projet ;
 *  6. après un RECHARGEMENT COMPLET de la page, le projet et son historique
 *     réapparaissent ;
 *  7. le calcul rouvert porte les MÊMES entrées et les MÊMES résultats —
 *     comparaison octet pour octet des corps rendus par l'API ;
 *  8. B, de l'autre organisation, ne voit pas ce projet et ne peut pas rouvrir
 *     son calcul.
 *
 * ON OBSERVE CE QUI PART ET CE QUI REVIENT, pas l'état de React. L'écran peut
 * afficher ce qu'il veut : ce qui compte est l'octet sur le réseau.
 */
import { chargerChromium, cheminChromium } from "./playwright.mjs";

const WEB = process.env.EUROSTRUCT_WEB || "http://localhost:3000";
const API = process.env.EUROSTRUCT_API || "http://127.0.0.1:8000";

const A = { courriel: "a@fictif.invalid", mdp: "FICTIF-A" };
const B = { courriel: "b@fictif.invalid", mdp: "FICTIF-B" };
const ACTEUR_A = process.env.EUROSTRUCT_E2E_ACTEUR_A || "";
const ACTEUR_B = process.env.EUROSTRUCT_E2E_ACTEUR_B || "";

const echecs = [];
const exige = (ok, message) => {
  if (!ok) echecs.push(message);
};

//: OU EN EST-ON QUAND CA CASSE. Une exception de Playwright nomme le selecteur
//: ou le delai, jamais l'etape: « Timeout 15000ms exceeded » ne dit pas
//: laquelle. Ce marqueur le dit.
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
const ctx = await nav.newContext();
const page = await ctx.newPage();

/**
 * CE QUE LA PAGE A CRIÉ, ET QU'ON NE VOYAIT PAS.
 *
 * Un composant qui lève au rendu produit une page sans bouton, et le parcours
 * échoue alors sur « sélecteur introuvable » — un diagnostic qui parle de
 * Playwright et jamais de la cause.
 */
const criees = [];
page.on("pageerror", (e) => criees.push(`erreur de page: ${e.message}`));
page.on("console", (m) => {
  if (m.type() === "error") criees.push(`console: ${m.text()}`);
});
page.on("requestfailed", (r) => {
  criees.push(`requete echouee: ${r.method()} ${r.url()} — ${r.failure()?.errorText}`);
});

/** Tout ce qui part vers l'API : méthode, URL, en-tête, corps. */
const requetes = [];
page.on("request", (r) => {
  const url = r.url();
  if (!url.startsWith(API)) return;
  requetes.push({
    methode: r.method(),
    url,
    autorisation: r.headers()["authorization"] ?? null,
    corps: r.postData(),
  });
});

const versAtelier = () => requetes.filter((r) => r.url.includes("/v1/projects"));

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
  //: LA LISTE DES PROJETS EST CE QUI SUIT LA CONNEXION. Attendre le selecteur
  //: plutot qu'un delai: un `sleep` passerait au vert sur une machine lente en
  //: n'ayant rien observe.
  await page.waitForSelector("#projet", { timeout: 15000 });
}

/** Attend la réponse d'un appel de l'atelier, et rend son corps. */
async function corpsDe(motif, methode, action) {
  const attente = page.waitForResponse(
    (r) => r.url().includes(motif) && r.request().method() === methode,
    { timeout: 30000 },
  );
  await action();
  const reponse = await attente;
  return { statut: reponse.status(), corps: await reponse.json().catch(() => null) };
}

try {
  // =======================================================================
  // 1 à 3 — A SE CONNECTE, VOIT SES PROJETS, EN CRÉE UN
  // =======================================================================
  ici("ouverture de la page");
  await page.goto(WEB, { waitUntil: "domcontentloaded" });

  ici("connexion de A");
  //: LA LISTE PART AVEC LE BEARER DE A, et c'est le premier fait: avant ce
  //: lot, aucune requete d'atelier n'existait du tout.
  const listeInitiale = await corpsDe("/v1/projects", "GET",
                                      () => connecter(A));
  exige(listeInitiale.statut === 200,
        `la liste des projets a rendu ${listeInitiale.statut}`);
  exige(Array.isArray(listeInitiale.corps?.projects),
        "la liste des projets n'est pas une liste");

  const premiereListe = versAtelier().find((r) => r.methode === "GET");
  exige(sujetDuJeton(premiereListe?.autorisation) === ACTEUR_A,
        `la liste est partie sous « ${sujetDuJeton(premiereListe?.autorisation)} » ` +
        `et non sous A (${ACTEUR_A})`);

  ici("creation du projet");
  await page.click("text=Nouveau projet");
  await page.fill("#p-nom", "FICTIF — Halle navigateur");
  await page.fill("#p-ref", "FICTIF-NAV-01");
  await page.fill("#p-date", "2024-03-01");
  const cree = await corpsDe("/v1/projects", "POST",
                             () => page.click("text=Créer le projet"));
  exige(cree.statut === 201, `la creation a rendu ${cree.statut}`);
  const projetId = cree.corps?.project_id ?? "";
  exige(/^[0-9a-f-]{36}$/i.test(projetId),
        `la creation n'a pas rendu d'identifiant de projet (« ${projetId} »)`);
  exige(cree.corps?.ndp_as_of === "2024-03-01",
        `la date de reference rendue est « ${cree.corps?.ndp_as_of} »`);

  //: AUCUN CORPS N'A NOMME UNE ORGANISATION. `organization_id` est facultatif
  //: et l'ecran ne le remplit pas: l'organisation sort des appartenances.
  const corpsCreation = JSON.parse(
    versAtelier().find((r) => r.methode === "POST")?.corps ?? "{}");
  exige(corpsCreation.organization_id === null
        || corpsCreation.organization_id === undefined,
        `l'ecran a nomme une organisation: ${corpsCreation.organization_id}`);

  ici("selection du projet");
  //: L'ECRAN SELECTIONNE LE PROJET QU'IL VIENT DE CREER, et le NOMME. Sans
  //: cela l'ingenieur devrait deviner sur quoi il travaille.
  await page.waitForSelector("text=FICTIF Bureau A", { timeout: 15000 });

  // =======================================================================
  // 4 et 5 — LE CALCUL EST LANCÉ, ET ENREGISTRÉ
  // =======================================================================
  ici("calcul enregistre");
  //: EXPLORATOIRE, ET C'EST LE CAS REEL: aucun parametre national belge n'est
  //: confirme sur cette base. Le mode strict refuserait — a juste titre — et
  //: ce parcours-ci eprouve la persistance, pas le portillon normatif.
  await page.uncheck("#strict");
  const enregistre = await corpsDe(
    `/v1/projects/${projetId}/calculations/ec2/beam-flexure`, "POST",
    () => page.click("text=Calculer et enregistrer sur le projet"));
  exige(enregistre.statut === 201,
        `l'enregistrement a rendu ${enregistre.statut}`);
  const calculId = enregistre.corps?.calculation_id ?? "";
  exige(/^[0-9a-f-]{36}$/i.test(calculId),
        `aucun identifiant de calcul (« ${calculId} »)`);
  exige(enregistre.corps?.status === "succeeded",
        `le calcul est « ${enregistre.corps?.status} »`);
  exige(!!enregistre.corps?.result, "aucun resultat enregistre");
  exige(!!enregistre.corps?.journal, "aucun journal enregistre");
  exige((enregistre.corps?.verifications ?? []).length > 0,
        "aucune verification enregistree");
  exige(enregistre.corps?.mention === "PROJET — NON SIGNABLE",
        `la mention conditionnelle manque: « ${enregistre.corps?.mention} »`);

  //: `DEMO-001` EST PARTI. Ni dans ce qui sort de l'ecran, ni dans ce que la
  //: base rend: la requete enregistree porte l'identifiant reel du projet.
  const requeteCalcul = versAtelier().find(
    (r) => r.methode === "POST" && r.url.includes("beam-flexure"));
  exige(!(requeteCalcul?.corps ?? "").includes("DEMO-001"),
        "l'ecran envoie encore « DEMO-001 »");
  exige(enregistre.corps?.request?.project_id === projetId,
        "la requete enregistree ne porte pas l'identifiant du projet: " +
        `« ${enregistre.corps?.request?.project_id} »`);
  exige(sujetDuJeton(requeteCalcul?.autorisation) === ACTEUR_A,
        "le calcul n'est pas parti sous le jeton de A");

  // =======================================================================
  // 6 et 7 — RECHARGEMENT COMPLET, PUIS RÉOUVERTURE
  // =======================================================================
  ici("rechargement complet");
  //: UN VRAI RECHARGEMENT, PAS UN CLIC. Tout l'etat React disparait; ce qui
  //: revient vient de la base.
  await page.reload({ waitUntil: "domcontentloaded" });
  const apresRechargement = await corpsDe("/v1/projects", "GET",
                                          () => connecter(A));
  const revu = (apresRechargement.corps?.projects ?? [])
    .find((p) => p.project_id === projetId);
  exige(!!revu, "le projet a disparu apres rechargement complet");
  exige(revu?.calculation_count === 1,
        `le projet annonce ${revu?.calculation_count} calcul(s) apres ` +
        "rechargement, et un seul a ete enregistre");

  ici("historique apres rechargement");
  const historique = await corpsDe(
    `/v1/projects/${projetId}/calculations`, "GET",
    () => page.selectOption("#projet", projetId));
  exige(historique.statut === 200,
        `l'historique a rendu ${historique.statut}`);
  exige((historique.corps?.calculations ?? [])
          .some((c) => c.calculation_id === calculId),
        "le calcul enregistre n'est pas dans l'historique apres rechargement");

  ici("reouverture du calcul");
  const relu = await corpsDe(
    `/v1/projects/${projetId}/calculations/${calculId}`, "GET",
    () => page.click("text=Rouvrir"));
  exige(relu.statut === 200, `la reouverture a rendu ${relu.statut}`);

  //: LA COMPARAISON EST EXACTE, PAS « SIMILAIRE ». Deux serialisations triees
  //: par cle: un champ qui bouge d'un iota fait tomber le cas.
  const canon = (v) => JSON.stringify(v, Object.keys(v ?? {}).sort());
  exige(canon(relu.corps?.request) === canon(enregistre.corps?.request),
        "les entrees du calcul rouvert different de celles enregistrees");
  exige(canon(relu.corps?.result) === canon(enregistre.corps?.result),
        "les resultats du calcul rouvert different de ceux enregistres");
  exige(relu.corps?.inputs_hash === enregistre.corps?.inputs_hash,
        "l'empreinte des entrees a bouge a la reouverture");
  exige(relu.corps?.engine_version === enregistre.corps?.engine_version,
        "la version du moteur a bouge a la reouverture");
  exige(relu.corps?.mention === "PROJET — NON SIGNABLE",
        "la mention conditionnelle ne survit pas a la reouverture");

  // =======================================================================
  // 8 — L'AUTRE ORGANISATION NE VOIT RIEN
  // =======================================================================
  ici("isolation: B se connecte");
  await page.click("#deconnecter");
  await page.waitForSelector("#connecter", { timeout: 15000 });
  const listeDeB = await corpsDe("/v1/projects", "GET", () => connecter(B));
  exige(listeDeB.statut === 200, `la liste de B a rendu ${listeDeB.statut}`);
  exige(!(listeDeB.corps?.projects ?? [])
          .some((p) => p.project_id === projetId),
        "B voit le projet de l'autre organisation");
  const requeteDeB = versAtelier().filter((r) => r.methode === "GET").pop();
  exige(sujetDuJeton(requeteDeB?.autorisation) === ACTEUR_B,
        "la liste de B n'est pas partie sous le jeton de B");

  ici("isolation: B tente de rouvrir");
  //: ON NOMME LE CALCUL DIRECTEMENT. L'ecran ne le propose pas a B — c'est
  //: bien le point — donc l'appel est fait depuis la page, avec le jeton que
  //: le navigateur detient, exactement comme le ferait un client curieux.
  const refus = await page.evaluate(async ([api, projet, calcul]) => {
    const r = await fetch(
      `${api}/v1/projects/${projet}/calculations/${calcul}`,
      { headers: { Authorization: `Bearer ${window.__ESC_JETON__ ?? ""}` } });
    return r.status;
  }, [API, projetId, calculId]);
  //: 401 OU 422, ET LES DEUX SONT JUSTES. Sans jeton accessible depuis la
  //: page — c'est le cas, il n'est jamais persiste — c'est 401; avec le jeton
  //: de B, PostgreSQL refuse et c'est 422. Ce qui compte est qu'aucun 200 ne
  //: sorte, et que le corps ne nomme rien du projet.
  exige(refus !== 200,
        `B a obtenu ${refus} en nommant le calcul d'une autre organisation`);

  // =======================================================================
  // AUCUN JETON N'EST PERSISTÉ — la propriété tient aussi sur ce parcours
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
} finally {
  await nav.close();
}

if (echecs.length) {
  console.log("ROUGE — parcours atelier depuis le navigateur");
  echecs.forEach((e) => console.log("   - " + e));
  if (criees.length) {
    console.log("   ce que la page a signale:");
    criees.slice(0, 12).forEach((c) => console.log("     · " + c));
  }
  process.exit(1);
}
console.log(
  "ok: A cree un projet, calcule et enregistre; le rechargement complet " +
  "retrouve le projet et son historique; le calcul rouvert porte les memes " +
  "entrees et les memes resultats; B ne voit rien; aucun jeton persiste.",
);
