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
 * LES FAITS QUE CE PARCOURS ÉTABLIT
 * ----------------------------------
 *  1. A se connecte et voit la liste des projets de SON organisation ;
 *  2. il crée un projet — nom, référence, pays, **région**, date de référence ;
 *  3. le projet est sélectionné, l'écran nomme son organisation, et le
 *     référentiel est **verrouillé** : le sélecteur de pays est désactivé et
 *     porte celui du dossier ;
 *  4. **substituer un contexte français est impossible** — un corps annonçant
 *     `country=FR` et `as_of=2030-01-01` sur un projet BE daté de 2024 obtient
 *     un 422, envoyé avec le jeton réel du navigateur ;
 *  5. le calcul enregistré part avec le Bearer de A, sur le chemin du projet,
 *     et `DEMO-001` n'apparaît nulle part ;
 *  6. après un RECHARGEMENT COMPLET, le projet et son historique réapparaissent
 *     et le calcul rouvert porte les MÊMES entrées et résultats ;
 *  7. **la note se télécharge par le bouton**, et porte le contexte du projet,
 *     le SHA exact du moteur, les deux empreintes et le MÊME taux de travail ;
 *  8. B, de l'autre organisation, n'obtient ni la réouverture ni la note — avec
 *     son propre jeton valide, et sans que le refus laisse rien filtrer.
 *
 * ON OBSERVE CE QUI PART ET CE QUI REVIENT, pas l'état de React. L'écran peut
 * afficher ce qu'il veut : ce qui compte est l'octet sur le réseau.
 */
import { readFile } from "node:fs/promises";

import { chargerChromium, cheminChromium } from "./playwright.mjs";

const WEB = process.env.EUROSTRUCT_WEB || "http://localhost:3000";
const API = process.env.EUROSTRUCT_API || "http://127.0.0.1:8000";

const A = { courriel: "a@fictif.invalid", mdp: "FICTIF-A" };
const B = { courriel: "b@fictif.invalid", mdp: "FICTIF-B" };
const ACTEUR_A = process.env.EUROSTRUCT_E2E_ACTEUR_A || "";
const ACTEUR_B = process.env.EUROSTRUCT_E2E_ACTEUR_B || "";

