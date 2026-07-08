import type { Metadata } from "next"
import { LegalShell, LegalSection } from "@/components/pages/legal-shell"

export const metadata: Metadata = {
  title: "Conditions Générales d'Utilisation",
  description:
    "Conditions Générales d'Utilisation de la plateforme d'agents IA Bapica.",
}

export default function CGUPage() {
  return (
    <LegalShell
      title="Conditions Générales d'Utilisation"
      subtitle="Règles d'accès et d'usage de la plateforme Bapica."
      updated="4 juillet 2026"
    >
      <LegalSection title="Article 1 — Objet">
        <p>
          Les présentes Conditions Générales d&apos;Utilisation (« CGU »)
          définissent les modalités d&apos;accès et d&apos;utilisation de la
          plateforme Bapica. Toute utilisation de la Plateforme implique
          l&apos;acceptation sans réserve des présentes CGU.
        </p>
      </LegalSection>

      <LegalSection title="Article 2 — Accès à la plateforme">
        <p>
          La Plateforme est accessible 24h/24 et 7j/7, sous réserve des
          opérations de maintenance et des cas de force majeure. Bapica ne peut
          être tenue responsable des interruptions ou dysfonctionnements
          indépendants de sa volonté.
        </p>
        <p>
          L&apos;accès aux Agents nécessite la création d&apos;un compte et,
          selon les fonctionnalités, la souscription à un abonnement.
        </p>
      </LegalSection>

      <LegalSection title="Article 3 — Comptes utilisateurs">
        <p>
          Chaque utilisateur s&apos;engage à fournir des informations exactes
          lors de la création de son compte et à les maintenir à jour. Un compte
          est strictement personnel. L&apos;utilisateur est responsable de
          toutes les actions réalisées depuis son compte.
        </p>
      </LegalSection>

      <LegalSection title="Article 4 — Sécurité">
        <p>
          L&apos;utilisateur est responsable de la confidentialité de ses
          identifiants et mots de passe. En cas de suspicion d&apos;accès non
          autorisé, il s&apos;engage à en informer immédiatement Bapica. Bapica
          met en œuvre des mesures techniques (chiffrement, contrôle
          d&apos;accès) pour protéger la Plateforme.
        </p>
      </LegalSection>

      <LegalSection title="Article 5 — Usage autorisé">
        <p>L&apos;utilisateur s&apos;interdit notamment de :</p>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            utiliser la Plateforme à des fins illicites, frauduleuses ou
            contraires à l&apos;ordre public ;
          </li>
          <li>
            tenter de contourner les mesures de sécurité ou d&apos;accéder à des
            données de tiers ;
          </li>
          <li>
            perturber le fonctionnement de la Plateforme (surcharge, injection,
            rétro-ingénierie) ;
          </li>
          <li>
            générer via les Agents des contenus diffamatoires, haineux ou
            portant atteinte aux droits de tiers.
          </li>
        </ul>
      </LegalSection>

      <LegalSection title="Article 6 — Propriété intellectuelle">
        <p>
          La Plateforme et l&apos;ensemble de ses composants sont protégés par
          le droit de la propriété intellectuelle et demeurent la propriété de
          Bapica. Aucune disposition des présentes CGU ne confère à
          l&apos;utilisateur de droit de propriété sur la Plateforme.
        </p>
      </LegalSection>

      <LegalSection title="Article 7 — Responsabilité">
        <p>
          Les Agents s&apos;appuyant sur des technologies d&apos;intelligence
          artificielle, les contenus générés peuvent comporter des erreurs.
          L&apos;utilisateur demeure seul responsable de la vérification et de
          l&apos;usage qu&apos;il fait des résultats produits. Bapica ne saurait
          être tenue responsable des décisions prises sur cette base.
        </p>
      </LegalSection>

      <LegalSection title="Article 8 — Suspension et résiliation">
        <p>
          Bapica se réserve le droit de suspendre ou de supprimer, sans préavis,
          tout compte en cas de violation des présentes CGU, sans que cela
          n&apos;ouvre droit à indemnité. L&apos;utilisateur peut supprimer son
          compte à tout moment depuis son tableau de bord.
        </p>
      </LegalSection>

      <LegalSection title="Article 9 — Modification des CGU">
        <p>
          Bapica peut modifier les présentes CGU à tout moment. Les
          utilisateurs seront informés des modifications substantielles. La
          poursuite de l&apos;utilisation vaut acceptation des CGU mises à jour.
        </p>
      </LegalSection>
    </LegalShell>
  )
}
