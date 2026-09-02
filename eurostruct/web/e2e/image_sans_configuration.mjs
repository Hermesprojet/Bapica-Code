/**
 * AUCUNE URL, AUCUNE CLÉ NE DOIT ÊTRE FIGÉE DANS L'IMAGE DE L'INTERFACE.
 *
 * POURQUOI C'EST FACILE À VIOLER SANS S'EN APERCEVOIR
 * ----------------------------------------------------
 * Next **inline les variables `NEXT_PUBLIC_*` dans le bundle au moment du
 * build**. Une image construite avec `NEXT_PUBLIC_SUPABASE_ANON_KEY=…` porte
 * cette clé dans son JavaScript, définitivement — y compris après qu'on a
 * « changé la variable d'environnement », puisque la valeur n'est plus une
 * variable mais une chaîne littérale du code livré.
 *
 * La conséquence n'est pas seulement une fuite : la même image ne peut plus
 * servir deux environnements. Chaque changement d'adresse devient une
 * reconstruction, et la promesse « on déploie l'artefact qu'on a testé »
 * tombe.
 *
 * CE QUE CE CONTRÔLE FAIT
 * ------------------------
 * 1. il vérifie que ni le `Dockerfile` de l'interface ni la composition ne
 *    nomment de `NEXT_PUBLIC_*` — c'est ce qui garde l'image propre ;
 * 2. il vérifie qu'aucune valeur littérale ne traîne dans la composition :
 *    tout doit passer par `${…}` ;
 * 3. il **construit réellement** l'interface avec des variables de runtime
 *    empoisonnées, et cherche le poison dans le bundle produit. Les variables
 *    de runtime — sans préfixe `NEXT_PUBLIC_` — ne doivent laisser aucune
 *    trace.
 *
 * POURQUOI LE POINT 3 EST DÉCISIF. Les points 1 et 2 lisent des fichiers : ils
 * tombent si quelqu'un ajoute un `ARG`. Le point 3 regarde ce que Next a
 * réellement produit ; il tomberait aussi si `lib/configuration.ts` revenait à
 * lire `process.env` au niveau du module. On le vérifie en le falsifiant :
 * relancé avec `--falsifier`, il pose la variante `NEXT_PUBLIC_*` et le poison
 * DOIT alors apparaître — sans quoi le contrôle ne prouverait rien.
 */
import { execFileSync } from "node:child_process";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ICI = dirname(fileURLToPath(import.meta.url));
const WEB = resolve(ICI, "..");
const RACINE = resolve(WEB, "..");

const FALSIFIER = process.argv.includes("--falsifier");
const POISON_CLE = "FICTIF-POISON-ANON-KEY-ne-doit-pas-etre-dans-le-bundle";
const POISON_URL = "https://fictif-poison.invalid/emetteur";

const echecs = [];
const exige = (ok, message) => {
  if (!ok) echecs.push(message);
};

