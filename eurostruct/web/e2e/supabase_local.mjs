/**
 * UN GOTRUE LOCAL, DÉTERMINISTE, SANS AUCUN SECRET RÉEL.
 *
 * POURQUOI CE DÉCOR EXISTE
 * -------------------------
 * Le parcours d'autorité ne se prouve qu'en traversant un navigateur : c'est
 * l'écran qui décide quand joindre un `Authorization`, quand le retirer, et
 * quand refuser de partir. `TestClient` ne peut rien en dire — il n'exécute
 * pas la page.
 *
 * Mais un navigateur a besoin d'un émetteur de jetons joignable. Celui-ci
 * parle le sous-ensemble de GoTrue que `lib/session.ts` appelle réellement :
 *
 *     POST /auth/v1/token?grant_type=password
 *     POST /auth/v1/token?grant_type=refresh_token
 *     GET  /jwks
 *
 * CE QU'IL N'EST PAS
 * -------------------
 * Ce n'est pas Supabase. Les clés RSA sont générées au démarrage et meurent
 * avec le processus ; aucun compte, aucun mot de passe et aucune instance
 * réelle n'apparaissent. `SUPABASE_UNVERIFIED` reste donc vrai : ce décor
 * prouve le comportement de NOTRE code face à un émetteur conforme, jamais la
 * compatibilité avec l'émetteur de Supabase.
 *
 * LA VÉRIFICATION, ELLE, EST CELLE DE PRODUCTION. L'API en face reçoit le
 * `jwks_url` de ce serveur et vérifie les signatures avec
 * `AuthentificateurSupabase`. Un jeton mal signé est refusé ici comme il le
 * serait ailleurs.
 *
 * LES COMPTES SONT DES SUJETS, PAS DES IDENTITÉS. Ils viennent de
 * `EUROSTRUCT_E2E_COMPTES`, que le harnais remplit avec les UUID qu'il a
 * lui-même inscrits dans `auth.users` de la base jetable.
 */
import { generateKeyPairSync, randomUUID, sign } from "node:crypto";
import { createServer } from "node:http";

const PORT = Number(process.env.EUROSTRUCT_SUPABASE_LOCAL_PORT || 54321);
const ISSUER = process.env.EUROSTRUCT_SUPABASE_LOCAL_ISSUER
  || `http://127.0.0.1:${PORT}/auth/v1`;
const AUDIENCE = "authenticated";
const KID = "eurostruct-e2e-1";

/**
 * Les comptes du décor :
 * `courriel:mdp:uuid[:duree_s[:rafraichissable[:retard_mdp_ms]]]`.
 *
 * `duree_s` sert aux cas d'expiration : un jeton qui dure quelques secondes
 * permet d'observer ce que l'écran fait quand il périme, sans attendre une
 * heure ni truquer l'horloge du navigateur.
 *
 * `rafraichissable` (`oui` par défaut) sépare les DEUX comportements attendus
 * à l'expiration, qui sont différents et doivent être éprouvés séparément :
 *
 *   * `oui` -> l'écran renouvelle **en mémoire** et l'utilisateur ne voit
 *     rien ; la requête suivante porte le jeton NEUF ;
 *   * `non` -> l'écran **ferme** la session et demande une reconnexion ; plus
 *     aucune requête ne part.
 *
 * Un émetteur qui délivrerait toujours un jeton de renouvellement rendrait le
 * second chemin inobservable — et c'est le chemin où le jeton périmé risque de
 * partir quand même.
 */
