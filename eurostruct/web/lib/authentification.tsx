"use client";

/**
 * LA SESSION VIT ICI, ET NULLE PART AILLEURS.
 *
 * CE QUE CE MODULE RÉPARE
 * ------------------------
 * `Connexion` gardait la session dans son propre `useState`. Le jeton était
 * donc obtenu, affiché — « Session ouverte » — et **jamais utilisé** : aucun
 * autre composant ne pouvait le voir, `sessionValide()` n'était appelée nulle
 * part, et aucune action d'autorité n'existait. Un jeton obtenu et jamais
 * employé n'est pas une authentification : c'est une case cochée.
 *
 * Le remonter au niveau d'un fournisseur fait trois choses d'un coup : les
 * actions d'autorité y accèdent, l'expiration se surveille en un seul endroit,
 * et la déconnexion vide réellement la seule copie qui existe.
 *
 * OÙ EST LE JETON, EXACTEMENT
 * ----------------------------
 * Dans un `useRef`, en mémoire de l'onglet. Pas dans `localStorage`, pas dans
 * `sessionStorage`, pas dans un cookie, pas dans une URL. Rien de ce module
 * n'écrit un jeton ailleurs que dans cette référence, et rien ne le journalise.
 *
 * Pourquoi une référence en plus de l'état React : l'état sert à **afficher**,
 * la référence à **partir**. Un `fetch` déclenché depuis une fermeture capturée
 * lirait sinon la session du rendu précédent — c'est-à-dire, précisément au
 * moment d'un renouvellement, l'ancien jeton.
 *
 * L'EXPIRATION EST SURVEILLÉE, PAS SUBIE
 * ---------------------------------------
 * Un minuteur se déclenche à l'échéance, marge comprise :
 *
 *   * un jeton de renouvellement existe -> on renouvelle **en mémoire**, et
 *     l'utilisateur ne voit rien ;
 *   * il n'y en a pas, ou il est refusé -> on **ferme** la session et on
 *     demande une reconnexion. Pas de session à demi vivante.
 *
 * Dans les deux cas, aucune requête ne part avec un jeton périmé.
 */

import {
  createContext, useCallback, useContext, useEffect, useMemo, useRef, useState,
} from "react";
import {
  MARGE_EXPIRATION_MS, authDisponible, ouvrirSession, renouvelerSession,
  resteMs, sessionValide, type Session,
} from "@/lib/session";
import type { PorteurDeJeton } from "@/lib/transport";

/** Ce qu'un écran peut savoir de la session — jamais le jeton lui-même. */
export type EtatAuth = {
  /** Une session utilisable est ouverte. */
  connecte: boolean;
  /** Une session a existé puis a expiré sans pouvoir être renouvelée. */
  expiree: boolean;
  /** La configuration Supabase est présente. */
  disponible: boolean;
  ouvrir(courriel: string, motDePasse: string): Promise<string | null>;
  fermer(): void;
  /** Le porteur à passer à `appelProtege`. Stable. */
  porteur: PorteurDeJeton;
};

const Contexte = createContext<EtatAuth | null>(null);

/**
 * Le fournisseur. Une seule instance, au sommet de la page.
 *
 * LE JETON N'EST PAS DANS LA VALEUR DU CONTEXTE. Seul un booléen en sort, et
 * un porteur qui sait le produire au moment de partir. Un contexte qui
 * exposerait le jeton le rendrait lisible depuis n'importe quel composant, y
 * compris ceux qu'on ajoutera plus tard sans y penser.
 */