// --- 1. le Dockerfile et la composition ne nomment aucun NEXT_PUBLIC_* ------
//
// ON NE REGARDE QUE LES DIRECTIVES, PAS LA PROSE. Les deux fichiers
// EXPLIQUENT longuement pourquoi ces variables n'y sont pas — et une premiere
// redaction de ce controle lisait le fichier entier, donc ses propres
// commentaires, et refusait le contenu qu'elle exigeait. Un controle qui
// interdit d'ecrire pourquoi la regle existe pousse a supprimer l'explication.
const sansCommentaires = (texte) =>
  texte
    .split("\n")
    .filter((l) => !/^\s*#/.test(l))
    .join("\n");

const dockerfile = readFileSync(join(WEB, "Dockerfile"), "utf8");
exige(!sansCommentaires(dockerfile).includes("NEXT_PUBLIC_"),
      "web/Dockerfile nomme une variable NEXT_PUBLIC_*: elle serait inlinee " +
      "dans le bundle au build, donc figee dans l'image");

const compose = readFileSync(join(RACINE, "compose.yaml"), "utf8");
exige(!sansCommentaires(compose).includes("NEXT_PUBLIC_"),
      "compose.yaml nomme une variable NEXT_PUBLIC_*");

// --- 2. la composition ne porte aucune valeur litterale --------------------
//
// On lit les lignes `CLE: valeur` du bloc `environment:` et on exige que la
// valeur soit une reference `${...}` — jamais une chaine ecrite en dur.
for (const ligne of compose.split("\n")) {
  const m = /^\s{6}([A-Z_][A-Z0-9_]*):\s*(.+)$/.exec(ligne);
  if (!m) continue;
  const [, cle, valeur] = m;
  const brut = valeur.trim();
  if (brut === ">-" || brut === "|" || brut === "") continue;   // scalaire plie
  exige(brut.includes("${"),
        `compose.yaml: ${cle} porte une valeur litterale (${brut}). ` +
        "Tout ce qui depend de l'environnement passe par ${...}, et les " +
        "secrets ne sont jamais dans un fichier versionne.");
}

// --- 3. le build ne bake pas les variables de RUNTIME ----------------------
const env = { ...process.env, NEXT_TELEMETRY_DISABLED: "1", CI: "1" };
// Les variables SANS prefixe: celles que le layout lit a chaque requete.
env.EUROSTRUCT_SUPABASE_ANON_KEY = POISON_CLE;
env.EUROSTRUCT_SUPABASE_URL = POISON_URL;
env.EUROSTRUCT_API_URL = POISON_URL;
// On retire toute variante NEXT_PUBLIC_ heritee de l'environnement appelant.
for (const k of Object.keys(env)) {
  if (k.startsWith("NEXT_PUBLIC_")) delete env[k];
}
if (FALSIFIER) {
  // LA FALSIFICATION: on pose la variante prefixee. Next DOIT alors l'inliner,
  // et le controle DOIT tomber. S'il ne tombe pas, il ne prouve rien.
  env.NEXT_PUBLIC_SUPABASE_ANON_KEY = POISON_CLE;
}

try {
  execFileSync("npm", ["run", "build"], {
    cwd: WEB, env, stdio: "pipe", timeout: 600_000,
  });
} catch (cause) {
  console.log("ROUGE — le build de l'interface a echoue");
  console.log(String(cause.stdout || cause).slice(-2000));
  process.exit(1);
}

/** Tous les fichiers produits, en profondeur. */
function* fichiers(racine) {
  for (const entree of readdirSync(racine)) {
    const chemin = join(racine, entree);
    if (statSync(chemin).isDirectory()) yield* fichiers(chemin);
    else yield chemin;
  }
}

let porteurs = [];
for (const chemin of fichiers(join(WEB, ".next"))) {
  if (!/\.(js|mjs|cjs|json|html|txt|map)$/.test(chemin)) continue;
  const contenu = readFileSync(chemin, "utf8");
  if (contenu.includes(POISON_CLE) || contenu.includes(POISON_URL)) {
    porteurs.push(chemin.slice(WEB.length + 1));
  }
}

if (FALSIFIER) {
  // Ici on ATTEND la fuite: c'est ce qui montre que le controle regarde bien
  // ce qu'il pretend regarder.
  if (porteurs.length === 0) {
    console.log(
      "ROUGE — falsification: une variable NEXT_PUBLIC_* posee au build n'a " +
      "PAS ete retrouvee dans le bundle. Le controle ne prouve donc rien.",
    );
    process.exit(1);
  }
  console.log(
    `ok (falsification): le poison apparait dans ${porteurs.length} fichier(s) ` +
    "quand il est pose en NEXT_PUBLIC_* — le controle est decisif.",
  );
  process.exit(0);
}

exige(porteurs.length === 0,
      `la configuration de runtime est figee dans le bundle: ${porteurs.slice(0, 5).join(", ")}`);

if (echecs.length) {
  console.log("ROUGE — configuration figee dans l'image de l'interface");
  echecs.forEach((e) => console.log("   - " + e));
  process.exit(1);
}
console.log(
  "ok: ni le Dockerfile ni la composition ne nomment de NEXT_PUBLIC_*, la " +
  "composition ne porte aucune valeur litterale, et une configuration de " +
  "runtime ne laisse aucune trace dans le bundle construit.",
);
