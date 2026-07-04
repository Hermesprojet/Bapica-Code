import type { Metadata } from 'next'
import Link from 'next/link'
import { Navbar } from '@/components/landing/navbar'
import { Footer } from '@/components/landing/footer'

export const metadata: Metadata = { title: 'Conditions Générales de Vente | Bapica' }

export default function CGVPage() {
  return (
    <>
      <Navbar />
      <main className="pt-24 pb-20">
        <div className="container mx-auto max-w-3xl px-4">
          <Link href="/" className="mb-8 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors">
            ← Retour à l&apos;accueil
          </Link>
          <h1 className="text-3xl font-bold tracking-tight mb-2">Conditions Générales de Vente</h1>
          <p className="text-sm text-muted-foreground mb-10">Dernière mise à jour : 4 juillet 2026</p>
          <div className="space-y-6 text-sm leading-relaxed text-muted-foreground">
            <h2 className="text-lg font-semibold text-foreground mt-10">Préambule</h2>
            <p>Les présentes Conditions Générales de Vente régissent l&apos;accès et l&apos;utilisation de la plateforme Bapica, éditée par la société Bapica, SAS au capital de 1 000 €, immatriculée au RCS de Paris sous le numéro 000 000 000, dont le siège social est situé à Paris.</p>

            <h2 className="text-lg font-semibold text-foreground mt-10">Article 1 — Définitions</h2>
            <p><strong>« Plateforme »</strong> : l&apos;application web Bapica accessible depuis le site bapica.com.</p>
            <p><strong>« Agent IA »</strong> : assistant virtuel spécialisé dans une fonction métier.</p>
            <p><strong>« Abonnement »</strong> : formule d&apos;accès aux services, souscrite pour une durée mensuelle.</p>
            <p><strong>« Client »</strong> : toute personne physique ou morale souscrivant à un abonnement.</p>

            <h2 className="text-lg font-semibold text-foreground mt-10">Article 2 — Services</h2>
            <p>Bapica propose une plateforme multi-agents IA pour PME et indépendants. Les agents disponibles varient selon la formule (Essentiel 8 agents ou Pro 12 agents). Bapica s&apos;engage à mettre en œuvre les moyens nécessaires pour assurer la continuité du service.</p>

            <h2 className="text-lg font-semibold text-foreground mt-10">Article 3 — Prix</h2>
            <p>Formule Essentiel : <strong>49 € TTC / mois</strong> — Formule Pro : <strong>79 € TTC / mois</strong>. TVA au taux de 20 % incluse. Bapica peut modifier ses tarifs sous réserve d&apos;un préavis de 30 jours.</p>

            <h2 className="text-lg font-semibold text-foreground mt-10">Article 4 — Période d&apos;essai</h2>
            <p>Le Client bénéficie de <strong>15 jours d&apos;essai gratuit</strong> sans carte bancaire. Après cette période, souscription à l&apos;abonnement ou résiliation sans frais.</p>

            <h2 className="text-lg font-semibold text-foreground mt-10">Article 5 — Paiement</h2>
            <p>Paiement par carte bancaire via Stripe. Prélèvement mensuel. En cas d&apos;impayé, l&apos;accès peut être suspendu.</p>

            <h2 className="text-lg font-semibold text-foreground mt-10">Article 6 — Propriété intellectuelle</h2>
            <p>La plateforme est la propriété de Bapica. Les contenus générés par les agents IA appartiennent au Client.</p>

            <h2 className="text-lg font-semibold text-foreground mt-10">Article 7 — Données personnelles</h2>
            <p>Conformément à notre Politique de Confidentialité. Hébergement Supabase (UE). Paiement Stripe. Emails Resend.</p>

            <h2 className="text-lg font-semibold text-foreground mt-10">Article 8 — Résiliation</h2>
            <p>Résiliation possible à tout moment depuis le tableau de bord. Effet en fin de période en cours.</p>

            <h2 className="text-lg font-semibold text-foreground mt-10">Article 9 — Droit applicable</h2>
            <p>Droit français. Tribunaux compétents de Paris.</p>
          </div>
        </div>
      </main>
      <Footer />
    </>
  )
}