export function FournisseurAuth({ children }: { children: React.ReactNode }) {
  const session = useRef<Session | null>(null);
  const [connecte, setConnecte] = useState(false);
  const [expiree, setExpiree] = useState(false);
  //: Renouvellement EN VOL. Deux actions simultanées sur un jeton échu ne
  //: doivent pas produire deux échanges: GoTrue fait tourner le jeton de
  //: renouvellement, si bien que le second échange échouerait avec un jeton
  //: déjà consommé — et fermerait une session parfaitement saine.
  const enVol = useRef<Promise<Session | null> | null>(null);
  const [echeance, setEcheance] = useState(0);

  /**
   * NUMÉRO DE LA SESSION COURANTE. Il s'incrémente à chaque ouverture et à
   * chaque fermeture.
   *
   * CE QU'IL EMPÊCHE, ET QUI EST ARRIVÉ. Le renouvellement est un aller-retour
   * réseau. Si l'utilisateur se déconnecte **pendant** cet aller-retour, la
   * réponse revient après coup et `poser(issue.valeur)` **rouvre la session
   * qu'il vient de fermer** — avec un jeton frais, et sans que rien à l'écran
   * ne le dise. Le parcours navigateur l'a produit tout seul : le compte à
   * jeton court renouvelle toutes les cinq secondes, et une déconnexion tombe
   * tôt ou tard dans cette fenêtre.
   *
   * Un échange ne peut donc écrire que si le numéro n'a pas bougé depuis son
   * départ. Sinon il est caduc, et sa réponse est jetée.
   */
  const generation = useRef(0);

  /**
   * NUMERO DE LA DERNIERE DEMANDE D'OUVERTURE. Il s'incrémente au DEPART de
   * chaque connexion, et à chaque fermeture.
   *
   * DEUX COURSES QUE `generation` NE VOYAIT PAS, parce qu'elle ne bouge qu'à
   * l'ARRIVEE d'une session:
   *
   *   * une connexion LENTE qui revient après une déconnexion. `ouvrir()`
   *     écrivait sans rien vérifier: la session se rouvrait toute seule, avec
   *     un jeton frais, alors que la personne venait de partir — le même
   *     défaut que le renouvellement en vol, sur l'autre chemin;
   *   * deux connexions SIMULTANEES. Si la première est plus lente que la
   *     seconde, sa réponse arrive en dernier et ECRASE la plus récente. On se
   *     retrouve connecté sous le compte qu'on n'a pas choisi en dernier —
   *     et sur un écran d'autorité, c'est l'identité qui décide qui approuve.
   *
   * Une réponse d'ouverture n'écrit donc que si son numéro est encore le
   * dernier émis.
   */
  const demande = useRef(0);

  const poser = useCallback((s: Session | null) => {
    session.current = s;
    setConnecte(s !== null);
    setEcheance(s ? s.expire_a : 0);
  }, []);

  const fermer = useCallback(() => {
    // LA SEULE COPIE DISPARAIT. Il n'y en a pas d'autre à nettoyer, ce qui est
    // exactement la raison de n'en avoir jamais fait de seconde.
    generation.current += 1;
    // ET LES OUVERTURES EN VOL SONT PERIMEES. Une connexion lente qui revient
    // après ce clic ne doit pas rouvrir ce que la personne vient de fermer.
    demande.current += 1;
    enVol.current = null;
    poser(null);
    setExpiree(false);
  }, [poser]);

  const _renouveler = useCallback(async (): Promise<Session | null> => {
    const courante = session.current;
    if (!courante) return null;
    if (enVol.current) return enVol.current;

    const mienne = generation.current;
    const echange = (async () => {
      const issue = await renouvelerSession(courante);
      // CADUC: la session a été fermée ou remplacée pendant l'aller-retour.
      // On ne rouvre rien, et on ne signale pas non plus une expiration qui
      // ne concerne plus personne.
      if (mienne !== generation.current) return null;
      if (issue.type === "session") {
        poser(issue.valeur);
        setExpiree(false);
        return issue.valeur;
      }
      // REFUS DE RENOUVELLEMENT: on ferme. Une session qu'on ne peut plus
      // prolonger n'est pas une session en sursis.
      generation.current += 1;
      poser(null);
      setExpiree(true);
      return null;
    })();

    enVol.current = echange;
    try {
      return await echange;
    } finally {
      if (enVol.current === echange) enVol.current = null;
    }
  }, [poser]);

  const ouvrir = useCallback(
    async (courriel: string, motDePasse: string): Promise<string | null> => {
      // LE NUMERO EST PRIS AVANT L'ALLER-RETOUR, et relu après.
      const mienne = (demande.current += 1);
      const issue = await ouvrirSession(courriel, motDePasse);
      // CADUQUE: une déconnexion, ou une connexion PLUS RECENTE, est passée
      // pendant l'aller-retour. On ne rouvre rien et on n'écrase rien.
      if (mienne !== demande.current) return null;
      if (issue.type === "session") {
        // Une ouverture aussi périme les échanges en vol: le renouvellement
        // de la session précédente n'a plus rien à écrire ici.
        generation.current += 1;
        enVol.current = null;
        poser(issue.valeur);
        setExpiree(false);
        return null;
      }
      return issue.message;
    },
    [poser],
  );

  // LE MINUTEUR. Il ne lit pas l'horloge en boucle: il se pose une fois, à
  // l'échéance de la session courante, et se repose au renouvellement suivant.
  useEffect(() => {
    if (!echeance) return;
    const dans = Math.max(0, echeance - MARGE_EXPIRATION_MS - Date.now());
    const t = setTimeout(() => {
      const courante = session.current;
      if (!courante) return;
      if (courante.rafraichissement) {
        void _renouveler();
      } else {
        poser(null);
        setExpiree(true);
      }
    }, dans);
    return () => clearTimeout(t);
  }, [echeance, _renouveler, poser]);

  /**
   * Le porteur. **Stable** — sa référence ne change pas d'un rendu à l'autre —
   * parce qu'il lit `session.current` au moment de l'appel et non une valeur
   * capturée.
   */
  const porteur = useMemo<PorteurDeJeton>(
    () => ({
      async jetonUtilisable(): Promise<string | null> {
        const courante = session.current;
        if (!courante) return null;
        if (sessionValide(courante)) return courante.jeton;
        // ÉCHU. On tente le renouvellement, et à défaut on ferme. On ne rend
        // JAMAIS le jeton périmé « pour essayer quand même ».
        if (!courante.rafraichissement) {
          poser(null);
          setExpiree(true);
          return null;
        }
        const neuve = await _renouveler();
        return neuve ? neuve.jeton : null;
      },

      /**
       * APRES UN 401, ET SEULEMENT LA. Notre horloge disait « encore
       * valide »; le serveur dit non, et c'est lui qui a raison.
       *
       * On passe par le MEME `_renouveler` que le minuteur: son
       * dédoublonnage en vol reste donc valable, et deux appels qui prennent
       * un 401 en même temps ne consomment pas deux fois le jeton de
       * renouvellement — GoTrue le fait tourner, et le second échange
       * échouerait sur un jeton déjà utilisé.
       */
      async renouvellementForce(): Promise<string | null> {
        const courante = session.current;
        if (!courante || !courante.rafraichissement) {
          poser(null);
          setExpiree(true);
          return null;
        }
        const neuve = await _renouveler();
        return neuve ? neuve.jeton : null;
      },

      /**
       * Le serveur a refusé un jeton que nous croyions bon, et le
       * renouvellement n'a rien donné. Une session dont chaque appel fait 401
       * n'est pas une session: c'est un écran qui ment.
       */
      abandonner(): void {
        generation.current += 1;
        demande.current += 1;
        enVol.current = null;
        poser(null);
        setExpiree(true);
      },
    }),
    [_renouveler, poser],
  );

  const valeur = useMemo<EtatAuth>(
    () => ({
      connecte, expiree, disponible: authDisponible(),
      ouvrir, fermer, porteur,
    }),
    [connecte, expiree, ouvrir, fermer, porteur],
  );

  return <Contexte.Provider value={valeur}>{children}</Contexte.Provider>;
}

/** Accès à la session. Lève hors du fournisseur, plutôt que de rendre `null`.
 *
 * Un `null` silencieux produirait un écran qui n'authentifie plus sans que
 * rien ne le dise — le défaut même que ce module répare. */
export function useAuth(): EtatAuth {
  const v = useContext(Contexte);
  if (!v) {
    throw new Error(
      "useAuth hors de <FournisseurAuth>: la session n'est detenue nulle part.",
    );
  }
  return v;
}

export { resteMs };
