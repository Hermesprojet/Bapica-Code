/**
 * LE JETON DOIT RÉELLEMENT PILOTER LES DÉCISIONS D'AUTORITÉ.
 *
 * CE QUE CE PARCOURS ÉPROUVE, ET QUE RIEN D'AUTRE NE PEUT ÉPROUVER
 * -----------------------------------------------------------------
 * `test_e2e_postgres.py` prouve que l'API exige une identité et que
 * PostgreSQL refuse l'auto-approbation. Il construit ses en-têtes lui-même :
 * il ne dit rien de ce que l'ÉCRAN envoie.
 *
 * Or c'est là qu'était le défaut. `Connexion` gardait la session dans son état
 * local, `sessionValide()` n'était appelée nulle part, et aucune action
 * d'autorité n'existait dans l'interface. Un jeton obtenu et jamais utilisé
 * n'est pas une authentification : c'est une case cochée.
 *
 * LES NEUF FAITS QUE CE PARCOURS ÉTABLIT
 * ---------------------------------------
 *  1. A se connecte, et la requête de proposition porte RÉELLEMENT le Bearer
 *     de A — comparé au jeton que l'émetteur a délivré, pas « non vide » ;
 *  2. aucun corps d'autorité ne nomme d'acteur ;
 *  3. A ne peut pas approuver sa propre décision ;
 *  4. A se déconnecte, et le jeton disparaît : la requête suivante part sans ;
 *  5. B se connecte et approuve ;
 *  6. la décision se consomme UNE fois ;
 *  7. le rejeu est refusé ;
 *  8. une session expirée ne déclenche JAMAIS une requête avec un jeton périmé ;
 *  9. aucun jeton n'apparaît dans `localStorage`, `sessionStorage`, les
 *     cookies ou une URL.
 *
 * ON OBSERVE LES REQUÊTES SORTANTES, PAS L'ÉTAT DE REACT. L'écran peut
 * afficher ce qu'il veut : ce qui compte est l'octet qui part sur le réseau.
 */
import { chargerChromium, cheminChromium } from "./playwright.mjs";

const WEB = process.env.EUROSTRUCT_WEB || "http://localhost:3000";
const API = process.env.EUROSTRUCT_API || "http://127.0.0.1:8000";

const A = { courriel: "a@fictif.invalid", mdp: "FICTIF-A" };
const B = { courriel: "b@fictif.invalid", mdp: "FICTIF-B" };
//: DEUX COMPTES A JETON COURT, ET ILS N'EPROUVENT PAS LA MEME CHOSE.
//: Le premier reçoit un jeton de renouvellement: à l'échéance, l'écran doit
//: renouveler en mémoire et repartir avec le jeton NEUF. Le second n'en reçoit
//: aucun: l'écran doit fermer la session et ne plus rien envoyer.
const RENOUVELABLE = { courriel: "court@fictif.invalid", mdp: "FICTIF-COURT" };
const SANS_RENOUVELLEMENT = { courriel: "sec@fictif.invalid", mdp: "FICTIF-SEC" };

const echecs = [];
const exige = (ok, message) => {
  if (!ok) echecs.push(message);
};

//: OU EN EST-ON QUAND CA CASSE. Une exception de Playwright nomme le selecteur
//: ou le delai, jamais l'etape du parcours: « Timeout 15000ms exceeded » ne dit
//: pas laquelle des quatre connexions a echoue. Ce marqueur le dit.
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
 * CE QUE LA PAGE A CRIE, ET QU'ON NE VOYAIT PAS.
 *
 * Un composant qui lève au rendu produit une page sans bouton, et le parcours
 * echoue alors sur « selecteur introuvable » ou sur un delai — un diagnostic
 * qui parle de Playwright et jamais de la cause. On garde donc les erreurs de
 * la page et on les rend AVEC l'echec.
 */
const criees = [];
page.on("pageerror", (e) => criees.push(`erreur de page: ${e.message}`));
page.on("console", (m) => {
  if (m.type() === "error") criees.push(`console: ${m.text()}`);
});
page.on("requestfailed", (r) => {
  criees.push(`requete echouee: ${r.method()} ${r.url()} — ${r.failure()?.errorText}`);
});

/** Tout ce qui part vers l'API d'autorité: méthode, URL, en-tête, corps. */
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

