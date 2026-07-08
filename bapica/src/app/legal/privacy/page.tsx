import type { Metadata } from "next"
import { LegalShell, LegalSection } from "@/components/pages/legal-shell"

export const metadata: Metadata = {
  title: "Politique de confidentialité",
  description:
    "Comment Bapica collecte, utilise et protège vos données personnelles conformément au RGPD.",
}

export default function PrivacyPage() {
  return (
    <LegalShell
      title="Politique de confidentialité"
      subtitle="Nous nous engageons à protéger vos données personnelles et à respecter votre vie privée."
      updated="4 juillet 2026"
    >
      <LegalSection title="1. Responsable du traitement">
        <p>
          Le responsable du traitement des données est la société{" "}
          <strong>Bapica</strong>, SAS au capital de 1&nbsp;000&nbsp;€, dont le
          siège social est à Paris (SIRET 000&nbsp;000&nbsp;000). Pour toute
          question, contactez notre délégué à la protection des données à
          l&apos;adresse dpo@bapica.com.
        </p>
      </LegalSection>

      <LegalSection title="2. Données collectées">
        <p>Nous collectons les catégories de données suivantes :</p>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            <strong>Données d&apos;identification</strong> : nom, prénom,
            adresse e-mail, mot de passe (chiffré).
          </li>
          <li>
            <strong>Données de facturation</strong> : gérées par Stripe (nous ne
            stockons aucune donnée de carte bancaire).
          </li>
          <li>
            <strong>Données d&apos;usage</strong> : conversations avec les
            Agents, historique d&apos;utilisation, journaux de connexion.
          </li>
          <li>
            <strong>Données techniques</strong> : adresse IP, type de
            navigateur, cookies.
          </li>
        </ul>
      </LegalSection>

      <LegalSection title="3. Finalités du traitement">
        <p>Vos données sont traitées pour :</p>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            gérer votre authentification et votre compte (via{" "}
            <strong>Supabase</strong>) ;
          </li>
          <li>
            traiter vos paiements et votre abonnement (via{" "}
            <strong>Stripe</strong>) ;
          </li>
          <li>fournir et améliorer les fonctionnalités des Agents ;</li>
          <li>vous envoyer des communications liées au service (via Resend) ;</li>
          <li>assurer la sécurité et prévenir la fraude.</li>
        </ul>
      </LegalSection>

      <LegalSection title="4. Base légale">
        <p>
          Les traitements reposent sur : l&apos;exécution du contrat
          (fourniture du service et facturation), notre intérêt légitime
          (sécurité, amélioration du service), votre consentement (cookies non
          essentiels) et le respect de nos obligations légales (comptabilité,
          lutte contre la fraude).
        </p>
      </LegalSection>

      <LegalSection title="5. Durée de conservation">
        <p>
          Les données de compte sont conservées pendant toute la durée de la
          relation contractuelle, puis archivées ou supprimées dans un délai
          maximal de 3 ans après la clôture du compte. Les données de
          facturation sont conservées 10 ans conformément aux obligations
          comptables.
        </p>
      </LegalSection>

      <LegalSection title="6. Destinataires et sous-traitants">
        <p>
          Vos données sont accessibles à nos équipes habilitées et à nos
          sous-traitants techniques : <strong>Supabase</strong>{" "}
          (authentification et base de données), <strong>Stripe</strong>{" "}
          (paiement), <strong>Vercel</strong> (hébergement) et{" "}
          <strong>Resend</strong> (envoi d&apos;e-mails). Chacun agit dans le
          cadre d&apos;accords conformes au RGPD.
        </p>
      </LegalSection>

      <LegalSection title="7. Vos droits">
        <p>
          Conformément au RGPD, vous disposez des droits d&apos;accès, de
          rectification, d&apos;effacement, de limitation, d&apos;opposition et
          de portabilité de vos données. Vous pouvez exercer ces droits à tout
          moment via notre{" "}
          <a href="/legal/rgpd" className="text-primary hover:underline">
            page RGPD
          </a>{" "}
          ou en écrivant à dpo@bapica.com.
        </p>
      </LegalSection>

      <LegalSection title="8. Cookies">
        <p>
          Nous utilisons des cookies strictement nécessaires au fonctionnement
          de la Plateforme (session, authentification) ainsi que, sous réserve
          de votre consentement, des cookies de mesure d&apos;audience. Vous
          pouvez configurer vos préférences à tout moment depuis votre
          navigateur.
        </p>
      </LegalSection>

      <LegalSection title="9. Contact DPO">
        <p>
          Pour toute question relative à vos données personnelles, contactez
          notre Délégué à la Protection des Données (DPO) à l&apos;adresse{" "}
          <strong>dpo@bapica.com</strong>. Vous pouvez également saisir la CNIL
          (
          <a
            href="https://www.cnil.fr"
            className="text-primary hover:underline"
            target="_blank"
            rel="noopener noreferrer"
          >
            www.cnil.fr
          </a>
          ).
        </p>
      </LegalSection>
    </LegalShell>
  )
}
