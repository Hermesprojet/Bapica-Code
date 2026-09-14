/**
 * ENTRER DANS L'APPLICATION, DEPUIS UN VRAI NAVIGATEUR.
 *
 * CE QUE CE PARCOURS ÉPROUVE, ET QUE RIEN D'AUTRE NE PEUT ÉPROUVER
 * -----------------------------------------------------------------
 * `test_entree.py` prouve que les huit primitives et les huit routes tiennent
 * sous identité vérifiée, et que PostgreSQL cloisonne. Il construit ses
 * requêtes lui-même : il ne dit rien de ce que l'ÉCRAN montre à quelqu'un qui
 * arrive, ni de ce qu'il peut faire avec sa souris, ni de ce qui reste après
 * un F5.
 *
 * Et c'est exactement là qu'était le défaut : le produit REFUSAIT
 * correctement, et n'offrait aucune porte. Un cul-de-sac ne se voit pas dans
 * une suite d'API ; il se voit sur un écran.
 *
 * LES QUATORZE FAITS
 * -------------------
 *   1. F se connecte, et son écran dit qu'il n'appartient à aucun bureau —
 *      avec exactement deux portes, pas un selecteur vide ;
 *   2. il crée son organisation depuis l'écran, et en devient `owner` ;
 *   3. le même geste répété ne fonde pas un second bureau ;
 *   4. il crée un projet — le geste même qui refusait avant ;
 *   5. il émet une invitation `engineer` ; le secret apparaît à l'écran,
 *      **une fois** ;
 *   6. la liste des invitations ne porte ni le secret ni son empreinte ;
 *   7. après un RECHARGEMENT COMPLET, le secret n'est plus nulle part ;
 *   8. I se connecte, voit les deux mêmes portes, colle le lien, et entre
 *      avec le rôle que l'invitation portait ;
 *   9. le même lien, présenté une seconde fois par X, est refusé ;
 *  10. I, `engineer`, ne voit aucun panneau d'administration — et l'écran dit
 *      pourquoi ;
 *  11. F produit un brouillon de livrable et le télécharge : le sha256 des
 *      octets **reçus par le navigateur** est celui que la base a enregistré ;
 *  12. F promeut I `validating_engineer`, et I le voit à sa reconnexion ;
 *  13. F désactive I : la ligne survit à l'écran, et I ne voit plus le
 *      bureau ;
 *  14. F n'a aucun bouton sur sa propre ligne, et la route le refuse aussi
 *      quand on la force.
 *
 * CE QUE CE PARCOURS N'ÉPROUVE PAS, ET QUI EST DIT
 * -------------------------------------------------
 * Le magasin OBJET. Ce parcours tourne sur le magasin local — le même code de
 * route, la même vérification d'empreinte — parce qu'un MinIO réel exige un
 * démon Docker que ce harnais ne suppose pas. Le protocole S3 a son propre
 * harnais, `db/test/stockage_s3.sh`, en huit étapes contre un serveur réel.
 *
 * Le calcul est EXPLORATOIRE : ouvrir le mode strict demande le quatre-yeux,
 * qui est éprouvé ailleurs. Le livrable produit porte donc « PROJET — NON
 * SIGNABLE », et c'est vrai.
 *
 * AUCUN DE CES COMPTES N'EST RÉEL. La base est détruite à la fin du harnais.
 * `SUPABASE_UNVERIFIED` reste vrai et le registre national reste à 0/29.
 *
 * ON OBSERVE CE QUI PART ET CE QUI REVIENT, pas l'état de React.
 */
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";

import { chargerChromium, cheminChromium } from "./playwright.mjs";

const WEB = process.env.EUROSTRUCT_WEB || "http://localhost:3000";
const API = process.env.EUROSTRUCT_API || "http://127.0.0.1:8000";
const TELECHARGEMENTS = process.env.EUROSTRUCT_E2E_TELECHARGEMENTS || "/tmp";

