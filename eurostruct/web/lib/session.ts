/**
 * La session Supabase, côté navigateur.
 *
 * CE QUE CE MODULE EST, ET CE QU'IL N'EST PAS
 * --------------------------------------------
 * Il obtient un jeton et le transporte. Il ne le **vérifie** pas : la
 * vérification est côté API, dans `AuthentificateurSupabase`, parce qu'une
 * vérification faite dans le navigateur ne prouve rien — le navigateur est
 * l'endroit que l'attaquant contrôle.
 *
 * Ce que le jeton porte n'est donc jamais lu ici pour décider quoi que ce
 * soit. On l'envoie, et c'est l'API qui dit oui ou non.
 *
 * PAS DE SDK, ET C'EST DELIBERE
 * ------------------------------
 * `@supabase/supabase-js` apporte un client complet — base, stockage, temps
 * réel — dont cette tranche n'utilise rien. On appelle donc directement le
 * point d'entrée `token` de GoTrue, qui est une API HTTP stable et publique.
 * Moins de surface, et rien à tenir à jour.
 *
 * LE JETON NE VA PAS DANS `localStorage`
 * ---------------------------------------
 * Il vit en mémoire, dans l'onglet. Un jeton dans `localStorage` survit à la
 * fermeture, se lit depuis n'importe quel script de la page, et se retrouve
 * dans les copies d'écran de débogage. La contrepartie — se reconnecter en
 * rouvrant l'onglet — est acceptable pour cette tranche.
 */

const URL_SUPABASE = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const CLE_ANON = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

/** La configuration est-elle présente ? Sinon l'écran n'affiche pas la connexion. */
export function authDisponible(): boolean {
  return Boolean(URL_SUPABASE && CLE_ANON);
}

export type Session = { jeton: string; expire_a: number };

export type IssueConnexion =
  | { type: "session"; valeur: Session }
  | { type: "refus"; message: string };

/**
 * Échange un couple courriel / mot de passe contre un jeton.
 *
 * Rend un refus explicite plutôt que de lever : un identifiant refusé n'est
 * pas une exception, c'est une réponse que l'utilisateur doit lire.
 */
export async function ouvrirSession(
  courriel: string,
  motDePasse: string,
): Promise<IssueConnexion> {
  if (!authDisponible()) {
    return {
      type: "refus",
      message:
        "authentification non configuree: NEXT_PUBLIC_SUPABASE_URL et " +
        "NEXT_PUBLIC_SUPABASE_ANON_KEY sont absentes. Voir " +
        "eurostruct/api/.env.example.",
    };
  }
  let reponse: Response;
  try {
    reponse = await fetch(
      `${URL_SUPABASE}/auth/v1/token?grant_type=password`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json", apikey: CLE_ANON },
        body: JSON.stringify({ email: courriel, password: motDePasse }),
      },
    );
  } catch (cause) {
    return { type: "refus", message: `Supabase injoignable (${String(cause)}).` };
  }

  const corps: unknown = await reponse.json().catch(() => null);
  if (!reponse.ok || !corps || typeof corps !== "object") {
    // ON NE RECOPIE PAS LE MESSAGE DE SUPABASE TEL QUEL. Il distingue parfois
    // « utilisateur inconnu » de « mot de passe faux », ce qui donne un
    // oracle d'enumeration de comptes.
    return { type: "refus", message: "identifiants refuses." };
  }
  const c = corps as { access_token?: string; expires_in?: number };
  if (!c.access_token) {
    return { type: "refus", message: "reponse sans jeton d'acces." };
  }
  return {
    type: "session",
    valeur: {
      jeton: c.access_token,
      expire_a: Date.now() + (c.expires_in ?? 3600) * 1000,
    },
  };
}

/** Le jeton est-il encore utilisable ? Marge d'une minute. */
export function sessionValide(s: Session | null): s is Session {
  return Boolean(s && s.expire_a - 60_000 > Date.now());
}