/**
 * Les jetons que l'ÉMETTEUR a délivrés.
 *
 * ON LES LIT SUR LA RÉPONSE QU'ON VIENT D'ATTENDRE, jamais dans un tableau
 * rempli par un écouteur en tâche de fond. Un écouteur `async` termine son
 * `json()` APRÈS que `waitForResponse` a résolu : lire « le dernier jeton du
 * tableau » juste après l'attente rend alors l'avant-dernier, et le cas conclut
 * « le renouvellement n'a produit aucun jeton différent » alors qu'il en a
 * produit un. Mesuré ici même.
 *
 * Le tableau ne sert donc qu'au balayage final des stockages, où l'ordre et la
 * fraîcheur n'importent pas.
 */
const jetonsDelivres = [];

/** Attend une délivrance de jeton et rend CELUI de cette réponse-là. */
async function jetonDe(attente) {
  const reponse = await attente;
  const corps = await reponse.json();
  if (!corps?.access_token) return null;
  jetonsDelivres.push(corps.access_token);
  return corps.access_token;
}

const attenteJeton = (delai) =>
  page.waitForResponse(
    (r) => r.url().includes("/auth/v1/token") && r.request().method() === "POST",
    { timeout: delai },
  );

const versAutorite = () => requetes.filter((r) => r.url.includes("/v1/authority/"));

async function connecter({ courriel, mdp }) {
  await page.fill("#courriel", courriel);
  await page.fill("#mdp", mdp);
  const delivre = attenteJeton(15000);
  await page.click("#connecter");
  const jeton = await jetonDe(delivre);
  await page.waitForSelector("#deconnecter", { timeout: 15000 });
  return jeton;
}

/** Attend qu'une requête d'autorité soit REÇUE, puis rend la dernière. */
async function agir(selecteur, motif) {
  const attente = page.waitForResponse(
    (r) => r.url().includes(motif) && r.request().method() === "POST",
    { timeout: 20000 },
  );
  await page.click(selecteur);
  const reponse = await attente;
  return { statut: reponse.status(), requete: versAutorite().at(-1) };
}