const F = { courriel: "f@fictif.invalid", mdp: "FICTIF-F" };
const I = { courriel: "i@fictif.invalid", mdp: "FICTIF-I" };
const X = { courriel: "x@fictif.invalid", mdp: "FICTIF-X" };
const ACTEUR_F = process.env.EUROSTRUCT_E2E_ACTEUR_F || "";
const ACTEUR_I = process.env.EUROSTRUCT_E2E_ACTEUR_I || "";

const NOM_BUREAU = "FICTIF Bureau de la fondatrice";
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
  await page.waitForSelector("#bureau", { timeout: 15000 });
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

/**
 * LE JETON QUE LE NAVIGATEUR VIENT D'EMPLOYER, OBSERVÉ SUR LE RÉSEAU.
 *
 * On ne le lit ni dans `localStorage`, ni dans une variable globale : on le
 * prend là où il passe déjà, dans l'en-tête d'une requête que l'écran a
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
 * d'atteindre une route qu'aucun bouton n'expose — parce que le produit refuse
 * délibérément de l'exposer. Un attaquant qui atteindrait l'API ne passerait
 * pas par les boutons non plus.
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

let organisationId = "";
let projetId = "";
let secret = "";

try {
  // =======================================================================
  // 1 — CE QUE VOIT UN COMPTE TOUT NEUF
  // =======================================================================
  ici("ouverture de la page");
  await page.goto(WEB, { waitUntil: "domcontentloaded" });

  ici("connexion de F");
  const bureaux = await corpsDe("/v1/organizations", "GET", () => connecter(F));
  exige(bureaux.statut === 200,
        `la liste des organisations a rendu ${bureaux.statut}`);
  exige(Array.isArray(bureaux.corps) && bureaux.corps.length === 0,
        "F appartient deja a un bureau: le decor n'est pas vierge");

  //: L'ECRAN NE MONTRE PAS UN SELECTEUR VIDE, IL MONTRE DEUX PORTES.
  await page.waitForSelector("#aucun-bureau", { timeout: 15000 });
  exige(await page.locator("#creer-bureau").count() === 1,
        "aucun bouton « Creer mon organisation »");
  exige(await page.locator("#rejoindre-bureau").count() === 1,
        "aucun bouton « Rejoindre avec une invitation »");
  const explication = await page.locator("#aucun-bureau p").first().innerText();
  exige(/aucun bureau/i.test(explication),
        `l'ecran n'explique pas ce qui manque: « ${explication.slice(0, 120)} »`);

  // =======================================================================
  // 2 — F FONDE SON BUREAU, DEPUIS L'ÉCRAN
  // =======================================================================
  ici("fondation du bureau");
  await page.click("#creer-bureau");
  await page.fill("#nom-bureau", NOM_BUREAU);
  await page.fill("#mon-nom", "FICTIF Ing. F");
  await page.fill("#mon-ordre", "FICTIF-ORDRE-NAV-1");
  const fonde = await corpsDe("/v1/organizations", "POST",
                              () => page.click("#valider-fondation"));
  exige(fonde.statut === 201, `la fondation a rendu ${fonde.statut}`);
  organisationId = fonde.corps?.organization_id ?? "";
  exige(/^[0-9a-f-]{36}$/i.test(organisationId),
        `la fondation n'a rendu aucun identifiant (« ${organisationId} »)`);
  exige(fonde.corps?.member_role === "owner",
        `le fondateur a le role « ${fonde.corps?.member_role} »`);

  //: LE PANNEAU D'EQUIPE APPARAIT, PARCE QUE F EST `owner`.
  await page.waitForSelector("#equipe", { timeout: 15000 });
  await page.waitForSelector("#table-membres", { timeout: 15000 });

  // =======================================================================
  // 3 — LE MÊME GESTE, DEUX FOIS, NE FONDE PAS DEUX BUREAUX
  // =======================================================================
  ici("second appel de fondation, meme nom");
  const encore = await depuisLaPage("/v1/organizations", "POST",
                                    { name: NOM_BUREAU, country: "BE",
                                      display_name: null,
                                      professional_id: null });
  exige(encore.statut === 201,
        `le second appel a rendu ${encore.statut} au lieu de 201`);
  exige(encore.corps?.organization_id === organisationId,
        "le second appel a fonde un SECOND bureau: son fondateur se "
        + "retrouverait devant deux entrees dont il ne saurait pas laquelle "
        + "est la sienne");

  // =======================================================================
  // 4 — LE PROJET, QUI REFUSAIT AVANT
  // =======================================================================
  ici("creation du projet");
  await page.click("text=Nouveau projet");
  await page.fill("#p-nom", "FICTIF — Premier projet du bureau");
  await page.fill("#p-date", DATE_REF);
  const projet = await corpsDe("/v1/projects", "POST",
                               () => page.click("text=Créer le projet"));
  exige(projet.statut === 201,
        `la creation du projet a rendu ${projet.statut}: le cul-de-sac n'est `
        + "pas ferme");
  projetId = projet.corps?.project_id ?? "";
  exige(projet.corps?.member_role === "owner",
        `le role rendu sur le projet est « ${projet.corps?.member_role} »`);

  // =======================================================================
  // 5 — L'INVITATION, ET SON SECRET MONTRÉ UNE FOIS
  // =======================================================================
  ici("emission d'une invitation");
  await page.selectOption("#role-invite", "engineer");
  await page.fill("#libelle-invite", "FICTIF pour l'invitee");
  await page.fill("#nom-invite", "FICTIF Ing. I");
  await page.fill("#ordre-invite", "FICTIF-ORDRE-NAV-2");
  const emise = await corpsDe("/invitations", "POST",
                              () => page.click("#emettre-invitation"));
  exige(emise.statut === 201, `l'emission a rendu ${emise.statut}`);
  secret = emise.corps?.token ?? "";
  exige(secret.length >= 32,
        `le secret fait ${secret.length} caracteres: trop court pour etre `
        + "imprevisible");

  await page.waitForSelector("#lien-emis", { timeout: 15000 });
  const affiche = await page.inputValue("#secret-invitation");
  exige(affiche === secret,
        "l'ecran n'affiche pas le secret que l'API vient de rendre");

  // =======================================================================
  // 6 — LA LISTE NE PORTE NI LE SECRET NI SON EMPREINTE
  // =======================================================================
  ici("la liste des invitations");
  const empreinte = createHash("sha256").update(secret).digest("hex");
  const liste = await depuisLaPage(
    `/v1/organizations/${organisationId}/invitations`);
  exige(liste.statut === 200, `la liste a rendu ${liste.statut}`);
  exige(!liste.texte.includes(secret),
        "la liste des invitations porte le SECRET");
  exige(!liste.texte.includes(empreinte),
        "la liste des invitations porte l'EMPREINTE: elle suffirait a "
        + "reconnaitre un lien intercepte ailleurs");
  await page.waitForSelector("#table-invitations", { timeout: 15000 });
  const etatAffiche = await page
    .locator("#table-invitations tbody tr td[data-etat]").first().innerText();
  exige(etatAffiche.trim() === "pending",
        `l'invitation neuve est affichee « ${etatAffiche.trim()} »`);

  // =======================================================================
  // 7 — APRÈS UN RECHARGEMENT COMPLET, LE SECRET A DISPARU
  // =======================================================================
  ici("rechargement complet");
  //: LA SESSION NE SURVIT PAS AU RECHARGEMENT, ET C'EST VOULU: le jeton n'est
  //: persiste nulle part. F se reconnecte donc — ce qui rend la mesure plus
  //: forte encore: meme apres une ouverture de session NEUVE, le secret n'est
  //: nulle part.
  await page.reload({ waitUntil: "domcontentloaded" });
  await connecter(F);
  await page.waitForSelector("#table-invitations", { timeout: 20000 });
  const pageEntiere = await page.content();
  exige(!pageEntiere.includes(secret),
        "le secret est encore dans la page apres rechargement: un lien a "
        + "usage unique ne doit pas survivre a la session qui l'a cree");
  exige(await page.locator("#lien-emis").count() === 0,
        "l'encart du lien survit au rechargement");

  //: ET IL N'EST NI DANS `localStorage`, NI DANS `sessionStorage`.
  const range = await page.evaluate(() => {
    const tout = [];
    for (const magasin of [localStorage, sessionStorage]) {
      for (let i = 0; i < magasin.length; i++) {
        tout.push(magasin.getItem(magasin.key(i)) ?? "");
      }
    }
    return tout.join(" ");
  });
  exige(!range.includes(secret),
        "le secret est range dans le navigateur: il survivrait a la session");

  // =======================================================================
  // 8 — I REJOINT LE BUREAU AVEC LE LIEN
  // =======================================================================
  ici("connexion de I");
  await deconnecter();
  await connecter(I);
  await page.waitForSelector("#aucun-bureau", { timeout: 15000 });

  ici("adhesion par le lien");
  await page.click("#rejoindre-bureau");
  await page.fill("#lien-invitation", secret);
  const entree = await corpsDe("/v1/invitations/accept", "POST",
                               () => page.click("#valider-adhesion"));
  exige(entree.statut === 200, `l'adhesion a rendu ${entree.statut}`);
  exige(entree.corps?.organization_id === organisationId,
        "l'adhesion n'a pas rendu le bureau attendu");
  exige(entree.corps?.member_role === "engineer",
        `le role obtenu est « ${entree.corps?.member_role} » au lieu de celui `
        + "que l'invitation portait");

  // =======================================================================
  // 9 — LE MÊME LIEN, UNE SECONDE FOIS, EST REFUSÉ
  // =======================================================================
  ici("le lien deja consomme");
  await deconnecter();
  await connecter(X);
  const rejoue = await depuisLaPage("/v1/invitations/accept", "POST",
                                    { token: secret });
  exige(rejoue.statut === 422,
        `le lien deja consomme a rendu ${rejoue.statut} au lieu d'un refus`);
  exige(/inconnue, expiree, revoquee ou deja utilisee/.test(rejoue.texte),
        `le refus distingue les cas: « ${rejoue.texte.slice(0, 160)} »`);
  const bureauxX = await depuisLaPage("/v1/organizations");
  exige(Array.isArray(bureauxX.corps) && bureauxX.corps.length === 0,
        "X est entre dans un bureau avec un lien deja consomme");

  // =======================================================================
  // 10 — I N'ADMINISTRE PAS, ET L'ÉCRAN LE DIT
  // =======================================================================
  ici("l'ecran de I");
  await deconnecter();
  await connecter(I);
  await page.waitForSelector("#pourquoi-pas-admin", { timeout: 15000 });
  const pourquoi = await page.locator("#pourquoi-pas-admin").innerText();
  exige(/engineer/.test(pourquoi) && /administre pas/.test(pourquoi),
        `l'explication ne nomme ni le role ni ce qui manque: « ${pourquoi}»`);
  exige(await page.locator("#table-membres").count() === 0,
        "l'annuaire est affiche a quelqu'un qui n'administre pas");
  exige(await page.locator("#formulaire-invitation").count() === 0,
        "le formulaire d'invitation est offert a quelqu'un qui n'administre pas");

  //: ET LA ROUTE REFUSE AUSSI, hors de tout bouton.
  const annuaireForce = await depuisLaPage(
    `/v1/organizations/${organisationId}/members`);
  exige(annuaireForce.statut === 422,
        `l'annuaire force a rendu ${annuaireForce.statut}`);
  exige(/n'administre pas/.test(annuaireForce.texte),
        `le refus ne dit pas pourquoi: « ${annuaireForce.texte.slice(0, 160)} »`);

  // =======================================================================
  // 11 — LE LIVRABLE, TÉLÉCHARGÉ DEPUIS L'ÉCRAN
  // =======================================================================
  ici("calcul et brouillon");
  await deconnecter();
  await connecter(F);
  await page.selectOption("#projet", projetId);
  //: LE CALCUL EST EXPLORATOIRE, ET ON LE DIT A L'ECRAN. Le mode strict est
  //: coche par defaut — c'est le bon defaut — et il refuse tant qu'aucun
  //: parametre national n'est confirme par le quatre-yeux. Ouvrir cette porte
  //: est l'objet de `parcours_livrable.sh`, pas de celui-ci: ici, ce qu'on
  //: eprouve est qu'un bureau tout juste fonde peut REELLEMENT produire et
  //: telecharger un document.
  await page.uncheck("#strict");
  const calcul = await corpsDe(
    "/calculations/ec2/beam-flexure", "POST",
    () => page.click("text=Calculer et enregistrer sur le projet"));
  exige(calcul.statut === 201, `le calcul a rendu ${calcul.statut}`);
  const calculId = calcul.corps?.calculation_id ?? "";

  const bouton = page.locator(
    `tr[data-calcul="${calculId}"] >> text=Produire un brouillon`);
  await bouton.waitFor({ timeout: 20000 });
  const brouillon = await corpsDe("/deliverables", "POST", () => bouton.click());
  exige(brouillon.statut === 201, `la production a rendu ${brouillon.statut}`);
  const livrableId = brouillon.corps?.deliverable_id ?? "";
  const empreinteEnregistree = brouillon.corps?.sha256 ?? "";
  //: LE CALCUL EST EXPLORATOIRE, ET LE DOCUMENT LE DIT. On ne le cache pas:
  //: un livrable tire d'un calcul non strict n'est PAS signable.
  exige(typeof brouillon.corps?.watermark === "string"
        && brouillon.corps.watermark.length > 0,
        "un calcul exploratoire a produit un document SANS filigrane");

  ici("telechargement du livrable");
  const recu = await empreinteDuTelechargement(
    () => page.click(`tr[data-livrable="${livrableId}"] >> text=Télécharger`));
  exige(recu.sha256 === empreinteEnregistree,
        `le sha256 des octets recus (${recu.sha256.slice(0, 16)}…) differe de `
        + `celui enregistre (${empreinteEnregistree.slice(0, 16)}…)`);

  // =======================================================================
  // 12 — F PROMEUT I, ET I LE VOIT
  // =======================================================================
  ici("promotion de I");
  const promotion = await corpsDe(
    `/members/${ACTEUR_I}`, "PATCH",
    () => page.selectOption(
      `tr[data-membre="${ACTEUR_I}"] select`, "validating_engineer"));
  exige(promotion.statut === 200, `la promotion a rendu ${promotion.statut}`);
  exige(promotion.corps?.role === "validating_engineer",
        `le role apres promotion est « ${promotion.corps?.role} »`);

  ici("I constate son nouveau role");
  await deconnecter();
  const vuParI = await corpsDe("/v1/organizations", "GET", () => connecter(I));
  const sien = (vuParI.corps ?? []).find(
    (o) => o.organization_id === organisationId);
  exige(sien?.member_role === "validating_engineer",
        `I voit le role « ${sien?.member_role} » dans son bureau`);

  // =======================================================================
  // 13 — F DÉSACTIVE I: LA LIGNE SURVIT, L'ACCÈS NON
  // =======================================================================
  ici("desactivation de I");
  await deconnecter();
  await connecter(F);
  await page.waitForSelector("#table-membres", { timeout: 15000 });
  const desactivation = await corpsDe(
    `/members/${ACTEUR_I}`, "PATCH",
    () => page.click(
      `tr[data-membre="${ACTEUR_I}"] >> [data-action="desactiver"]`));
  exige(desactivation.statut === 200,
        `la desactivation a rendu ${desactivation.statut}`);
  exige(desactivation.corps?.is_active === false,
        "la desactivation n'a pas pris effet");

  //: LA LIGNE EST TOUJOURS A L'ECRAN, MARQUEE REVOQUEE. Une note de dix ans
  //: doit rester lisible et nommer son signataire.
  await page.waitForSelector(
    `tr[data-membre="${ACTEUR_I}"] td[data-actif="non"]`, { timeout: 15000 });

  ici("I ne voit plus le bureau");
  await deconnecter();
  const apresRevocation = await corpsDe("/v1/organizations", "GET",
                                        () => connecter(I));
  exige((apresRevocation.corps ?? []).every(
          (o) => o.organization_id !== organisationId),
        "un acces revoque voit encore son ancien bureau");
  await page.waitForSelector("#aucun-bureau", { timeout: 15000 });

  // =======================================================================
  // 14 — F NE SE MODIFIE PAS LUI-MÊME
  // =======================================================================
  ici("F face a sa propre ligne");
  await deconnecter();
  await connecter(F);
  await page.waitForSelector("#table-membres", { timeout: 15000 });
  const maLigne = page.locator(`tr[data-membre="${ACTEUR_F}"]`);
  exige(await maLigne.locator("select").count() === 0,
        "l'ecran offre un selecteur de role sur sa PROPRE ligne");
  exige(await maLigne.locator("button").count() === 0,
        "l'ecran offre un bouton sur sa PROPRE ligne");
  const mention = await maLigne.innerText();
  exige(/propre adhesion|propre adhésion/i.test(mention),
        `la ligne de l'appelant ne dit pas pourquoi: « ${mention} »`);

  //: ET LA ROUTE REFUSE, hors de tout bouton. C'est la frontiere; l'ecran ne
  //: fait que MONTRER ce qu'elle decide.
  const auto = await depuisLaPage(
    `/v1/organizations/${organisationId}/members/${ACTEUR_F}`, "PATCH",
    { role: "engineer", is_active: null, display_name: null,
      professional_id: null, update_names: false });
  exige(auto.statut === 422,
        `la modification de sa propre adhesion a rendu ${auto.statut}`);
  exige(/propre adhesion/.test(auto.texte),
        `le refus ne dit pas pourquoi: « ${auto.texte.slice(0, 160)} »`);

  //: ET LE DERNIER PROPRIETAIRE ACTIF NE DISPARAIT PAS NON PLUS.
  const seul = await depuisLaPage(
    `/v1/organizations/${organisationId}/members/${ACTEUR_F}`, "PATCH",
    { role: null, is_active: false, display_name: null,
      professional_id: null, update_names: false });
  exige(seul.statut === 422,
        `la desactivation du dernier proprietaire a rendu ${seul.statut}`);
} catch (cause) {
  echecs.push(`exception a l'etape « ${etapeCourante} »: ${cause}`);
  try {
    for (const sel of ["#aucun-bureau", "#pourquoi-pas-admin", "[role=alert]"]) {
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
  console.log("ROUGE — parcours d'entree depuis le navigateur");
  echecs.forEach((e) => console.log("   - " + e));
  if (criees.length) {
    console.log("   ce que la page a signale:");
    criees.slice(0, 12).forEach((c) => console.log("     · " + c));
  }
  process.exit(1);
}
console.log(
  "ok: F arrive devant deux portes et non un selecteur vide, fonde son bureau "
  + "depuis l'ecran et en devient owner, un second appel du meme nom ne fonde "
  + "pas de jumeau, le projet qui refusait avant aboutit; l'invitation montre "
  + "son secret UNE fois — ni la liste, ni la page rechargee, ni le stockage "
  + "du navigateur ne le portent; I entre avec le lien et le role qu'il "
  + "portait, X est refuse par le meme lien deja consomme, I n'administre pas "
  + "et l'ecran dit pourquoi comme la route; le brouillon telecharge porte "
  + "l'empreinte enregistree; F promeut puis desactive I — la ligne survit, "
  + "l'acces non — et ne peut ni se modifier lui-meme, ni faire disparaitre le "
  + "dernier proprietaire actif.",
);
