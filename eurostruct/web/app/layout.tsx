import type { Metadata } from "next";
import type { ReactNode } from "react";
import { CLE_GLOBALE, type ConfigurationPublique } from "@/lib/configuration";
import "./globals.css";

export const metadata: Metadata = {
  title: "EUROSTRUCT — vérification EC2",
  description:
    "Vérification ELU en flexion simple, section rectangulaire, Eurocode 2 " +
    "avec Annexe Nationale.",
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
 * La configuration publique, lue dans l'environnement du PROCESSUS.
 *
 * Ce sont des variables sans préfixe `NEXT_PUBLIC_`, et c'est délibéré : ce
 * préfixe est précisément ce qui déclenche l'inlining dans le bundle. Lues
 * ici, dans un composant serveur, elles restent des variables de runtime — la
 * même image sert donc n'importe quel environnement.
 */
function configurationServie(): ConfigurationPublique {
  return {
    apiUrl: process.env.EUROSTRUCT_API_URL ?? "",
    supabaseUrl: process.env.EUROSTRUCT_SUPABASE_URL ?? "",
    supabaseAnonKey: process.env.EUROSTRUCT_SUPABASE_ANON_KEY ?? "",
  };
}

export default function RacineLayout({ children }: { children: ReactNode }) {
  const config = configurationServie();
  return (
    <html lang="fr">
      <head>
        {/*
          `JSON.stringify` PUIS ECHAPPEMENT DE `<`. Une valeur d'environnement
          contenant « </script> » terminerait la balise et le reste serait
          interprete comme du HTML. On n'attend pas ce contenu, et c'est
          justement pour cela qu'il faut s'en proteger: la garde ne coute rien,
          l'absence de garde coute une injection.

          RIEN DE SECRET N'EST DEPOSE ICI. L'adresse de l'API, celle de
          l'emetteur, et la cle anonyme de GoTrue — qui designe un projet et
          n'autorise rien. Tout ce qui atterrit dans `window` est lisible par
          quiconque ouvre la page.
        */}
        <script
          dangerouslySetInnerHTML={{
            __html:
              `window.${CLE_GLOBALE}=` +
              JSON.stringify(config).replace(/</g, "\\u003c") +
              ";",
          }}
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