try {
  await page.goto(WEB, { waitUntil: "networkidle" });

  // ================================================================ 1. A
  ici("1-connexion-A");
  const jetonA = await connecter(A);
  exige(Boolean(jetonA), "l'emetteur n'a delivre aucun jeton a A");

  const proposition = await agir("#proposer", "/v1/authority/decisions");
  exige(proposition.statut === 201,
        `la proposition de A rend ${proposition.statut}, attendu 201`);

  // LE FAIT CENTRAL: l'octet qui part porte le jeton de A, pas « un » jeton.
  exige(proposition.requete?.autorisation === `Bearer ${jetonA}`,
        "la requete de proposition ne porte pas le Bearer que l'emetteur a " +
        `delivre a A (recu: ${proposition.requete?.autorisation ? "un autre en-tete" : "aucun en-tete"})`);

  // AUCUN CORPS NE NOMME D'ACTEUR. Un champ qui l'accepterait rendrait la
  // verification de signature decorative: il suffirait de mentir dans le corps.
  const corpsProposition = proposition.requete?.corps ?? "";
  for (const interdit of ["actor_id", "proposer_id", "approver_id",
                          "proposant", "approbateur"]) {
    exige(!corpsProposition.includes(interdit),
          `le corps de la proposition contient « ${interdit} »`);
  }

  const decision = (await page.locator("#decision-id").textContent())?.trim();
  exige(Boolean(decision) && decision !== "—",
        "l'ecran n'affiche pas l'identifiant de la decision creee");

  // ============================================ 2. A ne s'approuve pas
  ici("2-auto-approbation");
  const autoApprobation = await agir("#approuver", "/approval");
  exige(autoApprobation.statut === 422,
        `A a pu approuver sa propre decision (${autoApprobation.statut})`);
  exige(autoApprobation.requete?.autorisation === `Bearer ${jetonA}`,
        "la tentative d'auto-approbation n'a pas porte le jeton de A");

  // ==================================================== 3. A se deconnecte
  ici("3-deconnexion-A");
  await page.click("#deconnecter");
  await page.waitForSelector("#connecter", { timeout: 10000 });

  const avantDeconnexion = versAutorite().length;
  await page.click("#approuver");
  await page.waitForTimeout(1200);
  const apresDeconnexion = versAutorite().slice(avantDeconnexion);
  // LE JETON DE A NE DOIT PLUS EXISTER. Ni utilise, ni conserve.
  exige(!apresDeconnexion.some((r) => r.autorisation?.includes(jetonA)),
        "une requete a porte le jeton de A APRES la deconnexion");

  // ...MAIS L'IDENTIFIANT DE DECISION SURVIT: c'est lui que B doit reprendre.
  const apresSortie = (await page.locator("#decision-id").textContent())?.trim();
  exige(apresSortie === decision,
        "l'identifiant de decision a ete perdu a la deconnexion; B ne peut " +
        "plus reprendre le dossier de A");

  // ============================================== 4. B approuve, consomme
  ici("4-connexion-B");
  const jetonB = await connecter(B);
  exige(jetonB !== jetonA, "B a recu le meme jeton que A");

  const approbation = await agir("#approuver", "/approval");
  exige(approbation.statut === 204,
        `l'approbation par B rend ${approbation.statut}, attendu 204`);
  exige(approbation.requete?.autorisation === `Bearer ${jetonB}`,
        "l'approbation ne porte pas le Bearer de B");

  const consommation = await agir("#consommer", "/consumption");
  exige(consommation.statut === 200,
        `la consommation rend ${consommation.statut}, attendu 200`);

  // ================================================== 5. le rejeu est refuse
  ici("5-rejeu");
  const rejeu = await agir("#consommer", "/consumption");
  exige(rejeu.statut === 422,
        `le rejeu de la consommation rend ${rejeu.statut}, attendu 422`);

  // ================================ 6. l'expiration, avec renouvellement
  ici("6-renouvellement");
  //
  // Le jeton perime, un jeton de renouvellement existe: l'ecran renouvelle EN
  // MEMOIRE et repart avec le jeton NEUF. C'est la moitie agreable du
  // probleme, et elle doit tenir sans que l'utilisateur voie quoi que ce soit.
  await page.click("#deconnecter");
  await page.waitForSelector("#connecter", { timeout: 10000 });
  const jetonCourt = await connecter(RENOUVELABLE);

  // Le minuteur du fournisseur declenche l'echange tout seul: on n'appuie sur
  // rien, on regarde partir.
  const jetonNeuf = await jetonDe(attenteJeton(30000));
  exige(jetonNeuf !== jetonCourt,
        "le renouvellement n'a pas produit de jeton different");

  const apresRenouvellement = await agir("#proposer", "/v1/authority/decisions");
  exige(apresRenouvellement.requete?.autorisation !== `Bearer ${jetonCourt}`,
        "une requete est partie avec le jeton PERIME alors qu'il venait " +
        "d'etre renouvele");
  exige(apresRenouvellement.requete?.autorisation === `Bearer ${jetonNeuf}`,
        "la requete ne porte pas le jeton issu du renouvellement");

  // ============ 7. se deconnecter PENDANT un renouvellement ne rouvre rien
  ici("7-deconnexion-en-vol");
  //
  // CE QUE CE CAS A TROUVE, ET QU'AUCUN AUTRE NE POUVAIT TROUVER. Le
  // renouvellement est un aller-retour reseau. En se deconnectant pendant
  // celui-ci, la reponse revenait apres coup et ROUVRAIT la session — avec un
  // jeton frais, et sans que rien a l'ecran ne le dise. Le compte a jeton
  // court renouvelle toutes les cinq secondes: la fenetre n'a rien d'exotique,
  // et le parcours est tombe dedans tout seul avant qu'on l'ecrive.
  //
  // On vise donc la fenetre exprès: on attend le DEPART de l'echange, et on
  // clique « se deconnecter » avant qu'il ne revienne.
  // L'emetteur du decor retarde deliberement les renouvellements: sans cela
  // l'echange est deja termine quand le clic part, et la fenetre visee n'existe
  // pas. Le cas passait alors au vert AVEC le defaut present.
  const echangeParti = page.waitForRequest(
    (r) => r.url().includes("/auth/v1/token") && r.method() === "POST",
    { timeout: 30000 },
  );
  await echangeParti;
  await page.click("#deconnecter");   // la reponse est encore en vol
  await page.waitForTimeout(4000);    // de quoi la laisser revenir, et agir
  exige(await page.locator("#connecter").count() > 0,
        "une deconnexion pendant un renouvellement en vol a ete annulee par " +
        "la reponse: la session s'est ROUVERTE toute seule");

  const avantResurrection = versAutorite().length;
  await page.click("#proposer");
  await page.waitForTimeout(1200);
  exige(versAutorite().length === avantResurrection,
        "une requete d'autorite est partie apres une deconnexion survenue " +
        "pendant un renouvellement");

  // ========================= 8. l'expiration SANS renouvellement possible
  ici("8-expiration-seche");
  //
  // LE CAS QUI COMPTE LE PLUS. Aucun jeton de renouvellement: l'ecran doit
  // FERMER la session. Un jeton perime envoye quand meme est un 401 de plus
  // dans les journaux, et surtout la preuve que l'ecran ne sait pas ce qu'il
  // detient.
  const jetonSec = await connecter(SANS_RENOUVELLEMENT);

  // ON N'INTERROMPT PAS LE PARCOURS SI LE BANDEAU MANQUE.
  //
  // Attendre le selecteur et laisser l'attente LEVER faisait tout tenir a un
  // seul fait: en retirant la fermeture du minuteur, le cas tombait bien, mais
  // sur « waitForSelector: Timeout 30000ms » — un diagnostic qui parle de
  // Playwright et jamais du defaut. On note l'absence du bandeau, PUIS on va
  // regarder ce qui part sur le reseau: c'est la, et pas a l'ecran, que se
  // decide si un jeton perime a ete envoye.
  await page.waitForSelector("#session-expiree", { timeout: 25000 })
    .catch(() => {});
  exige(await page.locator("#session-expiree").count() > 0,
        "une session expiree sans renouvellement possible n'est pas signalee " +
        "a l'ecran: l'utilisateur croit sa session ouverte");

  const avantPeremption = versAutorite().length;
  await page.click("#proposer");
  await page.waitForTimeout(1500);
  const apresPeremption = versAutorite().slice(avantPeremption);
  exige(!apresPeremption.some((r) => r.autorisation?.includes(jetonSec)),
        "une requete est partie avec un jeton PERIME");
  exige(apresPeremption.length === 0,
        "une requete d'autorite est partie alors que la session avait expire " +
        `sans pouvoir etre renouvelee (${apresPeremption.length} requete(s))`);

  // ========================================== 9. rien dans les stockages
  ici("9-stockages");
  //
  // EN DERNIER, POUR COUVRIR TOUS LES JETONS DELIVRES — A, B, les deux
  // ephemeres et celui du renouvellement. On cherche le jeton LUI-MEME, pas un
  // nom de cle: une implementation qui le rangerait sous « x » passerait un
  // controle par nom.
  const stockages = await page.evaluate(() => {
    const vider = (s) => {
      const o = {};
      for (let i = 0; i < s.length; i += 1) {
        const k = s.key(i);
        o[k] = s.getItem(k);
      }
      return o;
    };
    return {
      local: vider(window.localStorage),
      session: vider(window.sessionStorage),
      cookie: document.cookie,
      url: window.location.href,
    };
  });
  const tout = JSON.stringify(stockages);
  for (const jeton of jetonsDelivres) {
    exige(!tout.includes(jeton),
          "un jeton delivre est persiste dans le navigateur (localStorage, " +
          "sessionStorage, cookie ou URL)");
    // Un JWT se reconnait aussi a sa charge utile seule.
    exige(!tout.includes(jeton.split(".")[1]),
          "la charge utile d'un jeton est persistee dans le navigateur");
  }
  exige(!/eyJ[A-Za-z0-9_-]{10,}/.test(tout),
        "quelque chose qui ressemble a un JWT est persiste dans le navigateur");
  exige(jetonsDelivres.length >= 5,
        `seulement ${jetonsDelivres.length} jeton(s) delivre(s): le parcours ` +
        "n'a pas traverse les cinq sessions attendues");
} catch (cause) {
  echecs.push(`exception a l'etape « ${etapeCourante} »: ${cause}`);
} finally {
  await nav.close();
}

if (echecs.length) {
  console.log("ROUGE — parcours authentifie d'autorite");
  echecs.forEach((e) => console.log("   - " + e));
  if (criees.length) {
    console.log("   ce que la page a signale:");
    criees.slice(0, 12).forEach((c) => console.log("     · " + c));
  }
  process.exit(1);
}
console.log(
  "ok: A propose sous son propre Bearer, ne s'approuve pas, se deconnecte; " +
  "B approuve et consomme une fois; le rejeu est refuse; aucun jeton " +
  "persiste; une session expiree n'emet plus rien.",
);