//: LE CONTEXTE NORMATIF DU PROJET. Les trois valeurs se figent a la creation
//: et aucun calcul du dossier ne peut en designer d'autres.
const PAYS = "BE";
const REGION = "Wallonie";
const DATE_REF = "2024-03-01";
//: CE QU'UN CLIENT TENTERAIT DE SUBSTITUER.
const PAYS_INTRUS = "FR";

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
  await page.fill("#p-region", REGION);
  await page.fill("#p-date", DATE_REF);
  const cree = await corpsDe("/v1/projects", "POST",
                             () => page.click("text=Créer le projet"));
  exige(cree.statut === 201, `la creation a rendu ${cree.statut}`);
  const projetId = cree.corps?.project_id ?? "";
  exige(/^[0-9a-f-]{36}$/i.test(projetId),
        `la creation n'a pas rendu d'identifiant de projet (« ${projetId} »)`);
  exige(cree.corps?.ndp_as_of === DATE_REF,
        `la date de reference rendue est « ${cree.corps?.ndp_as_of} »`);
  exige(cree.corps?.region === REGION,
        `la region rendue est « ${cree.corps?.region} »`);
  exige(cree.corps?.country === PAYS,
        `le pays rendu est « ${cree.corps?.country} »`);

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

  ici("le referentiel est verrouille a l'ecran");
  //: LE SELECTEUR DE PAYS EST DESACTIVE ET PORTE CELUI DU PROJET. Un champ
  //: modifiable donnerait a croire que le referentiel se choisit calcul par
  //: calcul, ce que la base refuse de toute facon.
  exige(await page.isDisabled("#pays"),
        "le selecteur de pays reste modifiable alors qu'un projet est choisi");
  exige(await page.inputValue("#pays") === PAYS,
        `le selecteur affiche « ${await page.inputValue("#pays")} » et le `
        + `projet est « ${PAYS} »`);
  const contexteAffiche = await page.inputValue("#ctx");
  for (const attendu of [PAYS, REGION, DATE_REF]) {
    exige(contexteAffiche.includes(attendu),
          `le contexte affiche « ${contexteAffiche} » ne nomme pas ${attendu}`);
  }

  ici("substituer un contexte francais est impossible");
  //: ON N'EMPRUNTE PAS L'ECRAN ICI, ET C'EST TOUT L'INTERET: il ne peut PAS
  //: produire ce corps-la — le type genere ne porte ni `country`, ni `region`,
  //: ni `as_of`. On envoie donc la requete depuis la page, avec le jeton que
  //: le navigateur detient, exactement comme le ferait un client curieux.
  const jetonDeA = (premiereListe?.autorisation ?? "").replace(/^Bearer /, "");
  exige(jetonDeA.length > 20, "le jeton de A n'a pas ete observe");
  const substitution = await page.evaluate(async ([api, projet, jwt, pays]) => {
    const r = await fetch(
      `${api}/v1/projects/${projet}/calculations/ec2/beam-flexure`,
      { method: "POST",
        headers: { "Content-Type": "application/json",
                   Authorization: `Bearer ${jwt}` },
        body: JSON.stringify({
          element: "P-INTRUS", strict_ndp: false, country: pays,
          region: "Ile-de-France", as_of: "2030-01-01",
          section: { b: { value: 300, unit: "mm" },
                     h: { value: 500, unit: "mm" },
                     d: { value: 450, unit: "mm" } },
          materials: { concrete_grade: "C30/37", steel_grade: "B500B" },
          M_Ed: { value: 180, unit: "kN*m" } }) });
    return { statut: r.status, corps: await r.text() };
  }, [API, projetId, jetonDeA, PAYS_INTRUS]);
  exige(substitution.statut === 422,
        `un corps annoncant « ${PAYS_INTRUS} » et « 2030-01-01 » sur un projet `
        + `« ${PAYS} / ${DATE_REF} » obtient ${substitution.statut}: le `
        + "referentiel du calcul ne vient pas du projet.");
  exige(/country|region|as_of|project_id/.test(substitution.corps),
        "le refus ne nomme pas le champ en cause");

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
  // 5 bis — LA NOTE SE TELECHARGE, ET DIT LA VERITE
  // =======================================================================
  ici("telechargement de la note");
  //: PAR LE BOUTON, PAS PAR UNE REQUETE FABRIQUEE. Ce qu'on eprouve est ce
  //: que l'ingenieur fait: cliquer. Un `fetch` monte a la main prouverait que
  //: la route repond, pas que l'ecran sait s'en servir — et c'est justement
  //: la ou le lot precedent avait un trou.
  const attenteFichier = page.waitForEvent("download", { timeout: 30000 });
  await page.click("text=Télécharger la note HTML");
  const fichier = await attenteFichier;
  const nomPropose = fichier.suggestedFilename();
  exige(nomPropose.endsWith(".html"),
        `le fichier propose s'appelle « ${nomPropose} »`);
  exige(nomPropose.includes(calculId.slice(0, 8)),
        `le nom « ${nomPropose} » ne porte pas l'identifiant du calcul: deux `
        + "notes du meme projet s'ecraseraient dans le dossier de l'ingenieur");

  const chemin = await fichier.path();
  const note = chemin ? await readFile(chemin, "utf8") : "";
  exige(note.length > 500, "la note telechargee est vide ou tronquee");

  ici("la note porte le contexte, le moteur et les memes resultats");
  //: LE CONTEXTE DU PROJET, PAS CELUI DU JOUR.
  for (const attendu of [PAYS, REGION, DATE_REF, "FICTIF-NAV-01",
                         "FICTIF Bureau A"]) {
    exige(note.includes(attendu),
          `la note ne porte pas « ${attendu} »`);
  }
  //: LE MOTEUR, EXACTEMENT. « 0.3.0 » ne designe aucun code: plusieurs
  //: commits la partagent. Le SHA, lui, en designe un.
  exige(note.includes(enregistre.corps.engine_version),
        "la note ne nomme pas la version du moteur");
  exige(!!enregistre.corps.engine_build_sha
        && note.includes(enregistre.corps.engine_build_sha),
        `la note ne porte pas le SHA du moteur `
        + `(« ${enregistre.corps.engine_build_sha} »)`);
  exige(note.includes(enregistre.corps.inputs_hash),
        "la note ne porte pas l'empreinte des entrees");
  exige(note.includes(enregistre.corps.execution_identity),
        "la note ne porte pas l'identite d'execution");

  //: LES MEMES RESULTATS. On compare le taux de travail maximal ENREGISTRE a
  //: ce que la note imprime: un ecart signifierait qu'un calcul a eu lieu
  //: quelque part dans le chemin d'affichage.
  const maxi = enregistre.corps.result?.verification?.max_utilisation;
  const attenduTaux = (Number(maxi) * 100).toFixed(1).replace(".", ",");
  exige(note.includes(`${attenduTaux}&nbsp;%`),
        `le taux maximal enregistre (${attenduTaux} %) n'est pas imprime tel `
        + "quel dans la note");

  //: LES DEUX MENTIONS, ET AUCUNE PROMESSE DE FINALITE.
  exige(note.includes("PROJET — NON SIGNABLE"),
        "le calcul est exploratoire et la note ne le dit pas");
  exige(note.includes("livrable final"),
        "la note ne dit pas qu'elle n'est pas un livrable final");
  exige(!/<script/i.test(note), "la note contient un script");
  exige(!/(src|href)\s*=\s*["']?\s*(https?:)?\/\//i.test(note),
        "la note reference une ressource externe");

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

  ici("isolation: B tente de rouvrir ET de telecharger");
  //: LE JETON DE B EST CELUI QUE LE NAVIGATEUR VIENT D'ENVOYER. On le
  //: recupere sur sa requete de liste plutot que d'en fabriquer un: c'est la
  //: seule facon d'eprouver le refus AVEC UNE IDENTITE VALIDE — un appel sans
  //: jeton rendrait 401 et ne dirait rien du cloisonnement.
  const jetonDeB = (requeteDeB?.autorisation ?? "").replace(/^Bearer /, "");
  exige(jetonDeB.length > 20, "le jeton de B n'a pas ete observe");

  for (const [quoi, chemin] of [
    ["reouverture", `/v1/projects/${projetId}/calculations/${calculId}`],
    ["note", `/v1/projects/${projetId}/calculations/${calculId}/note.html`],
  ]) {
    const refus = await page.evaluate(async ([api, ou, jwt]) => {
      const r = await fetch(`${api}${ou}`,
                            { headers: { Authorization: `Bearer ${jwt}` } });
      return { statut: r.status, corps: (await r.text()).slice(0, 2000) };
    }, [API, chemin, jetonDeB]);
    exige(refus.statut === 422,
          `B obtient ${refus.statut} sur la ${quoi} d'une autre organisation`);
    //: LE REFUS NE DIT PAS CE QU'IL CACHE. Ni le nom du projet, ni son
    //: organisation, ni la moindre empreinte: un message trop precis est un
    //: oracle.
    for (const secret of ["FICTIF — Halle navigateur", "FICTIF Bureau A",
                          enregistre.corps.inputs_hash]) {
      exige(!refus.corps.includes(secret),
            `le refus de la ${quoi} laisse filtrer « ${secret} »`);
    }
  }

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
  "ok: A cree un projet BE/Wallonie/2024-03-01, le referentiel est verrouille " +
  "a l'ecran, une substitution francaise est refusee en 422; le calcul est " +
  "enregistre, le rechargement complet retrouve projet et historique, la " +
  "reouverture rend les memes entrees et resultats; la note se telecharge par " +
  "le bouton et porte le contexte du projet, le SHA exact du moteur, les deux " +
  "empreintes et le meme taux de travail; B n'obtient ni reouverture ni note, " +
  "avec son propre jeton, et le refus ne laisse rien filtrer; aucun jeton " +
  "persiste.",
);
