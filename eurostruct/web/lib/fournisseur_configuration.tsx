"use client";

/**
 * Le pont entre le serveur qui LIT la configuration et le client qui l'UTILISE.
 *
 * POURQUOI UN COMPOSANT, ET PAS UNE BALISE `<script>`
 * ----------------------------------------------------
 * Le layout est un composant serveur : il lit `process.env` à chaque requête,
 * ce qui est le seul moyen qu'une même image serve plusieurs environnements.
 * Restait à faire descendre ces trois chaînes jusqu'au navigateur.
 *
 * La rédaction précédente les écrivait dans un `<script>` posé dans `<head>`.
 * React 19 **hisse** les balises `<script>` hors de l'endroit où on les
 * déclare : le HTML du serveur et l'arbre du client cessaient de correspondre,
 * et chaque chargement levait l'erreur d'hydratation #418 — mesurée sur
 * `next build` puis `next start`, et confirmée par neutralisation.
 *
 * ICI, LES VALEURS SONT DES PROPS. React les sérialise lui-même dans la charge
 * utile du composant client, les échappe lui-même, et les rend disponibles
 * AVANT le premier rendu des enfants. Il n'y a plus de balise à hisser, plus
 * de chaîne JavaScript composée à la main, et plus de moment où la
 * configuration n'existe pas encore.
 *
 * DEUX CHEMINS DE LECTURE, ET CHACUN A SA RAISON
 * ------------------------------------------------
 * `useConfiguration()` sert les composants : c'est le chemin React, il
 * re-rend quand la valeur change, et il échoue bruyamment hors du
 * fournisseur.
 *
 * `poserConfiguration()` sert la couche de transport, qui n'est pas un
 * composant : `base()` est appelée depuis un gestionnaire d'événement, une
 * promesse, un `fetch`. Un hook n'y a pas sa place. La valeur est posée
 * PENDANT le rendu — pas dans un effet — pour qu'aucun enfant ne puisse la
 * lire avant qu'elle n'existe.
 */
import { createContext, useContext } from "react";
import {
  poserConfiguration,
  type ConfigurationPublique,
} from "@/lib/configuration";

const Contexte = createContext<ConfigurationPublique | null>(null);

export function FournisseurConfiguration(
  { valeur, children }: {
    valeur: ConfigurationPublique;
    children: React.ReactNode;
  },
) {
  //: PENDANT LE RENDU, PAS DANS UN EFFET.
  //:
  //: Un effet s'exécute APRÈS le montage des enfants. Un enfant qui appellerait
  //: `base()` au montage — pour charger une liste, par exemple — lirait alors
  //: une configuration absente et refuserait, une fois, au premier affichage.
  //:
  //: L'appel est idempotent et ne fait rien côté serveur, où l'état de module
  //: est partagé entre les requêtes.
  poserConfiguration(valeur);

  return <Contexte.Provider value={valeur}>{children}</Contexte.Provider>;
}

/**
 * La configuration, pour un composant.
 *
 * ELLE LÈVE HORS DU FOURNISSEUR plutôt que de rendre des chaînes vides : un
 * écran qui afficherait « API non configurée » alors que le vrai défaut est un
 * fournisseur manquant enverrait chercher au mauvais endroit.
 */
export function useConfiguration(): ConfigurationPublique {
  const valeur = useContext(Contexte);
  if (valeur === null) {
    throw new Error(
      "useConfiguration() hors de FournisseurConfiguration: le layout doit "
      + "envelopper l'application, sinon l'adresse de l'API ne descend pas "
      + "jusqu'ici.",
    );
  }
  return valeur;
}
