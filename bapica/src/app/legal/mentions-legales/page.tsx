import type { Metadata } from "next"
import { LegalShell, LegalSection } from "@/components/pages/legal-shell"

export const metadata: Metadata = {
  title: "Mentions légales — Bapica",
  description:
    "Mentions légales de Bapica : éditeur, hébergeur et informations de contact.",
}

export default function MentionsLegalesPage() {
  return (
    <LegalShell
      title="Mentions légales"
      subtitle="Informations relatives à l'éditeur et à l'hébergement du site Bapica."
      updated="4 juillet 2026"
    >
      <LegalSection title="Éditeur du site">
        <p>
          Le site et la plateforme Bapica sont édités par la société{" "}
          <strong>Bapica</strong>, société par actions simplifiée (SAS) au
          capital de 1&nbsp;000&nbsp;€.
        </p>
        <ul className="list-disc space-y-1 pl-5">
          <li>SIRET : 000&nbsp;000&nbsp;000</li>
          <li>Siège social : Paris, France</li>
          <li>Adresse e-mail : contact@bapica.com</li>
          <li>Numéro de TVA intracommunautaire : à déterminer</li>
        </ul>
      </LegalSection>

      <LegalSection title="Directeur de la publication">
        <p>
          Le directeur de la publication est le représentant légal de la société
          Bapica.
        </p>
      </LegalSection>

      <LegalSection title="Hébergeur">
        <p>Le site est hébergé par :</p>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            <strong>Vercel Inc.</strong>
          </li>
          <li>340 S Lemon Ave #4133, Walnut, CA 91789, États-Unis</li>
          <li>
            Site web :{" "}
            <a
              href="https://vercel.com"
              className="text-primary hover:underline"
              target="_blank"
              rel="noopener noreferrer"
            >
              vercel.com
            </a>
          </li>
        </ul>
      </LegalSection>

      <LegalSection title="Contact">
        <p>
          Pour toute question relative au site, vous pouvez nous écrire à
          l&apos;adresse contact@bapica.com ou via notre{" "}
          <a href="/contact" className="text-primary hover:underline">
            formulaire de contact
          </a>
          .
        </p>
      </LegalSection>

      <LegalSection title="Propriété intellectuelle">
        <p>
          L&apos;ensemble des éléments présents sur le site (textes,
          graphismes, logos, marques) est protégé par le droit de la propriété
          intellectuelle et demeure la propriété exclusive de Bapica. Toute
          reproduction sans autorisation préalable est interdite.
        </p>
      </LegalSection>

      <LegalSection title="Données personnelles et CNIL">
        <p>
          Les traitements de données personnelles mis en œuvre par Bapica sont
          réalisés dans le respect du RGPD et de la loi Informatique et Libertés
          du 6 janvier 1978 modifiée. Vous disposez de droits sur vos données,
          détaillés dans notre{" "}
          <a href="/legal/privacy" className="text-primary hover:underline">
            Politique de confidentialité
          </a>{" "}
          et notre{" "}
          <a href="/legal/rgpd" className="text-primary hover:underline">
            page RGPD
          </a>
          .
        </p>
        <p>
          Vous pouvez également introduire une réclamation auprès de la
          Commission Nationale de l&apos;Informatique et des Libertés (CNIL),
          3 place de Fontenoy, 75007 Paris —{" "}
          <a
            href="https://www.cnil.fr"
            className="text-primary hover:underline"
            target="_blank"
            rel="noopener noreferrer"
          >
            www.cnil.fr
          </a>
          .
        </p>
      </LegalSection>
    </LegalShell>
  )
}
