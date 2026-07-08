import type { Metadata } from "next"
import { LegalShell, LegalSection } from "@/components/pages/legal-shell"

export const metadata: Metadata = {
  title: "RGPD",
  description:
    "Protection des données personnelles chez Bapica : vos droits, nos sous-traitants et nos engagements RGPD.",
}

export default function RGPDPage() {
  return (
    <LegalShell
      title="Protection des données (RGPD)"
      subtitle="Vos données vous appartiennent. Voici comment nous les protégeons et comment exercer vos droits."
      updated="4 juillet 2026"
    >
      <LegalSection title="Notre engagement">
        <p>
          Bapica traite les données personnelles conformément au Règlement
          Général sur la Protection des Données (Règlement UE 2016/679) et à la
          loi Informatique et Libertés. Nous appliquons les principes de
          minimisation, de transparence et de sécurité par défaut.
        </p>
      </LegalSection>

      <LegalSection title="Délégué à la protection des données (DPO)">
        <p>
          Un Délégué à la Protection des Données est votre point de contact pour
          toute question relative à vos données personnelles :
        </p>
        <ul className="list-disc space-y-1 pl-5">
          <li>E-mail : dpo@bapica.com</li>
          <li>Courrier : Bapica — DPO, Paris, France</li>
        </ul>
      </LegalSection>

      <LegalSection title="Vos droits">
        <p>Vous disposez à tout moment des droits suivants :</p>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            <strong>Droit d&apos;accès</strong> : obtenir une copie des données
            que nous détenons sur vous.
          </li>
          <li>
            <strong>Droit de rectification</strong> : corriger des données
            inexactes ou incomplètes.
          </li>
          <li>
            <strong>Droit à l&apos;effacement</strong> : demander la suppression
            de vos données (« droit à l&apos;oubli »).
          </li>
          <li>
            <strong>Droit à la portabilité</strong> : récupérer vos données dans
            un format structuré et lisible par machine.
          </li>
          <li>
            <strong>Droit d&apos;opposition et de limitation</strong> : vous
            opposer à un traitement ou en demander la limitation.
          </li>
        </ul>
      </LegalSection>

      <LegalSection title="Exercer vos droits">
        <p>
          Pour exercer l&apos;un de ces droits, deux possibilités s&apos;offrent
          à vous :
        </p>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            adresser une demande par e-mail à <strong>dpo@bapica.com</strong> en
            précisant le droit concerné ;
          </li>
          <li>
            utiliser notre{" "}
            <a href="/contact" className="text-primary hover:underline">
              formulaire de contact
            </a>{" "}
            en indiquant « Demande RGPD » dans votre message.
          </li>
        </ul>
        <p>
          Nous répondons à toute demande dans un délai maximal d&apos;un mois.
          Une pièce justificative d&apos;identité pourra vous être demandée afin
          de vérifier votre identité.
        </p>
      </LegalSection>

      <LegalSection title="Nos sous-traitants">
        <p>
          Nous faisons appel à des sous-traitants sélectionnés pour leur
          conformité au RGPD :
        </p>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            <strong>Supabase</strong> — authentification et base de données.
          </li>
          <li>
            <strong>Stripe</strong> — traitement des paiements.
          </li>
          <li>
            <strong>Vercel</strong> — hébergement de la plateforme.
          </li>
          <li>
            <strong>Resend</strong> — envoi des e-mails transactionnels.
          </li>
        </ul>
      </LegalSection>

      <LegalSection title="Durée de conservation">
        <p>
          Les données de compte sont conservées pendant la durée de la relation
          contractuelle, puis supprimées dans un délai maximal de 3 ans après la
          clôture du compte. Les documents comptables et de facturation sont
          conservés 10 ans conformément aux obligations légales.
        </p>
      </LegalSection>

      <LegalSection title="Sécurité">
        <p>
          Nous mettons en œuvre des mesures techniques et organisationnelles
          adaptées : chiffrement des données en transit (TLS) et au repos,
          contrôle des accès, journalisation, sauvegardes régulières et
          hébergement au sein d&apos;infrastructures sécurisées.
        </p>
      </LegalSection>

      <LegalSection title="Réclamation">
        <p>
          Si vous estimez que vos droits ne sont pas respectés, vous pouvez
          introduire une réclamation auprès de la CNIL —{" "}
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