const COMPTES = new Map();
for (const brut of (process.env.EUROSTRUCT_E2E_COMPTES || "").split(",")) {
  const [courriel, motDePasse, sub, duree, rafraichissable, retardMs] =
    brut.split(":");
  if (!courriel || !motDePasse || !sub) continue;
  COMPTES.set(courriel, {
    motDePasse,
    sub,
    duree: Number(duree || 3600),
    rafraichissable: (rafraichissable ?? "oui") !== "non",
    // 6e champ: le retard de l'echange MOT DE PASSE, en millisecondes.
    retardMs: Number(retardMs || 0),
  });
}
if (COMPTES.size === 0) {
  console.error(
    "supabase_local: aucun compte. EUROSTRUCT_E2E_COMPTES attend " +
      "« courriel:motdepasse:uuid[:duree_s[:rafraichissable]],… ». Un " +
      "emetteur sans compte ne prouve rien.",
  );
  process.exit(2);
}

// SANS OPTION D'ENCODAGE, `generateKeyPairSync` rend deja deux `KeyObject`.
// Les repasser par `createPublicKey` leve — la cle publique n'est pas un
// materiau a re-importer, elle est deja la.
const { publicKey, privateKey } = generateKeyPairSync("rsa", {
  modulusLength: 2048,
});
const jwk = { ...publicKey.export({ format: "jwk" }),
              kid: KID, alg: "RS256", use: "sig" };

const b64 = (o) =>
  Buffer.from(typeof o === "string" ? o : JSON.stringify(o))
    .toString("base64url");

function jetonPour(sub, dureeS) {
  const maintenant = Math.floor(Date.now() / 1000);
  const entete = b64({ alg: "RS256", typ: "JWT", kid: KID });
  const charge = b64({
    iss: ISSUER, aud: AUDIENCE, sub, role: "authenticated",
    iat: maintenant - 5, nbf: maintenant - 5, exp: maintenant + dureeS,
  });
  const signature = sign("RSA-SHA256", Buffer.from(`${entete}.${charge}`),
                         privateKey).toString("base64url");
  return `${entete}.${charge}.${signature}`;
}

/** Les jetons de renouvellement vivent ici, jamais dans le jeton lui-même. */
const RAFRAICHISSEMENTS = new Map();

/**
 * Délai artificiel sur le SEUL renouvellement, en millisecondes.
 *
 * POURQUOI UN DELAI DELIBERE, ET POURQUOI IL EST INDISPENSABLE. Le
 * renouvellement est un aller-retour réseau, et la fenêtre pendant laquelle il
 * est *en vol* est celle où une déconnexion peut se faire annuler par la
 * réponse qui revient. Sur cette boucle locale, l'échange dure une
 * milliseconde : le cas qui vise cette fenêtre la manquait systématiquement et
 * passait au vert **avec le défaut présent** — vérifié en retirant la garde,
 * qui n'a fait tomber aucun cas.
 *
 * Un émetteur réel met des dizaines de millisecondes à répondre, et bien plus
 * sur un réseau mobile. Le délai ne fabrique donc pas une situation
 * artificielle : il rend observable celle de tout le monde.
 */
const DELAI_REFRESH_MS = Number(process.env.EUROSTRUCT_E2E_DELAI_REFRESH_MS || 0);

/**
 * Le même retard, mais sur l'échange MOT DE PASSE, et PAR COMPTE.
 *
 * IL REND OBSERVABLES DEUX COURSES QU'AUCUN CAS NE POUVAIT VISER. Une
 * connexion est un aller-retour: si elle revient APRES une déconnexion, elle
 * rouvre une session que la personne vient de fermer; si deux connexions sont
 * en vol et que la plus ancienne revient en dernier, elle ECRASE la plus
 * récente — et sur un écran d'autorité, l'identité décide qui approuve.
 *
 * PAR COMPTE, ET C'EST NECESSAIRE. Un retard global ralentirait aussi la
 * connexion RAPIDE de la course, qui n'arriverait alors plus en second: le
 * cas ne viserait plus rien. Le retard est donc le 6e champ de la
 * description d'un compte.
 */

function delivrer(compte) {
  const corps = {
    access_token: jetonPour(compte.sub, compte.duree),
    token_type: "bearer",
    expires_in: compte.duree,
  };
  if (compte.rafraichissable) {
    const rafraichissement = randomUUID();
    RAFRAICHISSEMENTS.set(rafraichissement, compte);
    corps.refresh_token = rafraichissement;
  }
  return corps;
}

