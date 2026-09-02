import type { Metadata } from "next";
import type { ReactNode } from "react";
import { configurationDuServeur } from "@/lib/configuration";
import { FournisseurConfiguration } from "@/lib/fournisseur_configuration";
import "./globals.css";

export const metadata: Metadata = {
  title: "EUROSTRUCT — vérification EC2",
  description:
    "Vérification d'une poutre en béton armé, Eurocode 2 avec Annexe " +
    "Nationale.",
};

/**
 * RENDU A CHAQUE REQUETE, JAMAIS FIGE AU BUILD.
 *
 * Sans cela, Next mettrait la page en cache statique et la configuration
 * servie serait celle du **moment du build** — c'est-à-dire exactement le
 * problème que `lib/configuration.ts` existe pour éviter.
 */
export const dynamic = "force-dynamic";

/**
 * LA CONFIGURATION DESCEND EN PROPS REACT, PAS EN BALISE `<script>`.
 *
 * CE QUE LA RÉDACTION PRÉCÉDENTE COÛTAIT
 * ----------------------------------------
 * Elle écrivait `window.__EUROSTRUCT__ = {…}` dans un `<script>` posé dans
 * `<head>`, avec un échappement manuel de `<` contre un `</script>` qui
 * terminerait la balise.
 *
 * React 19 **hisse** les balises `<script>` hors de l'endroit où on les
 * déclare. Le HTML rendu par le serveur et l'arbre reconstruit par le client
 * ne correspondaient donc plus, et **chaque chargement de page** levait
 * l'erreur #418 : « hydration failed… this tree will be regenerated on the
 * client ». Mesuré sur une construction de production réelle (`next build`
 * puis `next start`), puis confirmé par neutralisation — le `<head>` retiré,
 * l'erreur disparaît.
 *
 * Une hydratation qui échoue n'est pas un avertissement cosmétique : React
 * jette l'arbre rendu par le serveur et le reconstruit entièrement côté
 * client.
 *
 * CE QUE CELA NE CHANGE PAS
 * --------------------------
 * `process.env` est toujours lu ICI, dans un composant serveur, à chaque
 * requête. La même image sert toujours n'importe quel environnement, et rien
 * n'est figé au build : c'est la propriété qui comptait, et elle tient.
 *
 * L'ÉCHAPPEMENT NE DISPARAÎT PAS, IL CHANGE DE MAIN. React sérialise ses props
 * lui-même ; il n'y a plus de JavaScript composé à la main dans lequel une
 * valeur d'environnement pourrait s'échapper. La garde manuelle part avec le
 * risque qu'elle couvrait, pas avant lui.
 */
export default function RacineLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="fr">
      <body>
        <FournisseurConfiguration valeur={configurationDuServeur()}>
          {children}
        </FournisseurConfiguration>
      </body>
    </html>
  );
}