const ENTETES_CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "Authorization, Content-Type, apikey",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
};

function repondre(res, code, corps) {
  const texte = JSON.stringify(corps);
  res.writeHead(code, {
    "Content-Type": "application/json",
    "Content-Length": Buffer.byteLength(texte),
    ...ENTETES_CORS,
  });
  res.end(texte);
}

const serveur = createServer((req, res) => {
  if (req.method === "OPTIONS") {
    res.writeHead(204, ENTETES_CORS);
    res.end();
    return;
  }
  const url = new URL(req.url, `http://127.0.0.1:${PORT}`);

  if (req.method === "GET" && url.pathname === "/jwks") {
    repondre(res, 200, { keys: [jwk] });
    return;
  }

  if (req.method === "POST" && url.pathname === "/auth/v1/token") {
    let brut = "";
    req.on("data", (m) => {
      brut += m;
      // Une charge utile démesurée n'est pas une tentative de connexion.
      if (brut.length > 8192) req.destroy();
    });
    req.on("end", () => {
      let corps;
      try {
        corps = JSON.parse(brut || "{}");
      } catch {
        repondre(res, 400, { error: "invalid_request" });
        return;
      }
      const type = url.searchParams.get("grant_type");

      if (type === "refresh_token") {
        const compte = RAFRAICHISSEMENTS.get(corps.refresh_token);
        if (!compte) {
          repondre(res, 400, { error: "invalid_grant" });
          return;
        }
        // UN JETON DE RENOUVELLEMENT NE SERT QU'UNE FOIS. GoTrue fait tourner
        // le sien; un décor qui l'accepterait indéfiniment laisserait passer
        // un client qui ne remplace jamais celui qu'il détient.
        RAFRAICHISSEMENTS.delete(corps.refresh_token);
        const rendu = delivrer(compte);
        if (DELAI_REFRESH_MS > 0) {
          setTimeout(() => repondre(res, 200, rendu), DELAI_REFRESH_MS);
        } else {
          repondre(res, 200, rendu);
        }
        return;
      }

      if (type !== "password") {
        repondre(res, 400, { error: "unsupported_grant_type" });
        return;
      }
      const compte = COMPTES.get(corps.email);
      if (!compte || compte.motDePasse !== corps.password) {
        // Le MÊME refus pour un compte inconnu et un mot de passe faux: la
        // distinction est un oracle d'énumération.
        repondre(res, 400, { error: "invalid_grant",
                             error_description: "Invalid login credentials" });
        return;
      }
      const rendu = delivrer(compte);
      if (compte.retardMs > 0) {
        setTimeout(() => repondre(res, 200, rendu), compte.retardMs);
      } else {
        repondre(res, 200, rendu);
      }
    });
    return;
  }

  repondre(res, 404, { error: "not_found" });
});

// L'ADRESSE D'ECOUTE EST `127.0.0.1` PAR DEFAUT, ET CE DEFAUT NE BOUGE PAS.
//
// Un emetteur de jetons, meme fictif, n'a rien a ecouter au-dela de la boucle
// locale tant que personne ne l'a demande. La composition, elle, a besoin de
// le joindre depuis un CONTENEUR: elle passe alors l'adresse de la passerelle
// du pont Docker — une interface precise, jamais `0.0.0.0`, qui exposerait
// aussi les interfaces externes de la machine.
const ECOUTE = process.env.EUROSTRUCT_SUPABASE_LOCAL_BIND || "127.0.0.1";

serveur.listen(PORT, ECOUTE, () => {
  // AUCUN JETON, AUCUNE CLÉ PRIVÉE, AUCUN MOT DE PASSE dans cette ligne: elle
  // finit dans un journal de CI.
  console.log(
    `supabase_local: ${COMPTES.size} compte(s) fictifs, ${ECOUTE}:${PORT}`);
});
